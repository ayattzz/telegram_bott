import asyncio
import logging
import os
from datetime import datetime, timedelta, date
import re
import smtplib
from email.mime.text import MIMEText

import uvicorn
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from deep_translator import GoogleTranslator
from telegram import Update, Bot, InputFile
from telegram.error import TelegramError, BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, \
    CallbackContext



logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


ADMINS = os.getenv("ADMINS")
group_id = os.getenv("GROUP_ID")
FROM_EMAIL = os.getenv("FROM_EMAIL")
FROM_PASSWORD = os.getenv("FROM_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

EMAIL, PHONE, WAITING_FOR_RECEIPT = range(3)


user_languages = {}


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data='en')],
        [InlineKeyboardButton("🇫🇷 Français", callback_data='fr')],
        [InlineKeyboardButton("🇩🇿 العربية", callback_data='ar')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please choose a language:", reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data in ['en', 'fr', 'ar']:
        user_languages[user_id] = data
        await query.edit_message_text(text=f"Language set to {data}.")
    elif data == 'pay':
        # Call the pay function
        await pay(update, context)
    elif data == 'send':
        # Call the send function
        await send(update, context)
    else:
        await query.edit_message_text(text="Language not supported.")


def translate_text(text, dest_lang):
    return GoogleTranslator(target=dest_lang).translate(text)
def db_connect():
    conn = sqlite3.connect('users.db')
    return conn


def validate_email(email):
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(regex, email)


def validate_phone(phone):
    regex = r'^0\d{9}$'
    return re.match(regex, phone)


# Function to send email

def send_email(to_email, subject, body):
    from_email = FROM_EMAIL
    from_password = FROM_PASSWORD
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


from apscheduler.schedulers.background import BackgroundScheduler


scheduler = BackgroundScheduler()

import sqlite3
from datetime import datetime, timedelta


# Function to send trial reminders
async def send_trial_reminders(bot):
    logger.info("Starting send_trial_reminders function.")
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_date = datetime.now()
    logger.info(f"Checking for upcoming free trial expirations. Current date: {current_date}")
    reminder_date = current_date + timedelta(days=2)
    reminder_date_str = reminder_date.date().isoformat()
    c.execute("SELECT user_id, email, trial_end FROM users WHERE trial_end IS NOT NULL")
    rows = c.fetchall()

    for user_id, email, trial_end in rows:
        try:
            trial_end_date = datetime.fromisoformat(trial_end).date()
            if trial_end_date == reminder_date.date():
                # Default message in Arabic
                message = (
                    "تجربتك المجانية راح تنتهي بعد يومين.\n\n"
                    "اذا ترغب في البقاء معنا في غرفة الاحتراف.\n\n"
                    "قم بلاشتراك في الزر Menu التحت.\n\n"
                )
                # Check user language preference
                user_lang = user_languages.get(user_id, 'ar')
                if user_lang != 'ar':
                    translated_message = translate_text(message, user_lang)
                else:
                    translated_message = message
                await bot.send_message(chat_id=user_id, text=translated_message)
                logger.info(f"Sent trial reminder to user_id: {user_id}. Trial end date: {trial_end_date}.")
        except ValueError as e:
            logger.error(f"Date parsing error for user_id {user_id}: {e}")

    conn.close()
    logger.info("Finished send_trial_reminders function.")
# Function to send subscription reminders
async def send_subscription_reminders(bot):
    logger.info("Starting send_subscription_reminders function.")
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_date = datetime.now()
    logger.info(f"Checking for subscription reminders. Current date: {current_date}")
    c.execute("SELECT user_id, email, subscription_end FROM users WHERE subscribed = 1")
    rows = c.fetchall()

    for user_id, email, subscription_end in rows:
        try:
            subscription_end_date = datetime.fromisoformat(subscription_end)
            subscription_start_date = subscription_end_date - timedelta(days=30)
            reminder_date = subscription_start_date + timedelta(days=25)
            if reminder_date.date() == current_date.date():
                message = "Reminder: You are on the 25th day of your subscription. Thank you for being with us!"
                # Translate the message based on the user's preferred language
                translated_message = translate_text(message, user_languages.get(user_id, 'en'))
                await bot.send_message(chat_id=user_id, text=translated_message)
                logger.info(f"Sent subscription reminder to user_id: {user_id}. Subscription end date: {subscription_end_date}.")
        except ValueError as e:
            logger.error(f"Date parsing error for user_id {user_id}: {e}")

    conn.close()
    logger.info("Finished send_subscription_reminders function.")


async def ban_user_from_group(bot: Bot, user_id: int, group_id: int):
    try:
        await bot.ban_chat_member(chat_id=group_id, user_id=user_id)
        logger.info(f"User {user_id} successfully banned from group {group_id}.")
    except BadRequest as e:
        logger.error(f"Failed to ban user {user_id} from group {group_id}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


async def check_and_ban_unsubscribed_users(bot: Bot, group_id: int):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id, trial_end, subscribed FROM users")
    users = c.fetchall()
    conn.close()

    logger.info(f"Fetched users from database: {users}")

    current_date = datetime.now()

    for user_id, trial_end, subscribed in users:
        logger.info(f"Processing user_id: {user_id}, trial_end: {trial_end}, subscribed: {subscribed}")

        # Handle cases where trial_end is None
        if trial_end is None:
            # Consider banning the user if they are not subscribed
            if not subscribed:
                logger.info(f"Banning user {user_id} from group {group_id}.")
                await ban_user_from_group(bot, user_id, group_id)
            else:
                logger.info(f"User {user_id} is subscribed. No action needed.")
            continue

        try:
            trial_end_date = datetime.fromisoformat(trial_end)
            logger.info(f"User {user_id}: Trial end date {trial_end_date}, Current date {current_date}")

            # If the trial has expired and the user is not subscribed, ban them
            if trial_end_date < current_date and not subscribed:
                logger.info(f"Banning user {user_id} from group {group_id} as their trial has expired and they are not subscribed.")
                await ban_user_from_group(bot, user_id, group_id)
            else:
                logger.info(f"Trial still valid for user {user_id}. No action needed.")
        except ValueError as e:
            logger.error(f"Date parsing error for user_id {user_id}: {e}")


invite_links = {}

async def generate_invite_link(bot: Bot, group_id: int) -> str:
    try:
        invite_link = await bot.export_chat_invite_link(chat_id=group_id)
        invite_links[group_id] = invite_link  # Store the invite link
        return invite_link
    except Exception as e:
        logger.error(f"Failed to generate invite link for group {group_id}: {e}")
        return None

async def check_invite_link_validity(bot: Bot, invite_link: str) -> bool:
    try:
        chat = await bot.get_chat(chat_id=invite_link)
        return chat is not None
    except Exception as e:
        logger.info(f"Invite link {invite_link} is not valid: {e}")
        return False

async def unban_user_from_group(bot: Bot, user_id: int, group_id: int):
    try:
        await bot.unban_chat_member(chat_id=group_id, user_id=user_id)
        logger.info(f"User {user_id} successfully unbanned from group {group_id}.")
    except BadRequest as e:
        logger.error(f"Failed to unban user {user_id} from group {group_id}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

async def notify_user_with_invite_link(bot: Bot, user_id: int, invite_link: str):
    try:
        if invite_link:
            await bot.send_message(chat_id=user_id, text=f"لقد تم فك حظرك من مجموعة VIP: يمكنك إعادة الدخول من خلال هذا الرابط {invite_link}")
        else:
            await bot.send_message(chat_id=user_id, text="لقد تم فك حظرك من مجموعة VIP: ولكن هناك مشكلة في توليد رابط الدعوة الجديد.")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} with invite link: {e}")

async def handle_user_unban(bot: Bot, group_id: int, user_id: int):
    await unban_user_from_group(bot, user_id, group_id)

    # Check if we already have a valid invite link stored
    invite_link = invite_links.get(group_id)
    if invite_link:
        valid = await check_invite_link_validity(bot, invite_link)
        if not valid:
            invite_link = await generate_invite_link(bot, group_id)
    else:
        invite_link = await generate_invite_link(bot, group_id)

    await notify_user_with_invite_link(bot, user_id, invite_link)

async def check_and_unban_subscribed_users(bot: Bot, group_id: int):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE subscribed = 1")
    subscribed_users = c.fetchall()
    conn.close()

    for user in subscribed_users:
        user_id = user[0]
        await handle_user_unban(bot, group_id, user_id)

async def subscription_check_loop(bot: Bot, group_id: int):
    while True:
        await check_and_ban_unsubscribed_users(bot, group_id)  # Ensure to define this function
        await check_and_unban_subscribed_users(bot, group_id)
        await asyncio.sleep(3600)


def check_trial_expiration():
    logger.info("Starting check_trial_expiration function.")

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_date = datetime.now()

    logger.info(f"Checking trial expiration. Current date: {current_date}")

    c.execute("SELECT user_id, email, trial_end FROM users WHERE trial_end IS NOT NULL")
    rows = c.fetchall()

    for user_id, email, trial_end in rows:
        if trial_end:
            try:
                trial_end_date = datetime.fromisoformat(trial_end)
                if trial_end_date < current_date:
                    send_email(email, "Your Free Trial Has Expired",
                               "Your free trial has expired. Please subscribe to continue using our services.")



                    logger.info(f"Free trial expired for user_id: {user_id}. Expiry Date: {trial_end_date}.")
                    c.execute("UPDATE users SET trial_end = NULL WHERE user_id = ?", (user_id,))
                    logger.info(f"Updated trial status for user_id: {user_id}.")
                else:
                    logger.info(f"Trial still valid for user_id: {user_id}, ends on {trial_end_date}.")
            except ValueError as e:
                logger.error(f"Date parsing error for user_id {user_id}: {e}")

    conn.commit()
    conn.close()
    logger.info("Finished check_trial_expiration function.")


def update_subscription(user_id, subscribed):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    if subscribed:
        subscription_end = datetime.now() + timedelta(days=30)
        c.execute("UPDATE users SET subscribed = ?, subscription_end = ? WHERE user_id = ?",
                  (subscribed, subscription_end.isoformat(), user_id))
    else:
        c.execute("UPDATE users SET subscribed = ?, subscription_end = NULL WHERE user_id = ?",
                  (subscribed, None, user_id))
    conn.commit()
    conn.close()





# Check subscription expiration
def check_subscription_expiration():
    logger.info("Starting check_subscription_expiration function.")

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_date = datetime.now()

    logger.info(f"Checking subscription expiration. Current date: {current_date}")

    c.execute("SELECT user_id, email, subscription_end FROM users WHERE subscribed = 1")
    rows = c.fetchall()

    for user_id, email, subscription_end in rows:
        if subscription_end:
            try:
                subscription_end_date = datetime.fromisoformat(subscription_end)
                if subscription_end_date < current_date:
                    send_email(email, "Your Subscription Has Expired",
                               "Your subscription has expired. Please renew your subscription to continue using our services.")

                    logger.info(f"Subscription expired for user_id: {user_id}. Expiry Date: {subscription_end_date}.")
                    c.execute("UPDATE users SET subscribed = 0, subscription_end = NULL WHERE user_id = ?", (user_id,))
                    logger.info(f"Updated subscription status for user_id: {user_id}.")
                else:
                    logger.info(f"Subscription still valid for user_id: {user_id}, ends on {subscription_end_date}.")
            except ValueError as e:
                logger.error(f"Date parsing error for user_id {user_id}: {e}")

    conn.commit()
    conn.close()
    logger.info("Finished check_subscription_expiration function.")


# Check and notify for expired subscriptions


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')

    welcome_message = (
        "مرحبا بك ، انت على وشك الانخراط في اقوى غرفة التداول في الوطن العربي.\n \n"
        " \nراح ، نخلو تجربتك تتكلم."
" \n اضغط على الزر Menu ,          "    
        "افتح  حساب للحصول على اسبوع تجريبي مجاني.\n"
    )

    # Translate the welcome message
    translated_welcome_message = translate_text(welcome_message, user_lang)

    # Send the translated welcome message
    await update.message.reply_text(translated_welcome_message)

active_users = set()
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')

    # Clear user_data for this user to reset the state
    context.user_data.clear()

    message = "Please provide your email address to register:"
    translated_message = translate_text(message, user_lang)

    # Create the inline keyboard with a Cancel button
    keyboard = [[InlineKeyboardButton("Cancel", callback_data='cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(translated_message, reply_markup=reply_markup)

    return EMAIL


async def email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')

    email = update.message.text
    if not validate_email(email):
        message = 'Invalid email format. Please enter a valid email address (e.g., example@example.com):'
        translated_message = translate_text(message, user_lang)

        # Create the inline keyboard with a Cancel button
        keyboard = [[InlineKeyboardButton("Cancel", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(translated_message, reply_markup=reply_markup)
        return EMAIL

    context.user_data['email'] = email
    message = 'Thank you! Now, please provide your phone number:'
    translated_message = translate_text(message, user_lang)
    await update.message.reply_text(translated_message)

    return PHONE


async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')

    phone = update.message.text
    if not validate_phone(phone):
        message = 'Invalid phone number format. Please enter a valid phone number (e.g., 0123456789):'
        translated_message = translate_text(message, user_lang)
        await update.message.reply_text(translated_message)
        return PHONE

    email = context.user_data['email']
    trial_end = datetime.now() + timedelta(days=7)
    conn = db_connect()
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users (user_id, email, phone, trial_end, subscribed) VALUES (?, ?, ?, ?, ?)",
                  (user_id, email, phone, trial_end.isoformat(), False))
        conn.commit()
        invite_link = await generate_invite_link(context.bot, group_id)

        if invite_link:
            message = f'Thank you for registering! You have a free trial until {trial_end.date()}. Join the group using this link: {invite_link}'
        else:
            message = f'Thank you for registering! You have a free trial until {trial_end.date()}.'

        translated_message = translate_text(message, user_lang)
        await update.message.reply_text(translated_message)

    except sqlite3.IntegrityError:
        message = 'You are already registered.'
        translated_message = translate_text(message, user_lang)
        await update.message.reply_text(translated_message)

    finally:
        conn.close()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id if query else update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')
    message = "Registration cancelled."
    translated_message = translate_text(message, user_lang)

    if query:
        await query.message.reply_text(translated_message)
        await query.answer()  # To acknowledge the callback query
    else:
        await update.message.reply_text(translated_message)

    return ConversationHandler.END


import requests

from telegram import Update
from telegram.ext import CallbackContext



async def pay(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')


    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        message = "Sorry, there was an error accessing the database. Please try again later."
        translated_message = translate_text(message, user_lang)
        await update.callback_query.message.reply_text(translated_message) if update.callback_query else await update.message.reply_text(translated_message)
        return

    if user:
        # Create a payment request
        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "price_amount": 37.0,
            "price_currency": "usdttrc20",
            "pay_currency": "usdttrc20",
            "order_id": user_id,
            "order_description": "Payment for user registration",
            "ipn_callback_url": "http://192.168.1.9:8000/webhook"
        }

        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors
            payment_data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            message = "Failed to create payment. Please try again later."
            translated_message = translate_text(message, user_lang)
            await update.callback_query.message.reply_text(
                translated_message) if update.callback_query else await update.message.reply_text(translated_message)
            return

        payment_url = payment_data.get("invoice_url")

        if payment_url:
            message = f"Please complete your payment using the following link: {payment_url}"
        else:
            message = "Failed to create payment. Please try again later."
    else:
        message = "User not found in the database."

    translated_message = translate_text(message, user_lang)
    await update.callback_query.message.reply_text(
        translated_message) if update.callback_query else await update.message.reply_text(translated_message)





def is_user_registered(user_id: int) -> bool:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user is not None

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')

    message = (
        "اشتراك في غرفة الاحتراف بسعر حصري  37 usdt  او 8500 دج  للشهر.  \n\n"
        "حسب طريقة الدفع.\n"
        "‼️ هام ‼️  بعد شهر ان لم تحقق ارباح بصفقاتنا راح نقوم بارجاع المبلغ. او شهر مجاني. \n\n"
        "‼️ هام ‼️ اذا تقوم بالدفع بالcrypto , يرجى اختار ال Network الصحيح. \n\n"
    )

    # Translate the welcome message
    translated_message = translate_text(message, user_lang)

    # Create the inline keyboard with two buttons
    keyboard = [
        [
            InlineKeyboardButton("Crypto Payment", callback_data='pay'),
            InlineKeyboardButton("BaridiMob", callback_data='send')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the translated welcome message with the buttons
    await update.message.reply_text(translated_message, reply_markup=reply_markup)



async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    if user_id not in user_languages:
        user_languages[user_id] = 'en'  # Default language

    message = (
        "Thank you for choosing to subscribe to Live VIP Room! \n"
        "Please make a payment to the following account: \n"
        "BaridiMob: 00799999002405340925 \n"
        "Once you have completed the transaction, please send us a photo of the receipt.\n"
    )
    translated_message = translate_text(message, user_languages[user_id])
    await update.callback_query.message.reply_text(translated_message) if update.callback_query else await update.message.reply_text(translated_message)

    # Log the initiation of the subscription
    logger.info(f"Subscription initiated for user {user_id}. Waiting for receipt.")

    # Return the state indicating that the bot is waiting for the receipt
    return WAITING_FOR_RECEIPT




async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_languages:
        user_languages[user_id] = 'en'  # Default language

    logger.info(f"Received message: {update.message}")

    try:
        # Check if there is a photo in the message
        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()

            # Define the path to save the photo
            receipts_dir = 'receipts'
            if not os.path.exists(receipts_dir):
                os.makedirs(receipts_dir)
            photo_path = os.path.join(receipts_dir, f'{update.message.from_user.id}.jpg')


            await photo_file.download_to_drive(photo_path)


            message = "Thank you! Your receipt has been received. Check your email in the next few days for confirmation."
            translated_message = translate_text(message, user_languages[user_id])
            await update.message.reply_text(translated_message)
            logger.info(f"Receipt from user {update.message.from_user.id} saved to {photo_path}")


            conn = db_connect()
            c = conn.cursor()
            c.execute("SELECT email, phone FROM users WHERE user_id = ?", (update.message.from_user.id,))
            user_data = c.fetchone()
            conn.close()

            if user_data:
                email, phone = user_data
            else:
                email = "Unknown"
                phone = "Unknown"


            for admin_id in ADMINS:
                try:
                    with open(photo_path, 'rb') as photo:
                        caption = (f"User ID: {update.message.from_user.id}\n"
                                   f"Email: {email}\n"
                                   f"Phone: {phone}")
                        await context.bot.send_photo(chat_id=admin_id, photo=photo, caption=caption)
                except Exception as e:
                    logger.error(f"Failed to send photo to admin {admin_id}: {e}")

        else:
            logger.warning("No photo found in the message.")
            message = "No photo found in your message. Please send a valid photo."
            translated_message = translate_text(message, user_languages[user_id])
            await update.message.reply_text(translated_message)

    except Exception as e:
        logger.error(f"Error handling receipt: {e}")
        message = "Sorry, there was an error handling your receipt. Please try again later."
        translated_message = translate_text(message, user_languages[user_id])
        await update.message.reply_text(translated_message)

    return ConversationHandler.END

async def verify_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMINS:
        message = "You are not authorized to use this command."
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)
        return

    try:
        target_user_id = int(context.args[0])
        status = context.args[1].lower()
    except (IndexError, ValueError):
        message = "Usage: /verify <user_id> <status (approve/reject)>"
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)
        return

    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE user_id = ?", (target_user_id,))
    user = c.fetchone()

    if not user:
        message = "User not found."
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)
        return

    if status == "approve":
        invite_link = await generate_invite_link(context.bot, group_id)
        update_subscription(target_user_id, True)
        email = user[0]
        send_email(email, "Subscription Confirmation",
                   f"Your subscription has been confirmed. Welcome to the Live VIP Room! ")
        message = f"User {target_user_id} has been approved and notified via email."
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)
    elif status == "reject":
        message = f"User {target_user_id} has been rejected."
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)
    else:
        message = "Invalid status. Use 'approve' or 'reject'."
        translated_message = translate_text(message, user_languages.get(user_id, 'en'))
        await update.message.reply_text(translated_message)

    conn.close()


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT subscribed, subscription_end, trial_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        subscribed, subscription_end, free_trial_end = result
        today = date.today()

        if free_trial_end:
            free_trial_end_date = datetime.fromisoformat(free_trial_end).date()
            if today <= free_trial_end_date:
                days_left = (free_trial_end_date - today).days
                formatted_date = free_trial_end_date.strftime('%d/%m/%Y')
                if days_left == 0:
                    free_trial_message = f"Your free trial ends today ({formatted_date})."
                else:
                    free_trial_message = f"Your free trial is active and ends in {days_left} days on {formatted_date}."
            else:
                free_trial_message = "Your free trial has ended."
        else:
            free_trial_message = "You are not in a free trial period."

        if subscribed:
            subscription_status = f"Active until {datetime.fromisoformat(subscription_end).strftime('%Y-%m-%d')}"
        else:
            subscription_status = "Inactive. Please subscribe to access services."


        user_lang = user_languages.get(user_id, 'en')


        free_trial_message_translated = translate_text(free_trial_message, user_lang)
        subscription_status_translated = translate_text(subscription_status, user_lang)

        await update.message.reply_text(
            f"{free_trial_message_translated}\n\n{subscription_status_translated}"
        )
    else:
        user_lang = user_languages.get(user_id, 'en')
        not_registered_message = "You are not registered. Please use /register to start the registration process."
        not_registered_message_translated = translate_text(not_registered_message, user_lang)
        await update.message.reply_text(not_registered_message_translated)

async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMINS:
        await update.message.reply_text('You are not authorized to use this command.')
        return


    if len(context.args) == 0 and not update.message.voice and not update.message.document and not update.message.video:
        await update.message.reply_text('Please provide the message content or attach a media file.')
        return

    message_content = ' '.join(context.args)

    if update.message.voice:
        voice_file = await update.message.voice.get_file()
        media_file = voice_file.file_path
        media_type = 'voice'
    elif update.message.document:
        document_file = await update.message.document.get_file()
        media_file = document_file.file_path
        media_type = 'document'
    elif update.message.video:
        video_file = await update.message.video.get_file()
        media_file = video_file.file_path
        media_type = 'video'
    else:
        media_file = None
        media_type = None

    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE subscribed = 1")
    subscribed_users = c.fetchall()
    conn.close()

    for user in subscribed_users:
        try:
            if media_type == 'voice':
                await context.bot.send_voice(chat_id=user[0], voice=media_file, caption=message_content)
            elif media_type == 'document':
                await context.bot.send_document(chat_id=user[0], document=media_file, caption=message_content)
            elif media_type == 'video':
                await context.bot.send_video(chat_id=user[0], video=media_file, caption=message_content)
            else:
                await context.bot.send_message(chat_id=user[0], text=message_content)
        except Exception as e:
            logger.error(f"Failed to send message to user {user[0]}: {e}")




HELP_REQUEST = range(1)

async def help_request(update: Update, context: CallbackContext) -> int:
    default_message = "Please describe your problem or question."
    user_id = update.message.from_user.id
    user_lang = user_languages.get(user_id, 'en')
    translated_message = translate_text(default_message, user_lang)

    await update.message.reply_text(translated_message)
    return HELP_REQUEST


conn = sqlite3.connect('users.db')
c = conn.cursor()


async def handle_help_request(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_message = update.message.text


    c.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    phone_number = result[0] if result else "Not provided"
    if phone_number.startswith('0'):
        phone_number = '+213' + phone_number[1:]


    support_message = f"User ID: {user_id}\nPhone Number: {phone_number}\nMessage: {user_message}"
    await context.bot.send_message(chat_id='1695689621', text=support_message)


    default_acknowledgement = "Thank you for reaching out! Our support team will respond to you via your Telegram account."
    user_lang = user_languages.get(user_id, 'en')
    translated_acknowledgement = translate_text(default_acknowledgement, user_lang)

    await update.message.reply_text(translated_acknowledgement)


import nest_asyncio

async def reminder_check_loop(bot):
    while True:
        await send_trial_reminders(bot)
        await send_subscription_reminders(bot)
        check_subscription_expiration()
        check_trial_expiration()
        await asyncio.sleep(3600)



nest_asyncio.apply()


WEBHOOK_URL = f"{os.environ['RENDER_EXTERNAL_URL']}/webhook"  # Render URL

app = FastAPI()

application = Application.builder().token(BOT_TOKEN).build()  # Replace with your bot token

@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return {"message": "Webhook received"}

async def main():
    # Define command handlers
    application.add_handler(CommandHandler("start", start))
    registration_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, email),
                CallbackQueryHandler(cancel, pattern='^cancel$')
            ],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
    )

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('help', help_request)],
        states={
            HELP_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_request)],
        },
        fallbacks=[],
    )
    application.add_handler(conversation_handler)

    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("send", send))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt))
    application.add_handler(registration_conv_handler)
    application.add_handler(CommandHandler("verify", verify_receipt))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("setlang", set_language))
    application.add_handler(CommandHandler("admin_send", admin_send))
    application.add_handler(CallbackQueryHandler(button))

    bot = application.bot

    asyncio.create_task(subscription_check_loop(bot, group_id))
    asyncio.create_task(reminder_check_loop(bot))

    await bot.set_webhook(WEBHOOK_URL)  # Set webhook for bot

if __name__ == '__main__':
    asyncio.run(main())
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)