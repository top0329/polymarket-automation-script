import asyncio
import json
import ssl
import websockets
import websockets.exceptions
import zlib
import os
import logging
from logger import logger
from dotenv import load_dotenv
import os

load_dotenv()
# Discord settings
MONITOR_USER_TOKEN =os.getenv("MONITOR_USER_TOKEN")

DISCORD_WS_URL = "wss://gateway.discord.gg/?v=6&encoding=json"

if not os.path.exists('logs'):
    os.makedirs('logs')

async def send_payload(ws, payload):
    data = json.dumps(payload)
    if len(data.encode()) > 1048000:
        logging.warning("Payload too large, truncating...")
        payload['d'] = {k: v[:1000] if isinstance(v, str) else v
                       for k, v in payload['d'].items()}
        data = json.dumps(payload)
    await ws.send(data)

async def heartbeat(ws, interval, last_sequence):
    while True:
        await asyncio.sleep(interval)
        payload = {
            "op": 1,
            "d": last_sequence
        }
        await send_payload(ws, payload)
        logging.info("Heartbeat packet sent.")

async def identify(ws):
    identify_payload = {
        "op": 2,
        "d": {
            "token": MONITOR_USER_TOKEN,
            "properties": {
                "$os": "windows",
                "$browser": "chrome",
                "$device": "pc"
            },
            "compress": True,
            "large_threshold": 50,
            "intents": 32767
        }
    }
    await send_payload(ws, identify_payload)
    logging.info("Identification sent.")

async def on_message(ws):
    last_sequence = None
    while True:
        try:
            message = await ws.recv()
            if isinstance(message, bytes):
                message = zlib.decompress(message).decode('utf-8')
            event = json.loads(message)
            # logger.info("Received event: %s", event)
            op_code = event.get('op', None)

            if op_code == 10:
                interval = event['d']['heartbeat_interval'] / 1000
                asyncio.create_task(heartbeat(ws, interval, last_sequence))

            elif op_code == 0:
                last_sequence = event.get('s', None)
                event_type = event.get('t')

                if event_type == 'MESSAGE_CREATE':
                    channel_id = event['d']['channel_id']
                    if channel_id == "1343921888459755543": # the channel id of new-markets
                        # message content
                        # content = event['d']['content']
                        # print(content)

                        content = event['d']['content']
                        author = event['d']['author']
                        print(f"Author: {author['username']}#{author['discriminator']}")
                        print(f"Content: {content}")
                        logger.info(f"Message received from {author['username']}: {content}")

            elif op_code == 9:
                logging.info(f"Invalid session. Starting a new session...")
                await identify(ws)

        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"WebSocket connection closed: {str(e)}")
            raise  # Let main() handle reconnection

        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {str(e)}")
            consecutive_errors += 1
            await asyncio.sleep(min(1 * consecutive_errors, 30))  # Exponential backoff up to 30 seconds

        except zlib.error as e:
            logging.error(f"Decompression error: {str(e)}")
            consecutive_errors += 1
            await asyncio.sleep(min(1 * consecutive_errors, 30))

        except Exception as e:
            logging.error(f"Error processing message: {str(e)}", exc_info=True)
            consecutive_errors += 1
            await asyncio.sleep(min(1 * consecutive_errors, 30))

            # If too many consecutive errors occur, restart the connection
            if consecutive_errors >= 10:
                logging.error("Too many consecutive errors, forcing reconnection...")
                raise websockets.exceptions.ConnectionClosed(
                    1006, "Too many consecutive errors"
                )

async def main():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    while True:
        try:
            async with websockets.connect(DISCORD_WS_URL, ssl=ssl_context) as ws:
                await identify(ws)
                await on_message(ws)
        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"WebSocket connection closed unexpectedly:. Reconnecting...")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            logging.error(f"Unexpected error: . Reconnecting...")
            await asyncio.sleep(5)
            continue

if __name__ == "__main__":
    asyncio.run(main())