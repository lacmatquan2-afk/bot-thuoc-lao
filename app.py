import os
import re
import json
import time
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, request
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

CUSTOMER_FILE = "customers.json"
ORDER_FILE = "orders.json"

user_data = {}
last_message_time = {}

# ================= FILE =================
def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================= FACEBOOK =================
def send_message(psid, text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    requests.post(url, json=payload)

def send_quick_reply(psid):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": "Chọn chức năng:",
            "quick_replies": [
                {"content_type": "text", "title": "🔥 Xem giá", "payload": "PRICE"},
                {"content_type": "text", "title": "📦 Đặt hàng", "payload": "ORDER"},
                {"content_type": "text", "title": "📞 Tư vấn", "payload": "HELP"}
            ]
        }
    }
    requests.post(url, json=payload)

def send_telegram(text):
    if TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        requests.post(url, data=payload)

# ================= SALE FLOW =================
def handle_sale_flow(sender_id, text):

    if text == "price":
        send_message(sender_id,
            "🔥 Bảng giá:\n"
            "✔ Loại 100k\n"
            "✔ Loại đặc biệt 150k\n\n"
            "Chọn loại để đặt hàng."
        )
        return True

    if text == "order":
        user_data[sender_id] = {"step": "product"}
        send_message(sender_id, "Anh chọn 100k hay 150k?")
        return True

    if sender_id in user_data:

        step = user_data[sender_id]["step"]

        if step == "product":
            if "150" in text:
                user_data[sender_id]["product"] = "150k"
                user_data[sender_id]["price"] = 150000
            else:
                user_data[sender_id]["product"] = "100k"
                user_data[sender_id]["price"] = 100000

            send_message(sender_id, "Anh gửi SĐT:")
            user_data[sender_id]["step"] = "phone"
            return True

        if step == "phone":
            if re.fullmatch(r"0\d{9}", text):
                user_data[sender_id]["phone"] = text
                send_message(sender_id, "Anh gửi địa chỉ:")
                user_data[sender_id]["step"] = "address"
            else:
                send_message(sender_id, "SĐT chưa đúng.")
            return True

        if step == "address":

            orders = load_data(ORDER_FILE)
            order_id = str(len(orders)+1)

            order = {
                "product": user_data[sender_id]["product"],
                "price": user_data[sender_id]["price"],
                "phone": user_data[sender_id]["phone"],
                "address": text,
                "time": str(datetime.now())
            }

            orders[order_id] = order
            save_data(ORDER_FILE, orders)

            send_telegram(f"ĐƠN MỚI:\n{order}")
            send_message(sender_id, "✅ Đã chốt đơn!")

            user_data.pop(sender_id)
            return True

    return False

# ================= REPORT =================
def daily_report():
    orders = load_data(ORDER_FILE)
    today = datetime.now().date()

    count = 0
    revenue = 0

    for o in orders.values():
        t = datetime.fromisoformat(o["time"]).date()
        if t == today:
            count += 1
            revenue += o["price"]

    send_telegram(f"📊 BÁO CÁO HÔM NAY\n"
        f"Đơn: {count}\n"
        f"Doanh thu: {revenue}đ"
        )
    
# ================= WEBHOOK =================
@app.route("/")
def home():
    return "Bot thuoc lao dang chay OK"
@app.route("/delete-data", methods=["GET"])
def delete_data():
    return "Chúng tôi không lưu trữ dữ liệu người dùng."
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        verify_token = "thuoclao"   # token bạn đã nhập trong Facebook
        token_sent = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token_sent == verify_token:
            return challenge
        return "Verify token sai"

    if request.method == "POST":
        data = request.json

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]

                text = event.get("message", {}).get("text", "").lower()

                if not text:
                    return "ok"

                if text == "/report":
                    daily_report()
                    return "ok"

                handle_sale_flow(sender_id, text)

            send_quick_reply(sender_id)

    return "ok"

# ================= SCHEDULER =================
scheduler = BackgroundScheduler()
scheduler.add_job(daily_report, 'cron', hour=21, minute=0)
scheduler.start()

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)








