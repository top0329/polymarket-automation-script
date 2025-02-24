import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def main():
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

if __name__ == "__main__":
    main()
