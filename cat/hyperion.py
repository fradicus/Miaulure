import os
import cv2
import numpy as np
import time
from datetime import datetime, timezone
from ultralytics import YOLO
import supervision as sv
from pymongo import MongoClient
import torch
# === Configuration and Setup ===

model = YOLO("yolo11s.pt")
model.to("cuda")
class_names = model.model.names

CONF_THRESHOLD = 0.2
NMS_IOU_THRESHOLD = 0.1

ZONE_BED = (0, 0, 180, 130)
ZONE_FOUNTAIN = (328, 160, 375, 192)
ZONE_FOOD = (445, 400, 580, 465)
ZONE_CAT_TREE = (460, 35, 630, 235)

BATHROOM_LINE_Y = 475
DOOR_LINE_X = 638
BATHROOM_BOX_HEIGHT = 5
DOOR_BOX_WIDTH = 5

mongo_uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(mongo_uri)
db = mongo_client["cat_activity_db"]
logs_col = db["activity_logs"]
system_logs_col = db["system_logs"]

tracker = sv.ByteTrack()

last_activity = None
last_seen_time = None
last_move_time = None
last_position = None
last_velocity = None
last_zone = None
person_cat_overlap = False
overlap_event_times = []
bathroom_entry_time = None
door_entry_time = None

BATHROOM_COOLDOWN = 60
DOOR_COOLDOWN = 30
SLEEP_TIMEOUT = 600.0
INTERACTION_WINDOW = 10.0

zone_timers = {
    "Fountain": None,
    "Food": None,
    "Cat Tree": None
}
zone_durations = {
    "Fountain": 6.0,
    "Food": 5.0,
    "Cat Tree": 6.0
}
zone_cooldowns = {
    "Fountain": None,
    "Food": None,
    "Cat Tree": None
}
zone_cooldown_period = 10.0

# === General Activity Timing Logic (for Playing, Idle) ===
activity_timers = {
    "Idle": None,
    "Playing": None
}
activity_durations = {
    "Idle": 40.0,        # Require 5 seconds of inactivity before logging Idle
    "Playing": 10.0     # Require 10 seconds of consistent interaction to log Playing
}
activity_cooldowns = {
    "Idle": None,
    "Playing": None
}
activity_cooldown_period = 8.0  # Prevent repeating activity logs too soon


def overlaps_zone(box, zone):
    x1, y1, x2, y2 = box
    zx1, zy1, zx2, zy2 = zone
    return (x1 < zx2 and x2 > zx1 and y1 < zy2 and y2 > zy1)

def get_center(box):
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return np.array([cx, cy])

def log_system_event(event_type, message):
    log_doc = {
        "timestamp": datetime.now(timezone.utc),
        "event": event_type,
        "message": message
    }
    try:
        system_logs_col.insert_one(log_doc)
    except Exception as e:
        print(f"Failed to log system event: {e}")

try:
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")
    
    log_system_event("START", "Monitoring started.")
    print("Monitoring started...")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        results = model.predict(source=frame, conf=CONF_THRESHOLD, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        detections = detections.with_nms(class_agnostic=False, threshold=NMS_IOU_THRESHOLD)
        tracked_detections = tracker.update_with_detections(detections)

        cat_detection = None
        person_detections = []
        toy_detections = []

        for i, class_id in enumerate(tracked_detections.class_id):
            name = class_names[class_id]
            box = tracked_detections.xyxy[i]

            if name in ["cat","dog","bird"]:
                cat_detection = {
                    "bbox": box,
                    "conf": float(tracked_detections.confidence[i]),
                    "track_id": tracked_detections.tracker_id[i]
                }
            elif name == "person":
                person_detections.append(box)
            elif name in ["sports ball", "cup", "teddy bear", "toy", "apple", "feather", "bottle", "toothbrush","book","suitcase"]:
                toy_detections.append(box)

        now = time.time()
        current_activity = None
        current_conf = None

        if cat_detection:
            x1, y1, x2, y2 = map(int, cat_detection["bbox"])
            cat_center = get_center((x1, y1, x2, y2))
            current_conf = cat_detection["conf"]

            moved = False
            if last_position is not None:
                moved = np.linalg.norm(cat_center - last_position) > 10
            else:
                moved = True

            if moved:
                last_move_time = now
                if last_activity == "Sleeping":
                    last_activity = None  # Reset so we can log "Woke up" behavior

            last_seen_time = now
            last_position = cat_center

            in_bed = overlaps_zone((x1, y1, x2, y2), ZONE_BED)
            in_fountain = overlaps_zone((x1, y1, x2, y2), ZONE_FOUNTAIN)
            in_food = overlaps_zone((x1, y1, x2, y2), ZONE_FOOD)
            in_cat_tree = overlaps_zone((x1, y1, x2, y2), ZONE_CAT_TREE)
            in_bathroom_box = overlaps_zone((x1, y1, x2, y2), (0, BATHROOM_LINE_Y, frame.shape[1], BATHROOM_LINE_Y + BATHROOM_BOX_HEIGHT))
            in_door_box = overlaps_zone((x1, y1, x2, y2), (DOOR_LINE_X, 0, DOOR_LINE_X + DOOR_BOX_WIDTH, frame.shape[0]))

            if in_bathroom_box and (not bathroom_entry_time or now - bathroom_entry_time > BATHROOM_COOLDOWN):
                bathroom_entry_time = now
                current_activity = "Bathroom"

            elif in_door_box and (not door_entry_time or now - door_entry_time > DOOR_COOLDOWN):
                door_entry_time = now
                current_activity = "Door"

            def should_log_zone(name):
                if zone_timers[name] is None:
                    zone_timers[name] = now
                elapsed = now - zone_timers[name]
                cooldown = now - zone_cooldowns[name] if zone_cooldowns[name] else float("inf")
                if elapsed >= zone_durations[name] and cooldown >= zone_cooldown_period:
                    zone_cooldowns[name] = now
                    zone_timers[name] = None
                    return True
                return False
            
            def should_log_activity(name):
                if activity_timers[name] is None:
                    activity_timers[name] = now
                elapsed = now - activity_timers[name]
                cooldown = now - activity_cooldowns[name] if activity_cooldowns[name] else float("inf")
                if elapsed >= activity_durations[name] and cooldown >= activity_cooldown_period:
                    activity_cooldowns[name] = now
                    activity_timers[name] = None
                    return True
                return False


            if current_activity is None:
                if in_fountain and should_log_zone("Fountain"):
                    current_activity = "Cat drinking water"
                elif in_food and should_log_zone("Food"):
                    current_activity = "Eating"
                elif in_cat_tree and should_log_zone("Cat Tree"):
                    current_activity = "climbing/scratching"
                elif in_bed:
                    current_activity = "On Bed"

            if current_activity is None:
                if len(overlap_event_times) >= 2 or toy_detections:
                    if should_log_activity("Playing" ):
                        current_activity = "Playing"

                elif should_log_activity("Idle"):
                    current_activity = "Idle"

            if last_seen_time is not None:
                time_since_seen = now - last_seen_time
                time_since_moved = now - last_move_time if last_move_time else float("inf")
                if (time_since_seen >= SLEEP_TIMEOUT or time_since_moved >= SLEEP_TIMEOUT):
                    if last_activity != "Sleeping":
                        current_activity = "Sleeping"
                        current_conf = None
            if current_activity and current_activity != last_activity:
                doc = {
                    "timestamp": datetime.now(timezone.utc),
                    "activity": current_activity,
                    "confidence": current_conf,
                    "zone": last_zone,
                    "position": {"x": float(cat_center[0]), "y": float(cat_center[1])}
                }
                logs_col.insert_one(doc)
                print(f"[{doc['timestamp']}] Activity: {current_activity}")
                last_activity = current_activity
           # = Visualize tracked detections on the frame ===
        for i, box in enumerate(tracked_detections.xyxy):
            x1, y1, x2, y2 = map(int, box)
            class_id = tracked_detections.class_id[i]
            label = class_names[class_id]
            track_id = tracked_detections.tracker_id[i]

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label and track ID
            label_text = f"{label} (ID:{track_id})" if track_id else label
            cv2.putText(frame, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 255, 0), 2)
        #=== Draw zone rectangles (optional visual debugging) ===
       # Draw BED zone
        cv2.rectangle(frame, (ZONE_BED[0], ZONE_BED[1]), (ZONE_BED[2], ZONE_BED[3]), (255, 255, 255), 2)  # White
        cv2.putText(frame, "BED", (ZONE_BED[0], ZONE_BED[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw FOUNTAIN zone
        cv2.rectangle(frame, (ZONE_FOUNTAIN[0], ZONE_FOUNTAIN[1]), (ZONE_FOUNTAIN[2], ZONE_FOUNTAIN[3]), (255, 0, 0), 2)  # Blue
        cv2.putText(frame, "FOUNTAIN", (ZONE_FOUNTAIN[0], ZONE_FOUNTAIN[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # Draw FOOD zone
        cv2.rectangle(frame, (ZONE_FOOD[0], ZONE_FOOD[1]), (ZONE_FOOD[2], ZONE_FOOD[3]), (0, 255, 255), 2)  # Yellow
        cv2.putText(frame, "FOOD", (ZONE_FOOD[0], ZONE_FOOD[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Draw CAT TREE zone
        cv2.rectangle(frame, (ZONE_CAT_TREE[0], ZONE_CAT_TREE[1]), (ZONE_CAT_TREE[2], ZONE_CAT_TREE[3]), (255, 0, 255), 2)  # Magenta
        cv2.putText(frame, "CAT TREE", (ZONE_CAT_TREE[0], ZONE_CAT_TREE[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

        # Draw bathroom line
        cv2.line(frame, (0, BATHROOM_LINE_Y), (frame.shape[1], BATHROOM_LINE_Y), (255, 0, 255), 2)  # Magenta

        # Draw door line
        cv2.line(frame, (DOOR_LINE_X, 0), (DOOR_LINE_X, frame.shape[0]), (255, 0, 255), 2)  # Magenta

        #draw_gridlines_with_coordinates(frame, rows=10, cols=10)
        cv2.imshow("Cat Monitor", frame)
        

        if cv2.waitKey(1) & 0xFF == ord('~'):
            print("Exit requested by user.")
            break

except KeyboardInterrupt:
    log_system_event("STOP", "User interrupted.")
    print("Keyboard Interrupt.")
except Exception as e:
    log_system_event("CRASH", str(e))
    print(f"Crash: {e}")
finally:
    cap.release()
    mongo_client.close()
