from flask import Flask, request, jsonify
from pymongo import MongoClient
import bcrypt
from datetime import datetime, timezone

app = Flask(__name__)

mongo_client = MongoClient(
    "mongodb+srv://meow:coZONdy8XCjizac8@hyperion.cgnxcb1.mongodb.net/?retryWrites=true&w=majority&appName=Hyperion",
    authMechanism='SCRAM-SHA-256'
)

db = mongo_client["cat_activity_db"]
users_col = db["users"]

# Registration endpoint
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data['username']
    password = data['password']
    role = data.get('role', 'user')  # default role: user

    # Check if user exists
    if users_col.find_one({"username": username}):
        return jsonify({"error": "User already exists"}), 409

    # Hash the password
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert into MongoDB
    users_col.insert_one({
        "username": username,
        "password_hash": hashed_pw,
        "role": role,
        "created_at": datetime.now(timezone.utc)
    })

    return jsonify({"message": "Registration successful"}), 201

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data['username']
    password = data['password']

    user_doc = users_col.find_one({"username": username})

    if user_doc and bcrypt.checkpw(password.encode('utf-8'), user_doc["password_hash"]):
        return jsonify({"message": "Login successful", "role": user_doc["role"]}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401

if __name__ == '__main__':
    app.run(debug=True, port=5000)
