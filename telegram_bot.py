import os
import os.path
import logging
import requests
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, MenuButtonDefault, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.client import ClobClient
from pymongo import MongoClient

logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO
)

logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GAMMA_ENDPOINT = os.getenv('GAMMA_ENDPOINT')
CLOB_API_KEY = os.getenv('CLOB_API_KEY')
CLOB_SECRET = os.getenv('CLOB_SECRET')
CLOB_PASS_PHRASE = os.getenv('CLOB_PASS_PHRASE')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
CLOB_HTTP_URL = os.getenv('CLOB_HTTP_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
CHAIN_ID = int(os.getenv('CHAIN_ID', '1'))

# Initialize MongoDB client
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.polymarket
orders_collection = db.orders

# Initialize CLOB client
clob_client = ClobClient(CLOB_HTTP_URL, key=PRIVATE_KEY, chain_id=CHAIN_ID)

# States for order conversation
SELECTING_OUTCOME, ENTERING_AMOUNT, ENTERING_PRICE, SELECTING_SIDE = range(4)

# Global variables
subscribed_chats = set()
previous_markets = None  # Store previous request's market data
user_order_data = {}  # Store temporary order data

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create keyboard layout
    keyboard = [
        [KeyboardButton("📊 Subscribe"), KeyboardButton("❌ Unsubscribe")],
        [KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome to Polymarket Monitor Bot! 🤖\n\n"
             "Use the menu buttons below or these commands:\n"
             "/subscribe - Get new market alerts\n"
             "/unsubscribe - Stop market alerts\n"
             "/help - Show this help message",
        reply_markup=reply_markup
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribed_chats:
        subscribed_chats.add(chat_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text="You've successfully subscribed to new market alerts!"
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="You're already subscribed to market alerts!"
        )

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribed_chats:
        subscribed_chats.remove(chat_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text="You've been unsubscribed from market alerts."
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="You weren't subscribed to market alerts."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📚 *Available Commands:*\n\n"
             "• /start - Show the main menu\n"
             "• /subscribe - Get new market alerts\n"
             "• /unsubscribe - Stop market alerts\n"
             "• /help - Show this help message\n\n"
             "ℹ️ This bot monitors Polymarket for new markets and sends alerts when they are created.",
        parse_mode='Markdown'
    )

def format_market_message(market):
    message = f"🆕 New Market Alert!\n\n"
    message += f"📊 Question: {market['question']}\n"
    message += f"🔗 Market Link: https://polymarket.com/market/{market['slug']}\n"

    # Add description if available (truncated if too long)
    if 'description' in market:
        desc = market['description']
        if len(desc) > 200:
            desc = desc[:197] + "..."
        message += f"📝 Description: {desc}\n"

    # Add timing information
    if 'endDate' in market:
        end_date = datetime.fromisoformat(market['endDate'].replace('Z', '+00:00'))
        message += f"⏰ End Date: {end_date.strftime('%Y-%m-%d %H:%M')} UTC\n"

    # Add current market prices if available
    if 'outcomes' in market and 'outcomePrices' in market:
        outcomes = json.loads(market['outcomes'])
        prices = json.loads(market['outcomePrices'])
        message += "\n💰 Current Prices:\n"
        for outcome, price in zip(outcomes, prices):
            message += f"• {outcome}: ${float(price):.2f}\n"

    return message

def create_order_buttons(market_slug, market_id):
    keyboard = [
        [
            InlineKeyboardButton("📈 Market Order", callback_data=f"market_order:{market_id}"),
            InlineKeyboardButton("📊 Limit Order", callback_data=f"limit_order:{market_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_market_alert(context: ContextTypes.DEFAULT_TYPE, market):
    for chat_id in subscribed_chats:
        try:
            message = format_market_message(market)
            # Create order buttons with market ID
            reply_markup = create_order_buttons(market['slug'], market['id'])

            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending alert to chat {chat_id}: {e}")

async def check_new_markets(context: ContextTypes.DEFAULT_TYPE):
    try:
        global previous_markets

        # Query parameters for active, non-archived, non-closed markets
        params = {
            "limit": 50,
            "active": "true",
            "archived": "false",
            "closed": "false",
            "order": "startDate",
            "ascending": "false",
            "offset": 0
        }

        response = requests.get(os.path.join(GAMMA_ENDPOINT, "markets"), params=params)
        response.raise_for_status()
        current_markets = response.json()

        if not current_markets:
            return

        # If this is the first request, store the data and return
        if previous_markets is None:
            previous_markets = {market['id']: market for market in current_markets}
            return

        # Convert current markets to dictionary for easier lookup
        current_markets_dict = {market['id']: market for market in current_markets}

        # Find new markets (present in current but not in previous)
        new_market_ids = set(current_markets_dict.keys()) - set(previous_markets.keys())
        print(f"New market IDs: {new_market_ids}")

        if new_market_ids:
            now = datetime.now(timezone.utc)
            # Check each new market
            for market_id in new_market_ids:
                market = current_markets_dict[market_id]
                start_date = datetime.fromisoformat(market['startDate'].replace('Z', '+00:00'))

                # Only alert for markets started in the last 2 minutes
                if (now - start_date).total_seconds() <= 120:  # 2 minutes
                    await send_market_alert(context, market)

        # Update previous markets for next comparison
        previous_markets = current_markets_dict

    except Exception as e:
        logger.error(f"Error checking new markets: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 Subscribe":
        await subscribe(update, context)
    elif text == "❌ Unsubscribe":
        await unsubscribe(update, context)
    elif text == "ℹ️ Help":
        await help_command(update, context)
    else:
        await unknown(update, context)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Sorry, I didn't understand that command."
    )

async def setup_commands(application):
    """Setup bot commands in the menu"""
    commands = [
        BotCommand("start", "Start the bot and show menu"),
        BotCommand("subscribe", "Subscribe to market alerts"),
        BotCommand("unsubscribe", "Unsubscribe from alerts"),
        BotCommand("help", "Show help information")
    ]

    # Set commands in the menu
    await application.bot.set_my_commands(commands)

    # Set the menu button to default (three dots menu)
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonDefault()
    )

async def handle_market_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle market order button click"""
    query = update.callback_query
    market_id = query.data.split(':')[1]

    # Store market ID in user data
    context.user_data['market_id'] = market_id
    context.user_data['order_type'] = 'market'

    # Get market outcomes
    try:
        response = requests.get(f"{GAMMA_ENDPOINT}/markets/{market_id}")
        market_data = response.json()
        outcomes = json.loads(market_data['outcomes'])
        token_ids = json.loads(market_data.get('tokenIds', '[]'))

        # Store token IDs mapped to outcomes
        context.user_data['token_ids'] = dict(zip(outcomes, token_ids))

        # Create outcome selection buttons
        keyboard = [[InlineKeyboardButton(outcome, callback_data=f"outcome:{outcome}")]
                   for outcome in outcomes]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text="Select the outcome you want to trade:",
            reply_markup=reply_markup
        )
        return SELECTING_OUTCOME

    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        await query.answer("Error fetching market data. Please try again.")
        return ConversationHandler.END

async def handle_limit_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle limit order button click"""
    query = update.callback_query
    market_id = query.data.split(':')[1]

    # Store market ID in user data
    context.user_data['market_id'] = market_id
    context.user_data['order_type'] = 'limit'

    # Get market outcomes
    try:
        response = requests.get(f"{GAMMA_ENDPOINT}/markets/{market_id}")
        market_data = response.json()
        outcomes = json.loads(market_data['outcomes'])
        token_ids = json.loads(market_data.get('tokenIds', '[]'))

        # Store token IDs mapped to outcomes
        context.user_data['token_ids'] = dict(zip(outcomes, token_ids))

        # Create outcome selection buttons
        keyboard = [[InlineKeyboardButton(outcome, callback_data=f"outcome:{outcome}")]
                   for outcome in outcomes]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text="Select the outcome you want to trade:",
            reply_markup=reply_markup
        )
        return SELECTING_OUTCOME

    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        await query.answer("Error fetching market data. Please try again.")
        return ConversationHandler.END

async def handle_outcome_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle outcome selection"""
    query = update.callback_query
    outcome = query.data.split(':')[1]
    context.user_data['selected_outcome'] = outcome
    context.user_data['token_id'] = context.user_data['token_ids'][outcome]

    # Create side selection buttons
    keyboard = [
        [
            InlineKeyboardButton("Buy", callback_data="side:buy"),
            InlineKeyboardButton("Sell", callback_data="side:sell")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"Selected outcome: {outcome}\nDo you want to buy or sell?",
        reply_markup=reply_markup
    )
    return SELECTING_SIDE

async def handle_side_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle side selection"""
    query = update.callback_query
    side = query.data.split(':')[1]
    context.user_data['side'] = BUY if side.lower() == 'buy' else SELL

    await query.edit_message_text(
        text=f"Enter the amount you want to trade (in {'USD' if context.user_data['side'] == BUY else 'shares'}):"
    )
    return ENTERING_AMOUNT

async def handle_amount_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle amount entry"""
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount

        if context.user_data['order_type'] == 'market':
            # Place market order
            await place_order(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Enter the limit price (between 0 and 1):"
            )
            return ENTERING_PRICE

    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number for the amount."
        )
        return ENTERING_AMOUNT

async def handle_price_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price entry for limit orders"""
    try:
        price = float(update.message.text)
        if 0 <= price <= 1:
            context.user_data['price'] = price
            await place_order(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Price must be between 0 and 1. Please try again:"
            )
            return ENTERING_PRICE

    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number for the price."
        )
        return ENTERING_PRICE

async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Place the actual order using Polymarket CLOB API"""
    try:
        token_id = context.user_data['token_id']
        amount = context.user_data['amount']
        side = context.user_data['side']

        order_data = {
            "user_id": update.effective_user.id,
            "market_id": context.user_data['market_id'],
            "outcome": context.user_data['selected_outcome'],
            "token_id": token_id,
            "amount": amount,
            "side": "BUY" if side == BUY else "SELL",
            "type": context.user_data['order_type'],
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }

        if context.user_data['order_type'] == 'limit':
            price = context.user_data['price']
            order_data['price'] = price

            # Create and sign a limit order
            order_args = OrderArgs(
                price=price,
                size=amount,
                side=side,
                token_id=token_id
            )
            signed_order = clob_client.create_order(order_args)
            resp = clob_client.post_order(signed_order, OrderType.GTC)
        else:
            # Create and sign a market order
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side
            )
            signed_order = clob_client.create_market_order(order_args)
            resp = clob_client.post_order(signed_order, OrderType.FOK)

        # Update order data with response
        order_data.update({
            "order_id": resp.get("orderID"),
            "transaction_hashes": resp.get("transactionsHashes", []),
            "status": "success" if resp.get("success") else "failed",
            "error_message": resp.get("errorMsg", "")
        })

        # Save order to MongoDB
        orders_collection.insert_one(order_data)

        # Send response to user
        if resp.get("success"):
            message = (
                f"Order placed successfully!\n"
                f"Type: {order_data['type'].title()} Order\n"
                f"Side: {order_data['side']}\n"
                f"Outcome: {order_data['outcome']}\n"
                f"Amount: {'$' if order_data['side'] == 'BUY' else ''}{order_data['amount']}"
            )
            if order_data['type'] == 'limit':
                message += f"\nPrice: ${order_data['price']}"

            await update.message.reply_text(message)
        else:
            error_msg = resp.get("errorMsg", "Unknown error")
            await update.message.reply_text(
                f"Failed to place order: {error_msg}\nPlease try again later."
            )

    except Exception as e:
        logger.error(f"Error placing order: {e}")
        await update.message.reply_text(
            "An error occurred while placing your order. Please try again later."
        )

    # Clear user data
    context.user_data.clear()

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Setup commands in menu
    application.job_queue.run_once(setup_commands, when=1, data=application)

    # Add job queue to check for new markets every minute
    job_queue = application.job_queue
    job_queue.run_repeating(check_new_markets, interval=10, first=10)

    # Create conversation handler for orders
    order_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_market_order, pattern=r'^market_order:'),
            CallbackQueryHandler(handle_limit_order, pattern=r'^limit_order:')
        ],
        states={
            SELECTING_OUTCOME: [CallbackQueryHandler(handle_outcome_selection, pattern=r'^outcome:')],
            SELECTING_SIDE: [CallbackQueryHandler(handle_side_selection, pattern=r'^side:')],
            ENTERING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_entry)],
            ENTERING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_entry)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )

    # Add handlers
    start_handler = CommandHandler('start', start)
    subscribe_handler = CommandHandler('subscribe', subscribe)
    unsubscribe_handler = CommandHandler('unsubscribe', unsubscribe)
    help_handler = CommandHandler('help', help_command)
    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)

    application.add_handler(order_handler)  # Add this before other handlers
    application.add_handler(start_handler)
    application.add_handler(subscribe_handler)
    application.add_handler(unsubscribe_handler)
    application.add_handler(help_handler)
    application.add_handler(message_handler)
    application.add_handler(unknown_handler)

    application.run_polling()