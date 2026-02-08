# 🧭 Polymarket Automation Script

Trade and monitor Polymarket prediction markets from Telegram—place orders, browse events, and get alerts without leaving the app. Your automated command center for crypto prediction markets.

## 📚 Table of Contents
- [About](#about)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Screenshots](#screenshots)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)

<a id="about"></a>
## 🧩 About

This project was built to remove the friction of constantly switching between Polymarket and chat apps: you can browse events, place and manage orders, and receive market alerts directly in Telegram (and optionally Discord). The goal is to turn your messaging app into a full-featured Polymarket trading and monitoring hub, backed by the Polymarket CLOB API, Gamma API, and MongoDB for persistence.

<a id="features"></a>
## ✨ Features

- **Telegram trading** – Place market and limit orders, browse events and markets, and manage positions from inline keyboards and commands.
- **New market alerts** – Subscribe once and get notified in Telegram when new Polymarket events or markets go live.
- **Liquidity alerts** – Subscribe to specific markets and receive alerts when liquidity crosses your chosen threshold.
- **Order management** – View open and market orders and cancel orders directly from the bot.
- **Discord support** – Optional Discord integration for monitoring and alerts alongside Telegram.
- **Persistence** – MongoDB stores subscriptions and user preferences so alerts and settings survive restarts.

<a id="tech-stack"></a>
## 🧠 Tech Stack

- **Language:** Python
- **Bot & messaging:** python-telegram-bot, discord.py
- **Polymarket & blockchain:** py_clob_client, eth-account, py_order_utils
- **Database:** MongoDB (pymongo)
- **APIs:** Polymarket CLOB API, Gamma API
- **Scheduling & async:** APScheduler, aiohttp, websockets
- **Config & tooling:** python-dotenv, pydantic, requests

<a id="installation"></a>
## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/top0329/polymarket-automation-script.git
cd polymarket-automation-script

# Create and activate a virtual environment (recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

<a id="usage"></a>
## 🚀 Usage

After installing dependencies and configuring your `.env` (see [Configuration](#configuration)), run the Telegram bot:

```bash
python telegram_bot.py
```

The bot will start polling; interact with it in Telegram via [@polymarket_auto_bot](https://t.me/@polymarket_auto_bot). For Discord monitoring/alerts, run `discord_bot.py` or `polymarket_alerts.py` as needed.

<a id="configuration"></a>
## 🧾 Configuration

Create a `.env` file in the project root with the following variables:

| Variable                   | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`       | Telegram Bot API token from [@BotFather](https://t.me/BotFather) |
| `GAMMA_ENDPOINT`           | Polymarket Gamma API base URL                                    |
| `CLOB_HTTP_URL`            | Polymarket CLOB API URL                                          |
| `CLOB_API_KEY`             | CLOB API key (from `generate-api-key.py` or Polymarket)          |
| `CLOB_SECRET`              | CLOB API secret                                                  |
| `CLOB_PASS_PHRASE`         | CLOB API passphrase                                              |
| `PRIVATE_KEY`              | Wallet private key (for signing orders)                          |
| `POLYMARKET_PROXY_ADDRESS` | Polymarket proxy wallet address (funder)                         |
| `MONGODB_URI`              | MongoDB connection string (default: `mongodb://localhost:27017`) |
| `CHAIN_ID`                 | Chain ID (default: `137` for Polygon)                            |
| `MONITOR_USER_TOKEN`       | Discord user token (optional; for Discord alerts)                |

<a id="screenshots"></a>
## 🖼 Screenshots

<img width="476" height="623" alt="1" src="https://github.com/user-attachments/assets/ba34d0c7-53fe-43f6-8173-9a944353c56a" />
<img width="499" height="281" alt="2" src="https://github.com/user-attachments/assets/00d0c8f1-422a-47b9-a50e-fbd3d3bc074a" />
<img width="504" height="433" alt="3" src="https://github.com/user-attachments/assets/3578d6af-488f-4258-a4a5-3335c406c192" />

<a id="contact"></a>
## 📬 Contact

- **Email**: top000329@gmail.com
- **GitHub**: @top0329

<a id="acknowledgements"></a>
## 🌟 Acknowledgements

- [Polymarket](https://polymarket.com) for the prediction market platform and [CLOB](https://docs.polymarket.com) / [Gamma](https://gamma-api.polymarket.com) APIs.
- [py_clob_client](https://github.com/Polymarket/py-clob-client) and related Polymarket Python tooling for order placement and market data.
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) and [discord.py](https://github.com/Rapptz/discord.py) for the bot frameworks.
