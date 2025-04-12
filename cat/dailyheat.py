import matplotlib.pyplot as plt
import numpy as np
from pymongo import MongoClient
from datetime import datetime
import matplotlib.dates as mdates

# === MongoDB Setup ===
mongo_client = MongoClient(
    "mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion"
)
db = mongo_client["cat_activity_db"]
logs_col = db["activity_logs"]

# === Date Input ===
# Format: MM/DD/YY H:MM AM/PM
start_str = "4/5/25 1:00 PM"
end_str = "4/5/25 11:30 PM"

start_time = datetime.strptime(start_str, "%m/%d/%y %I:%M %p")
end_time = datetime.strptime(end_str, "%m/%d/%y %I:%M %p")

print(f"Generating heatmap from {start_time} to {end_time}")

# === Query MongoDB ===
logs = logs_col.find({
    "timestamp": {
        "$gte": start_time,
        "$lte": end_time
    }
})

# === Extract Coordinates ===
positions = [(log["position"]["x"], log["position"]["y"]) for log in logs if "position" in log]
if not positions:
    print("No activity logs found in the given time range.")
    exit()

x_coords, y_coords = zip(*positions)

# === Generate Heatmap ===
heatmap, xedges, yedges = np.histogram2d(x_coords, y_coords, bins=(64, 48), range=[[0, 640], [0, 480]])
extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]

plt.imshow(heatmap.T, extent=extent, origin='lower', cmap='hot')
plt.title(f"Cat Activity Heatmap\n{start_str} to {end_str}")
plt.xlabel("X Position")
plt.ylabel("Y Position")
plt.colorbar(label="Activity Density")
plt.grid(False)
plt.tight_layout()
plt.show()