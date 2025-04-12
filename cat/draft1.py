import cv2
import numpy as np
import time
from datetime import datetime, timezone
from ultralytics import YOLO
import supervision as sv
from pymongo import MongoClient
#import msvcrt  # For keypress detection on Windows  ----for not displaying


# === Configuration and Setup 

# Roboflow API Key (make sure to set your actual API key as an environment variable or here).
# This may be required to load the YOLO-World model via the inference library.
# Example: export ROBOFLOW_API_KEY="YOUR_API_KEY"
# (If running offline with a local model weight, this might not be needed.)
# os.environ["ROBOFLOW_API_KEY"] = "<YOUR_API_KEY>"

# Initialize YOLO-World model (small variant for speed)&#8203;:contentReference[oaicite:1]{index=1}
model = YOLO("yolo11s.pt")


# Define the classes of objects we want the model to detect.
# We include 'cat' and 'person' for tracking, and some toy-related classes to detect play objects.
class_names = model.model.names  # For YOLOv11 (same as YOLOv8) = ["cat", "person", "sports ball", "toy","cardboard box","string"]   
# (Note: YOLO-World is zero-shot; the above text prompts guide detection. 
# Additional classes like "bowl" or "cup" could be added if needed to detect the water fountain or food bowl, 
# but since those are static and defined as zones, we rely on zones instead of detection for them.)

# Set inference parameters for performance.
CONF_THRESHOLD = 0.2  # Confidence threshold for detection (default is 0.5&#8203;:contentReference[oaicite:2]{index=2}; lowered to catch more objects)
NMS_IOU_THRESHOLD = 0.1  # IoU threshold for Non-Maximum Suppression to filter overlapping detections
################### Similarly, if “person” sometimes appears at 0.5% confidence due to a face-like pattern on a pillow, 
################### you could raise the model’s internal confidence for person by filtering detections: e.g., if name=="person" and confidence<0.5: drop i

# Define zone coordinates (pixel coordinates in the frame).
# These are based on a reference image of the room and need to be calibrated for the actual camera view.
# Coordinates are given as (x1, y1, x2, y2) for rectangular zones (top-left and bottom-right corners).
ZONE_BED = (0, 0, 180, 130)         # light blue (top-left bed)
ZONE_FOUNTAIN = (328, 160, 375, 192) # blue (bottom~!-right)
ZONE_FOOD = (450, 400, 580, 465)      # yellow (left of fountain)
ZONE_CAT_TREE = (460, 35, 630, 240)  # red/pink (right wall, mid-height)
   # red/pink (right side wall)
# The play area is the rest of the visible room not covered by the above zones.
# We will infer "play area" if the cat is not in any other zone.

# Define the horizontal "bathroom" boundary line (magenta line in reference image).
BATHROOM_LINE_Y = 475  # If the cat's center crosses below this y-coordinate, it's considered entering the bathroom area.

DOOR_LINE_X = 638  # If the cat's center crosses this x-coordinate, it's considered entering the door area.

# MongoDB Atlas connection setup.
# TODO: Replace the connection string with your MongoDB Atlas URI and credentials.
mongo_client = MongoClient("mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion")
db = mongo_client["cat_activity_db"]       
logs_col = db["activity_logs"]           
system_logs_col = db["system_logs"] 

mongo_client = MongoClient("mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion")
db = mongo_client["cat_activity_db"]
logs_col = db["activity_logs"]
system_logs_col = db["system_logs"]

# Initialize object tracker for persistent identity (using ByteTrack via Supervision).
tracker = sv.ByteTrack()

# State variables for activity logic
last_activity = None            # Last logged activity (to avoid duplicate logging)
last_seen_time = None           # Last time the cat was detected
last_move_time = None           # Last time the cat was seen moving
last_position = None            # Last known position of the cat (center of bounding box)
last_velocity = None            # Last velocity vector of the cat (dx, dy)
last_zone = None                # Last zone in which the cat was seen
cat_below_line = False          # Whether the cat is currently below the bathroom line
cat_right_line = False          # Whether the cat is currently in the door area
person_cat_overlap = False      # Whether cat was overlapping person in the previous frame (for detecting new interactions)
overlap_event_times = []        # Timestamps of recent cat-person overlap events (to count interactions within 10s)
SLEEP_TIMEOUT = 600.0           # 10 minutes in seconds for sleeping activity
INTERACTION_WINDOW = 10.0       # 10 seconds window for counting play interactions

# === Zone timing logic ===
zone_timers = {
    "Fountain": None,
    "Food": None,
    "Cat Tree": None
}
zone_durations = {
    "Fountain": 6.0,  # seconds cat must remain in zone
    "Food": 5.0,
    "Cat Tree": 6.0
}
zone_cooldowns = {
    "Fountain": None,
    "Food": None,
    "Cat Tree": None
}
zone_cooldown_period = 10.0  # prevent re-logging too soon


# def draw_gridlines_with_coordinates(frame, rows=10, cols=10, color=(0, 255, 0), thickness=1, font_scale=0.4):
#     height, width, _ = frame.shape
#     # Draw horizontal and vertical lines
#     for i in range(1, rows):
#         y = int(i * height / rows)
#         cv2.line(frame, (0, y), (width, y), color, thickness)
#         cv2.putText(frame, f"y={y}", (5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

#     for i in range(1, cols):
#         x = int(i * width / cols)
#         cv2.line(frame, (x, 0), (x, height), color, thickness)
#         cv2.putText(frame, f"x={x}", (x + 5, 15), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

    # # Display intersection coordinates
    # for i in range(1, rows):
    #     for j in range(1, cols):
    #         x = int(j * width / cols)
    #         y = int(i * height / rows)
    #         cv2.putText(frame, f"({x},{y})", (x + 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

# Helper function to check if a bounding box overlaps a zone (rectangular).
def overlaps_zone(box, zone):
    """Check if the bounding box (x1,y1,x2,y2) intersects with the rectangular zone (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = box
    zx1, zy1, zx2, zy2 = zone
    # Overlap if the box and zone overlap in both x and y ranges
    return (x1 < zx2 and x2 > zx1 and y1 < zy2 and y2 > zy1)

# Helper function to get the center of a bounding box.
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
# === Main Video Processing Loop ===

try:
    cap = cv2.VideoCapture(0)  # open webcam (device 0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Make sure the camera is connected and accessible.")
    
    log_system_event("START", "Cat activity monitoring system started successfully.")
    print("Starting cat activity monitoring... Press ~ to stop.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame from webcam. Exiting loop.")
            break

        # Run object detection on the frame using YOLO-World
        results = model.predict(source=frame, conf=CONF_THRESHOLD, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        # Apply Non-Maximum Suppression to filter overlapping detections
        detections = detections.with_nms(class_agnostic=False, threshold=NMS_IOU_THRESHOLD)

        # Update object tracker with new detections (to maintain consistent IDs and track across frames)
        tracked_detections = tracker.update_with_detections(detections)

        # Extract detection info for cat and person (if present)
        cat_detection = None
        person_detections = []
        toy_detections = []
        for i, class_id in enumerate(tracked_detections.class_id):
            class_name = class_names[class_id]  # map class index to class name
            if class_name == "cat":
                cat_detection = {
                    "bbox": tracked_detections.xyxy[i],           # bounding box [x1, y1, x2, y2]
                    "conf": float(tracked_detections.confidence[i]),  # confidence score
                    "track_id": tracked_detections.tracker_id[i]      # tracker ID for the cat (if any)
                }
            elif class_name == "person":
                # Collect person bounding boxes for interaction checks
                person_detections.append(tracked_detections.xyxy[i])
            elif class_name in ["sports ball", "teddy bear", "toy"]:
                # Treat these classes as cat toys in the scene
                toy_detections.append(tracked_detections.xyxy[i])
        
        current_activity = None
        current_conf = None  # confidence to log (we will use cat detection confidence for activitys tied to detection)

        now = time.time()

        if cat_detection:
            # Cat is detected in the current frame
            cat_box = cat_detection["bbox"]
            # Ensure box coordinates are integers for calculations
            x1, y1, x2, y2 = map(int, cat_box)
            cat_center = get_center((x1, y1, x2, y2))
            cat_conf = cat_detection["conf"]
            current_conf = cat_conf  # default confidence to log for this activity
            cat_track_id = cat_detection.get("track_id", None)

            # Update last seen time
            last_seen_time = now

            # Determine if cat moved significantly since last frame
            moved = False
            if last_position is not None:
                # Calculate displacement (Euclidean distance or simple threshold)
                dist = np.linalg.norm(cat_center - last_position)
                if dist > 10:  # movement threshold in pixels (tune as needed)
                    moved = True
            else:
                moved = True  # first detection
            if moved:
                last_move_time = now
            # Update last velocity (if we have a previous position and timestamp)
            if last_position is not None and last_seen_time is not None:
                dt = now - last_seen_time if last_seen_time else 0
                if dt > 0:
                    last_velocity = (cat_center - last_position) / dt  # pixels per second
            # Update last position and zone
            last_position = cat_center

            # Determine which zone the cat is in (if any)
            in_bed     = overlaps_zone((x1, y1, x2, y2), ZONE_BED)
            in_fountain= overlaps_zone((x1, y1, x2, y2), ZONE_FOUNTAIN)
            in_food    = overlaps_zone((x1, y1, x2, y2), ZONE_FOOD)
            in_cat_tree= overlaps_zone((x1, y1, x2, y2), ZONE_CAT_TREE)

            at_bathroom= overlaps_zone((x1, y1, x2, y2), (0, BATHROOM_LINE_Y, frame.shape[1], frame.shape[0]))
            at_door    = overlaps_zone((x1, y1, x2, y2), (DOOR_LINE_X, 0, DOOR_LINE_X, frame.shape[0]))
            
            # (If needed, a polygonal or more precise zone check can be used for irregular shapes)

           # Track bathroom crossing
            cat_center_y = cat_center[1]
            bathroom_event = False
            if cat_center_y > BATHROOM_LINE_Y and not cat_below_line:
                bathroom_event = True
            cat_below_line = (cat_center_y > BATHROOM_LINE_Y)

            # Track door crossing
            cat_center_x = cat_center[0]
            door_event = False
            if cat_center_x > DOOR_LINE_X and not cat_right_line:
                door_event = True
            cat_right_line = (cat_center_x > DOOR_LINE_X)

            now_dt = datetime.now()

            def should_log_zone(zone_name):
                global now_dt
                if zone_timers[zone_name] is None:
                    zone_timers[zone_name] = now_dt
                elapsed = (now_dt - zone_timers[zone_name]).total_seconds()
                cooldown_elapsed = (now_dt - zone_cooldowns[zone_name]).total_seconds() if zone_cooldowns[zone_name] else float('inf')
                if elapsed >= zone_durations[zone_name] and cooldown_elapsed >= zone_cooldown_period:
                    zone_cooldowns[zone_name] = now_dt
                    zone_timers[zone_name] = None
                    return True
                return False

            # Determine activity based on zone (if not already set by bathroom and door crossing)
            if current_activity is None:
                if in_fountain and should_log_zone("Fountain"):
                        current_activity = "Cat drinking water"
                elif in_food and should_log_zone("Food"):
                        current_activity = "Eating"
                elif in_cat_tree and should_log_zone("Cat Tree"):
                        current_activity = "climbing/scratching"
                else:
                        # Not in fountain/food/cat_tree zones
                    if in_bed:
                            current_activity = "On Bed"
                    elif bathroom_event:
                            current_activity = "Bathroom"
                    elif door_event:
                             current_activity = "Door"
                    else:
                            current_activity = "Idle"  # Default to "Idle" if not in any specific zone
                    # Check for person-cat interactions
                    # Determine if cat overlaps with any person in this frame
                    overlapping_person = False
                    for p_box in person_detections:
                        # Check overlap between cat box and person box
                        px1, py1, px2, py2 = map(int, p_box)
                        if not (x2 < px1 or px2 < x1 or y2 < py1 or py2 < y1):
                            overlapping_person = True
                            break
                    # If overlapping with person, count interaction event
                    if overlapping_person:
                        if not person_cat_overlap:
                            # This is a new overlap event (cat just touched person)
                            overlap_event_times.append(now)
                            # Remove old events outside the 10-second window
                            overlap_event_times = [t for t in overlap_event_times if now - t <= INTERACTION_WINDOW]
                        person_cat_overlap = True
                    else:
                        person_cat_overlap = False
                    # If there have been 3 or more overlap events within 10 seconds, classify as playing
                    if len(overlap_event_times) >= 3:
                        current_activity = "Playing"  # playing with person
                    else:
                        # If not enough person interactions, check for toys
                        if toy_detections:
                            # If any toy-like object is detected in frame and cat is in play area, consider it playing
                            # (Optionally, could check if cat is near a toy or interacting with it)
                            if current_activity != "Playing":  # don't override if already playing with person
                                current_activity = "Playing"
                        # Otherwise, activity remains "Idle" or other value set above.
                    # Note: If cat was labeled "On Bed" above and not moving for a long time, sleeping logic (below) will handle it.

            # Reset any "At the window" event flag if cat reappeared (meaning it's no longer out of sight).
            window_event_logged = False  # we can use a separate flag to ensure we don't double-log window events
            # (This simple approach just resets the notion when cat is back.)

            last_zone = None
            if in_bed:
                last_zone = "Bed"
            elif in_cat_tree:
                last_zone = "Cat Tree"
            elif in_fountain:
                last_zone = "Fountain"
            elif in_food:
                last_zone = "Food"
            else:
                last_zone = "Play area"

        else:
            # Cat is NOT detected in the current frame
            # Check if it has been seen recently and might have just disappeared
            if last_seen_time is not None:
                time_since_seen = now - last_seen_time
            else:
                time_since_seen = float('inf')
            # If the cat just went out of sight, consider special case "At the window"
            # Condition: last zone was Bed, last known movement was towards left, and cat disappeared.
            if time_since_seen > 2.0 and time_since_seen < SLEEP_TIMEOUT:  # if it's been a couple seconds but not yet 10 min
                if last_zone == "Bed" and last_velocity is not None:
                    if last_velocity[0] < -1:  # negative x velocity (moving leftwards) 
                        if last_activity != "At the window":
                            current_activity = "At the window"
                            current_conf = None  # no direct detection confidence for this inferred activity
                            # Log this "At the window" event below (if conditions met)
            # If the cat is out of sight for longer, sleeping might be concluded below in sleeping check.
            # Also, if cat crossed the bathroom line and vanished, that was logged at crossing time as "Bathroom".

            # We won't update person_cat_overlap or overlap_event_times here since cat is not visible.
            # But we might want to reset interaction events if cat is gone for a while to avoid stale events:
            person_cat_overlap = False

        # Check if the cat is sleeping (no movement or out of sight for >= 10 minutes).
        if last_seen_time is not None:
            if (now - last_seen_time >= SLEEP_TIMEOUT) or (last_move_time is not None and now - last_move_time >= SLEEP_TIMEOUT):
                current_activity = "Sleeping"
                current_conf = None  # sleeping is inferred, not a direct detection
        # If the cat is sleeping, we treat that as a high-priority state (override other activitys).
        if current_activity == "Sleeping":
            pass  # already set above if condition met

        # === Logging to MongoDB ===
        # Log the activity if it is a new activity or an important event.
        if current_activity and current_activity != last_activity:
            # Prepare log document
            log_doc = {
            "timestamp": datetime.now(timezone.utc),
            "activity": current_activity,
            "confidence": current_conf,
            "zone": last_zone,
            "position": {
                "x": float(cat_center[0]),
                "y": float(cat_center[1])
                } if cat_detection else None
            }
            try:
                logs_col.insert_one(log_doc)
            except Exception as e:
                print(f"Warning: Failed to insert log into MongoDB: {e}")
            else:
                print(f"[{log_doc['timestamp']}] Detected activity: {current_activity} (conf={current_conf})")
            last_activity = current_activity

        # (Optional) small delay or frame skip logic can be added here to control processing frame rate.
        # e.g., time.sleep(0.1) to run at ~10 FPS if CPU usage is high.

        # Note: We are not displaying the video frames to a window in this script (headless operation).
        # If needed for debugging, one could use cv2.imshow here and break on key press.
        # === Show the video frame (optional, for visual feedback) ===
# === Visualize tracked detections on the frame ===
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
        
# === Allow user to press '~' to quit ===
        if cv2.waitKey(1) & 0xFF == ord('~'):
            print("Quitting monitoring loop via '~' key...")
            log_system_event("STOP", "Monitoring stopped by user ~")
            break

# === Check for key press to exit (Windows terminal only) ===          ------fot not displaying
    #    if msvcrt.kbhit():
        #    key = msvcrt.getch()
        #    if key == b'~':
         #       print("Quitting monitoring loop via '~' key...")
         #       break

    # end of while loop

except KeyboardInterrupt:
    log_system_event("STOP", "Monitoring stopped by user (KeyboardInterrupt).")
    print("Stopping monitoring due to keyboard interrupt.")

except Exception as e:
    log_system_event("CRASH", f"Unhandled exception occurred: {str(e)}") 
    print(f"System crashed with exception: {e}")
finally:
    # Release resources
    cap.release()
    mongo_client.close()
    # TODO: Implement generation of heatmaps from recorded positions and upload summary analytics to MongoDB.
    # For example, accumulate all cat positions over time to create a heatmap of activity, 
    # or compute daily time spent in each zone and insert those statistics into a separate collection.
    # These features can be implemented in the future for dashboard analytics.
