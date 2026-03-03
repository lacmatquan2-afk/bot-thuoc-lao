import os
import re
import time
import threading
import requests
import pytz
from flask import Flask, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}

# ================= GIÁ =================

PRICE = {
    "nhẹ": 120000,
    "vừa": 150000,
    "nặng": 180000
}

# ================= SEND MESSAGE =================

def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    requests.post(url, json=payload)

# ================= COMMENT =================

def reply_comment(comment_id, message):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    payload = {
        "message": message,
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post(url, data=payload)

# ================= TELEGRAM =================

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    requests.post(url, json=payload)

# ================= DETECT PHONE =================

def detect_phone(text):
    pattern = r'(0\d{9,10})'
    match = re.search(pattern, text)
    return match.group(0) if match else None

# ================= TÍNH TIỀN =================

def calculate_price(text):
    lower = text.lower()

    # Tìm số lạng
    numbers = re.findall(r'\d+', lower)
    if not numbers:
        return None

    lang = int(numbers[0])

    # Xác định loại
    for loai in PRICE:
        if loai in lower:
            price_per = PRICE[loai]
            total = lang * price_per

            if lang >= 3:
                ship = "Miễn phí ship 🚀"
            else:
                ship = "Phí ship 30k"

            return f"{lang} lạng loại {loai} = {total:,}đ\n{ship}"

    return None

# ================= AI =================

def ai_reply(user_id, message):
    lower = message.lower()

    if user_id not in user_data:
        user_data[user_id] = {"ordered": False}

    # Hỏi giá chung
    if "giá" in lower:
        return (
            "Bên em có:\n"
            "• Loại nhẹ: 120k/lạng\n"
            "• Loại vừa: 150k/lạng\n"
            "• Loại nặng: 180k/lạng\n"
            "Anh lấy loại nào và bao nhiêu lạng để em tính tiền ạ?"
        )

    # Tính tiền
    price_info = calculate_price(lower)
    if price_info:
        return f"{price_info}\nAnh cho em xin SĐT + địa chỉ để em lên đơn ạ 🚀"

    # Hỏi nặng nhẹ
    if "nặng" in lower or "nhẹ" in lower or "vừa" in lower:
        return "Anh lấy bao nhiêu lạng để em tính tổng tiền giúp anh ạ?"

    # AI fallback
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là nhân viên bán thuốc lào. Trả lời ngắn gọn, tập trung chốt đơn."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

# ================= WEBHOOK =================

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid"

    data = request.get_json()

    for entry in data.get("entry", []):

        # INBOX
        for messaging in entry.get("messaging", []):
            sender = messaging["sender"]["id"]

            if "message" in messaging:
                text = messaging["message"].get("text", "")

                phone = detect_phone(text)

                if phone:
                    user_data[sender]["ordered"] = True
                    send_message(sender, "Em đã nhận thông tin. Bên em sẽ gọi xác nhận sớm nhất ạ 🚀")

                    send_telegram(
                        f"🔥 ĐƠN HÀNG MỚI 🔥\n"
                        f"Khách: {sender}\n"
                        f"SĐT: {phone}\n"
                        f"Nội dung: {text}"
                    )
                    continue

                reply = ai_reply(sender, text)
                send_message(sender, reply)

        # COMMENT
        for change in entry.get("changes", []):
            if change.get("field") == "feed":
                value = change.get("value", {})
                comment_id = value.get("comment_id")
                from_id = value.get("from", {}).get("id")

                if from_id == PAGE_ID:
                    continue

                reply_comment(comment_id, "Em đã inbox anh/chị rồi ạ 🚀")
                send_message(from_id, "Chào anh/chị, bên em tư vấn ngay ạ!")

    return "OK", 200

# ================= AUTO POST =================

vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")

def auto_post():
    message = (
        "🔥 Thuốc lào Quảng Xương 🔥\n"
        "• Nhẹ 120k\n"
        "• Vừa 150k\n"
        "• Nặng 180k\n"
        "3 lạng freeship 🚀"
    )

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": PAGE_ACCESS_TOKEN
    }

    res = requests.post(url, data=payload)
    print("Auto post:", res.text)

scheduler = BackgroundScheduler(timezone=vn_tz)
scheduler.add_job(auto_post, CronTrigger(hour=8, minute=0, timezone=vn_tz))
scheduler.start()

print("Scheduler started")

# ================= HOME =================

@app.route("/")
def home():
    return "Bot is running"

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
