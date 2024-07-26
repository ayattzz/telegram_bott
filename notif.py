import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from fastapi import FastAPI, Request, HTTPException
import sqlite3
import hmac
import hashlib
from telegram import Bot
from main import logger

app = FastAPI()

SECRET_KEY = "+GAtFHo4O763z0DJL5e0055rjFOLMEo9"  # Set this to your NOWPayments secret key
BOT_TOKEN = "7351033518:AAFBkj3rwQB3K3ir0rdRxWjKXox__Y38vLA"
GROUP_ID = -1002240963009

def get_user_id_by_order_id(order_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        raise HTTPException(status_code=404, detail="User not found")

def send_email(to_email, subject, body):
    from_email = "ayazerouki1@gmail.com"
    from_password = "tivz ydaa tzcz epka"
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

async def notify_user(user_id, message):
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def db_connect():
    return sqlite3.connect('users.db')

async def generate_invite_link(bot: Bot, group_id: int) -> str:
    try:
        invite_link = await bot.export_chat_invite_link(chat_id=group_id)
        return invite_link
    except Exception as e:
        logger.error(f"Failed to generate invite link for group {group_id}: {e}")
        return None

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    payload_str = payload.decode('utf-8').strip()
    print(f"Raw Payload: {payload_str}")

    received_signature = request.headers.get('x-nowpayments-sig')
    if not received_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    data = await request.json()
    sorted_payload = json.dumps(data, sort_keys=True, separators=(',', ':'))
    print(f"Sorted Payload for Signature Calculation: {sorted_payload}")

    computed_signature = hmac.new(bytes(SECRET_KEY, 'utf-8'), sorted_payload.encode('utf-8'), hashlib.sha512).hexdigest()
    print(f"Computed Signature: {computed_signature}")

    if received_signature != computed_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if data.get("payment_status") == "finished":
        try:
            user_id = get_user_id_by_order_id(data.get("order_id"))
            update_subscription(user_id, True)
            email = get_email_by_user_id(user_id)
            await notify_user(user_id, "Payment confirmed!")
            bot = Bot(token=BOT_TOKEN)  # Create an instance of the bot
            invite_link = await generate_invite_link(bot, GROUP_ID)  # Pass the bot instance
            send_email(email, "Subscription Confirmation",
                       f"Your subscription has been confirmed. Welcome to the Live VIP Room! ")
        except HTTPException as e:
            print(f"Error: {e.detail}")
            raise e

    return {"status": "success"}

def get_email_by_user_id(user_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        raise HTTPException(status_code=404, detail="User not found")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="192.168.1.9", port=8000)
