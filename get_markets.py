import os
import json

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
from py_clob_client.constants import POLYGON

load_dotenv()


def main():
    host = os.getenv('CLOB_HTTP_URL')
    key = os.getenv("PRIVATE_KEY")
    creds = ApiCreds(
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASS_PHRASE"),
    )
    chain_id = POLYGON
    client = ClobClient(host, key=key, chain_id=chain_id, creds=creds)

    all_markets = []
    next_cursor = ""

    while True:
        response = client.get_markets(next_cursor=next_cursor)
        parsed_response = json.loads(json.dumps(response))

        # Add current page's data to our collection
        all_markets.extend(parsed_response["data"])

        # Get next_cursor from response
        next_cursor = parsed_response["next_cursor"]
        print(f"Next cursor: {next_cursor}")

        # Break if we've reached the end (LTE= means end)
        if next_cursor == "LTE=":
            break

    # Save to JSON file with nice formatting
    with open('all_markets.json', 'w') as f:
        json.dump(all_markets, f, indent=2)

    print(f"Total number of markets retrieved: {len(all_markets)}")
    print("Markets data saved to all_markets.json")
    print("Done!")


main()
