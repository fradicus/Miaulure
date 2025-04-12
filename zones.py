from pymongo import MongoClient

client = MongoClient("mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion")
db = client["cat_activity_db"]
zones_col = db["zones"]

# Define or update zones
zones = [
    {"name": "Bed", "coords": (0, 0, 180, 130)},
    {"name": "Fountain", "coords": (328, 160, 375, 192) },
    {"name": "Food", "coords": (445, 400, 580, 465)},
    {"name": "Door", "coords": (638,0,638,0)},
    {"name": "Cat Tree", "coords": (460, 35, 630, 235)},
    {"name": "Bathroom", "coords": (0, 475, 0, 475)},
    
]

# Clear old zones and insert new ones
zones_col.delete_many({})
zones_col.insert_many(zones)

print("✅ Zone data updated in MongoDB.")
