import os
import json
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from py_clob_client.client import ClobClient, DropNotificationParams

load_dotenv()

# Existing CLOB client setup
host: str = os.getenv('CLOB_HTTP_URL')
key: str = os.getenv('PRIVATE_KEY')
chain_id: int = 137

# MongoDB connection with status check
def check_mongodb_connection():
    try:
        MONGO_URI = os.getenv('MONGODB_URI')
        client = MongoClient(MONGO_URI)
        # The ismaster command is cheap and does not require auth
        client.admin.command('ismaster')
        print("MongoDB connection successful")
        return client
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None

#
def event_initialize():
    gamma_endpoint = os.getenv('GAMMA_ENDPOINT')
    all_events = []
    offset = 0
    limit = 500  # You can adjust this value

    while True:
        # Make request with pagination
        response = requests.get(
            f"{gamma_endpoint}/events",
            params={
                "offset": offset,
                "limit": limit
            }
        )

        current_events = response.json()

        # If no more events, break the loop
        if not current_events:
            break

        all_events.extend(current_events)
        offset += limit
        print(f"Offset: {offset}")

    # Save all events to JSON file
    with open('all_events.json', 'w') as f:
        json.dump(all_events, f, indent=2)

    print(f"Total number of events retrieved: {len(all_events)}")
    print("Events data saved to all_events.json")
    print("Done!")

# Initialize MongoDB client
mongo_client = check_mongodb_connection()
if mongo_client:
    db = mongo_client['polymarket']
    markets_collection = db['events']
