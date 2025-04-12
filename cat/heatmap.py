import cv2
import numpy as np
from pymongo import MongoClient
from datetime import datetime

# === MongoDB Setup ===
mongo_client = MongoClient("mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion")
db = mongo_client["cat_activity_db"]
activity_logs = db["activity_logs"]
zones_col = db["zones"]
heatmaps_col = db["heatmaps"]

# === Load Room Image ===
background_img = cv2.imread("Zoning.JPG")
if background_img is None:
    raise FileNotFoundError("Background image 'Zoning.JPG' not found.")
height, width = background_img.shape[:2]

# === Create Blank Heatmap ===
heatmap = np.zeros((height, width), dtype=np.float32)

# === Plot all logged positions into heatmap matrix ===
for doc in activity_logs.find():
    if "position" in doc and isinstance(doc["position"], dict):
        x = int(doc["position"].get("x", -1))
        y = int(doc["position"].get("y", -1))
        if 0 <= x < width and 0 <= y < height:
            cv2.circle(heatmap, (x, y), radius=10, color=1, thickness=-1)

# === Normalize and Convert to Color Map ===
heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX)
heatmap_colored = cv2.applyColorMap(heatmap_normalized.astype(np.uint8), cv2.COLORMAP_WINTER)

# === Overlay Heatmap on Room Image ===
overlayed = cv2.addWeighted(background_img, 0.5, heatmap_colored, 0.4, 0)

# === Draw Zones ===
for zone in zones_col.find():
    coords = zone.get("coords", [])
    if len(coords) == 4:
        x1, y1, x2, y2 = coords
        color = (255, 0, 255)  # Magenta for zones
        cv2.rectangle(overlayed, (x1, y1), (x2, y2), color, 2)
        cv2.putText(overlayed, zone.get("name", ""), (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

# === Save and Upload ===
cv2.imwrite("heatmap_overlay.png", overlayed)
_, buffer = cv2.imencode(".png", overlayed)
heatmaps_col.insert_one({
    "timestamp": datetime.utcnow(),
    "image": buffer.tobytes(),
    "note": "Room heatmap with zones overlay"
})

# === DISPLAY WINDOW FOR TESTING ===
cv2.namedWindow("Cat Heatmap", cv2.WINDOW_NORMAL)
cv2.imshow("Cat Heatmap", overlayed)
print("📸 Press any key to close the heatmap window...")
cv2.waitKey(0)
cv2.destroyAllWindows()
