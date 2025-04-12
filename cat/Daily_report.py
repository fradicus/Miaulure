import os
from datetime import datetime, timedelta
from pymongo import MongoClient
import openai
import requests

# === CONFIGURATION ===
USE_OPENAI = False  # 🔄 Set to True to use OpenAI, False to use local Mistral via Ollama

# MongoDB Setup
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cat_activity_db"]
logs_col = db["activity_logs"]
reports_col = db["daily_reports"]

# OpenAI Setup (if using)
openai.api_key = os.getenv("OPENAI_API_KEY")  # Or paste it here: openai.api_key = "sk-..."
OPENAI_MODEL = "gpt-3.5-turbo"

# Ollama Local Setup
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"  # Must be pulled already with `ollama pull mistral`

# === Generate Daily Summary ===
def fetch_daily_logs():
    today = datetime.now().date()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)
    return list(logs_col.find({"timestamp": {"$gte": start, "$lt": end}}))

def format_logs(logs):
    formatted = []
    for log in logs:
        time_str = log['timestamp'].astimezone().strftime("%I:%M %p")
        activity = log.get("activity", "Unknown")
        zone = log.get("zone", "Unknown")
        formatted.append(f"- At {time_str}, cat was '{activity}' in zone: {zone}.")
    return "\n".join(formatted)

def call_openai(formatted_logs):
    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a cat activity report assistant."},
            {"role": "user", "content": f"Summarize this daily activity:\n{formatted_logs}"}
        ]
    )
    return response["choices"][0]["message"]["content"]

def call_mistral(formatted_logs):
    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": f"Summarize this daily cat activity:\n{formatted_logs}",
        "stream": False
    })
    return response.json()["response"]

# === Main Execution ===
if __name__ == "__main__":
    logs = fetch_daily_logs()
    if not logs:
        print("No activity logs found for today.")
        exit()

    formatted_logs = format_logs(logs)
    print("Formatted logs for LLM:\n", formatted_logs)

    if USE_OPENAI:
        print("Using OpenAI...")
        summary = call_openai(formatted_logs)
    else:
        print("Using local Mistral (Ollama)...")
        summary = call_mistral(formatted_logs)

    print("\nGenerated Summary:\n", summary)

    # Save report
    report_doc = {
        "timestamp": datetime.now(),
        "summary": summary,
        "model_used": "OpenAI GPT" if USE_OPENAI else "Mistral via Ollama"
    }
    reports_col.insert_one(report_doc)
    print("Report saved to MongoDB.")
