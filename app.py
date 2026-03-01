from flask import Flask, request
import requests
import os
import sqlite3
import random
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(_name_)

# ================== CONFIG ==================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# ================== DATABASE ==================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id TEXT,
        message TEXT,
        level TEXT,
        time TEXT,
        remarketed INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================== HOME ==================
@app.route("/")
def home():
    return "<h1>👑 BOT SAFE MODE ĐANG CHẠY 🔥</h1>"

# ================== ADMIN ==================
@app.route("/admin")
def admin():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM customers ORDER BY id DESC")
    data = c.fetchall()
    conn.close()

    html = "<h2>Danh sách khách</h2>"
    for row in data:
        html += f"<p>{row}</p>"
    return html

# ================== VERIFY ==================
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Sai verify token"

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event:
                    message_text = messaging_event["message"].get("text", "")
                    handle_message(sender_id, message_text)

            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    comment_id = value.get("comment_id")
                    from_id = value.get("from", {}).get("id")

                    if comment_id:
                        reply_comment(comment_id)
                        if from_id:
                            send_message(from_id, "🔥 Em đã inbox anh tư vấn chi tiết rồi ạ!")

    return "OK", 200

# ================== HANDLE MESSAGE ==================
def handle_message(sender_id, message_text):
    text = message_text.lower()
    level = "cold"

    if any(word in text for word in ["mua", "đặt", "lấy"]):
        level = "hot"

    save_customer(sender_id, message_text, level)

    if any(word in text for word in ["giá", "bao nhiêu"]):
        reply = "🔥 Thuốc lào Quảng Định thơm đậm\nGiá từ 3x/kg\nFree ship từ 3 lạng 🚚\nGọi/Zalo: 0868862907"

    elif any(word in text for word in ["ship", "giao"]):
        reply = "🚚 Ship toàn quốc\nNhận hàng kiểm tra rồi thanh toán."

    elif any(word in text for word in ["sỉ", "đại lý"]):
        reply = "💰 Có giá sỉ cho đại lý.\nLiên hệ: 0868862907"

    elif level == "hot":
        reply = "🔥 Anh cho em xin SĐT + địa chỉ để chốt đơn nhé!"

    else:
        reply = ask_ai(message_text)

    send_message(sender_id, reply)

# ================== AI ==================
def ask_ai(message):
    if not OPENAI_API_KEY:
        return "Anh cần tư vấn loại nào ạ? 🔥"

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    data = {
        "model": "gpt-4o-mini",
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": "Bạn là nhân viên bán thuốc lào Quảng Định, nói chuyện tự nhiên, không spam."},
            {"role": "user", "content": message}
        ]
    }

    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=data
    )

    return r.json()["choices"][0]["message"]["content"]

# ================== SEND MESSAGE ==================
def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    requests.post(url, json=payload)

# ================== COMMENT REPLY ==================
def reply_comment(comment_id):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    payload = {
        "message": "🔥 Check inbox giúp em nhé anh!",
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post(url, data=payload)

# ================== SAVE DB ==================
def save_customer(sender_id, message_text, level):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO customers (sender_id, message, level, time) VALUES (?, ?, ?, ?)",
        (sender_id, message_text, level, datetime.now().isoformat())
    )

    conn.commit()
    conn.close()

# ================== SAFE REMARKETING ==================
def remarketing():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    SELECT id, sender_id, time FROM customers
    WHERE level='hot' AND remarketed=0
    """)

    users = c.fetchall()

    for user in users:
        record_id, sender_id, created_time = user
        created_time = datetime.fromisoformat(created_time)

        if datetime.now() - created_time <= timedelta(hours=24):

            messages = [
                "🔥 Em còn giữ giá tốt cho anh hôm nay nhé!",
                "🚚 Hôm nay chốt em free ship cho anh nhé!",
                "💨 Thuốc đang rất thơm, anh chốt giúp em nhé!"
            ]

            send_message(sender_id, random.choice(messages))

            c.execute("UPDATE customers SET remarketed=1 WHERE id=?", (record_id,))
            conn.commit()

            time.sleep(5)

    conn.close()

# ================== AUTO POST ==================
def auto_post():
    if not PAGE_ID:
        return

    content = """
🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥

💨 Thơm đậm – Nặng đô – Phê lâu
🚚 Ship toàn quốc
🎁 Free ship từ 3 lạng

📞 0868862907
"""

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    payload = {
        "message": content,
        "access_token": PAGE_ACCESS_TOKEN
    }

    requests.post(url, data=payload)

# ================== SCHEDULER ==================
scheduler = BackgroundScheduler()
scheduler.add_job(remarketing, "interval", hours=2)
scheduler.add_job(auto_post, "cron", hour=9)
scheduler.start()

# ================== RUN ==================
if _name_ == "_main_":
    app.run(debug=True)
