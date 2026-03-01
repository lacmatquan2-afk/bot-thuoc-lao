import os
import requests
import sqlite3
from flask import Flask, request
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# ===== CONFIG =====
VERIFY_TOKEN = "VERIFY_TOKEN"
PAGE_ACCESS_TOKEN = "PAGE_ACCESS_TOKEN"
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "CHAT_ID"
OPENAI_API_KEY = "OPENAI_KEY"
IMAGE_URL = "LINK_ANH"

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== DATABASE =====
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fb_id TEXT,
    name TEXT,
    phone TEXT,
    address TEXT,
    time TEXT
)
""")
conn.commit()

user_states = {}

# ===== VERIFY =====
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Invalid"

# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if "entry" in data:
        for entry in data["entry"]:
            if "messaging" in entry:
                for event in entry["messaging"]:
                    handle_message(event)
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        handle_comment(change["value"])
    return "ok", 200

# ===== COMMENT =====
def handle_comment(value):
    if "comment_id" in value:
        user_id = value["from"]["id"]
        send_message(user_id, "Cảm ơn anh đã quan tâm 🌿 Em inbox tư vấn ngay ạ!")
        send_private_reply(value["comment_id"], "Em đã inbox anh kiểm tra giúp em nhé 📩")

# ===== MESSAGE FLOW =====
def handle_message(event):
    sender_id = event["sender"]["id"]

    if "text" not in event["message"]:
        return

    text = event["message"]["text"]

    if sender_id not in user_states:
        user_states[sender_id] = {"step": "chat"}

    state = user_states[sender_id]

    # ===== FLOW ĐẶT HÀNG =====
    if text.lower() in ["mua", "đặt hàng", "chốt"]:
        state["step"] = "name"
        send_message(sender_id, "Anh cho em xin TÊN người nhận:")
        return

    if state["step"] == "name":
        state["name"] = text
        state["step"] = "phone"
        send_message(sender_id, "Cho em xin SỐ ĐIỆN THOẠI:")
        return

    if state["step"] == "phone":
        state["phone"] = text
        state["step"] = "address"
        send_message(sender_id, "Cho em xin ĐỊA CHỈ giao hàng:")
        return

    if state["step"] == "address":
        state["address"] = text
        save_order(sender_id, state)
        send_message(sender_id, "✅ Đặt hàng thành công! Bên em sẽ gọi xác nhận.")
        user_states[sender_id] = {"step": "chat"}
        return

    # ===== AI CHAT =====
    ai_reply = ask_ai(text)
    send_message(sender_id, ai_reply)

# ===== SAVE ORDER =====
def save_order(fb_id, state):
    now = str(datetime.now())
    cursor.execute(
        "INSERT INTO orders (fb_id, name, phone, address, time) VALUES (?, ?, ?, ?, ?)",
        (fb_id, state["name"], state["phone"], state["address"], now)
    )
    conn.commit()

    order_text = f"""
🔥 CÓ ĐƠN MỚI

👤 {state['name']}
📞 {state['phone']}
🏠 {state['address']}
⏰ {now}
"""
    send_telegram(order_text)

# ===== AI =====
def ask_ai(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là nhân viên bán thuốc lào Quảng Định. Trả lời ngắn gọn, thuyết phục."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

# ===== SEND FB MESSAGE =====
def send_message(user_id, text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": user_id}, "message": {"text": text}}
    requests.post(url, json=payload)

# ===== PRIVATE COMMENT REPLY =====
def send_private_reply(comment_id, text):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/private_replies?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={"message": text})

# ===== TELEGRAM =====
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})

# ===== AUTO POST DAILY =====
def auto_post():
    content = ask_ai("Viết bài bán thuốc lào Quảng Định hấp dẫn, ngắn gọn.")
    url = f"https://graph.facebook.com/v18.0/me/photos?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"url": IMAGE_URL, "caption": content}
    requests.post(url, data=payload)

scheduler = BackgroundScheduler()
scheduler.add_job(auto_post, "interval", days=1)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
