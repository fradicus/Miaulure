import matplotlib.pyplot as plt
import numpy as np
from pymongo import MongoClient
from datetime import datetime
import matplotlib.dates as mdates
from dailyheat import generate_heatmap

def main():
    # MongoDB Setup
    mongo_client = MongoClient(
        "mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion"
    )
    db = mongo_client["cat_activity_db"]
    logs_col = db["activity_logs"]

    # Date Input
    start_str = input("Enter start date (MM/DD/YY H:MM AM/PM): ")
    end_str = input("Enter end date (MM/DD/YY H:MM AM/PM): ")

    start_time = datetime.strptime(start_str, "%m/%d/%y %I:%M %p")
    end_time = datetime.strptime(end_str, "%m/%d/%y %I:%M %p")

    print(f"Generating heatmap from {start_time} to {end_time}")

    # Generate Heatmap
    generate_heatmap(logs_col, start_time, end_time)

if __name__ == "__main__":
    main()