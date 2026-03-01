from flask import Flask, request
import requests
import os
import sqlite3
import re
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

app = Flask(__name__)

# =========================
# ENV (SET TRONG RENDER)
# =========================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PAGE_ID = os.environ.get("PAGE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# DATABASE
# =========================
def init_db():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fb_id TEXT,
            name TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =========================
# MEMORY TRẠNG THÁI KHÁCH
# =========================
user_states = {}

# =========================
# VERIFY WEBHOOK
# =========================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Error", 403

# =========================
# MAIN WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            # ===== INBOX =====
            if "messaging" in entry:
                for msg in entry["messaging"]:
                    sender_id = msg["sender"]["id"]

                    if sender_id == PAGE_ID:
                        continue

                    if "message" in msg and "text" in msg["message"]:
                        text = msg["message"]["text"]

                        # Nếu đang trong quy trình chốt đơn
                        if sender_id in user_states:
                            handle_order_flow(sender_id, text)
                            continue

                        # Kiểm tra có SĐT không
                        phone = extract_phone(text)
                        if phone:
                            user_states[sender_id] = {
                                "phone": phone,
                                "step": "ask_address"
                            }
                            send_message(sender_id, "🔥 Em đã nhận SĐT. Anh/chị cho em xin địa chỉ giao hàng nhé?")
                            continue

                        reply = ai_reply(text)
                        send_message(sender_id, reply)

            # ===== COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        value = change["value"]

                        if value.get("item") == "comment":
                            comment_id = value.get("comment_id")
                            from_id = value.get("from", {}).get("id")
                            message = value.get("message", "")

                            if from_id == PAGE_ID:
                                continue

                            reply = ai_reply(message)
                            reply_comment(comment_id, reply)

                            # Tự inbox
                            send_message(from_id, "👋 Em đã phản hồi dưới comment. Check inbox giúp em để chốt đơn nhé!")

                            phone = extract_phone(message)
                            if phone:
                                user_states[from_id] = {
                                    "phone": phone,
                                    "step": "ask_address"
                                }
                                send_message(from_id, "🔥 Em đã nhận SĐT. Anh/chị cho em xin địa chỉ giao hàng nhé?")

    return "OK", 200

# =========================
# ORDER FLOW TỪNG BƯỚC
# =========================
def handle_order_flow(user_id, text):
    state = user_states[user_id]

    if state["step"] == "ask_address":
        state["address"] = text
        state["step"] = "ask_name"
        send_message(user_id, "Cho em xin tên người nhận hàng ạ?")
        return

    if state["step"] == "ask_name":
        state["name"] = text
        save_order(user_id, state["name"], state["phone"], state["address"])
        send_message(user_id, "✅ Đơn đã ghi nhận. Bên em sẽ liên hệ xác nhận và giao sớm nhất 🚚")
        del user_states[user_id]

# =========================
# AI REPLY
# =========================
def ai_reply(text):
    prompt = f"""
Bạn là nhân viên bán thuốc lào Quảng Định.
Trả lời ngắn gọn, thân thiện, mục tiêu chốt đơn.
Khách nói: {text}
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except:
        return "Thuốc lào Quảng Định thơm đậm 🔥 Liên hệ 0868862907"

# =========================
# EXTRACT PHONE
# =========================
def extract_phone(text):
    phones = re.findall(r'0\d{9}', text)
    return phones[0] if phones else None

# =========================
# SEND MESSAGE
# =========================
def send_message(user_id, text):
    url = f"https://graph.facebook.com/v18.0/me/messages"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    requests.post(url, params=params, json=payload)

# =========================
# REPLY COMMENT
# =========================
def reply_comment(comment_id, text):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    requests.post(url, params={
        "access_token": PAGE_ACCESS_TOKEN,
        "message": text
    })

# =========================
# SAVE ORDER
# =========================
def save_order(fb_id, name, phone, address):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("INSERT INTO orders (fb_id, name, phone, address, created_at) VALUES (?, ?, ?, ?, ?)",
              (fb_id, name, phone, address, datetime.now()))
    conn.commit()
    conn.close()

    send_telegram(f"🔥 ĐƠN MỚI\nTên: {name}\nSĐT: {phone}\nĐịa chỉ: {address}")

# =========================
# TELEGRAM
# =========================
def send_telegram(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        })

# =========================
# AUTO POST DAILY
# =========================
def auto_post():
    content = "🔥 Thuốc lào Quảng Định thơm đậm – Ship toàn quốc 🚚 Liên hệ 0868862907"
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    requests.post(url, data={
        "message": content,
        "access_token": PAGE_ACCESS_TOKEN
    })

scheduler = BackgroundScheduler()
scheduler.add_job(auto_post, "interval", days=1)
scheduler.start()

# =========================
# META REQUIRED
# =========================
@app.route("/")
def home():
    return "KING MAXIMUM V2 BOT ĐANG HOẠT ĐỘNG 👑"

@app.route("/privacy")
def privacy():
    return """
    <h1>Chính sách quyền riêng tư</h1>
    <p>Ứng dụng dùng để trả lời tin nhắn và xử lý đơn hàng.</p>
    <p>Không chia sẻ dữ liệu cho bên thứ ba.</p>
    <p>Email: lacmatquan2@gmail.com</p>
    """

@app.route("/data-deletion")
def data_deletion():
    return """
    <h1>Yêu cầu xóa dữ liệu</h1>
    <p>Gửi email: lacmatquan2@gmail.com</p>
    <p>Xử lý trong 24 giờ.</p>
    """

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
