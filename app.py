import os
import re
import json
import time
import random
import requests
from datetime import datetime
from flask import Flask, request, jsonify
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
    time.sleep(1)
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    requests.post(url, json=payload)

def send_telegram(text):
    if TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        requests.post(url, data=payload)

# ================= AUTO POST =================
POST_CONTENT = [
    "🔥 Thuốc lào Quảng Xương thơm nặng – Ship COD toàn quốc!",
    "Hàng mới về khói đậm phê mạnh 💨",
    "Anh em cần thuốc lào chuẩn vị inbox ngay!"
]

SEED_COMMENTS = [
    "Ai cần inbox em nhé 🔥",
    "Hàng đang sẵn kho",
    "Có ship COD toàn quốc"
]

def post_daily_content():
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    content = random.choice(POST_CONTENT)

    payload = {
        "message": content,
        "access_token": PAGE_ACCESS_TOKEN
    }

    res = requests.post(url, data=payload)
    result = res.json()

    if "id" in result:
        post_id = result["id"]

        for _ in range(random.randint(1, 2)):
            comment = random.choice(SEED_COMMENTS)
            requests.post(
                f"https://graph.facebook.com/v18.0/{post_id}/comments",
                data={
                    "message": comment,
                    "access_token": PAGE_ACCESS_TOKEN
                }
            )
            time.sleep(2)

# ================= AI =================
def ai_reply(question):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là nhân viên bán thuốc lào, trả lời ngắn gọn, tập trung bán hàng."},
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Anh inbox để em tư vấn kỹ hơn nhé."

# ================= SALE FLOW =================
def handle_sale_flow(sender_id, text):

    if text in ["giá", "bao nhiêu", "price"]:
        send_message(sender_id,
            "🔥 Bảng giá:\n"
            "✔ Loại thường: 100k\n"
            "✔ Loại đặc biệt: 150k\n\n"
            "Anh muốn đặt loại nào?"
        )
        user_data[sender_id] = {"step": "product"}
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
            send_message(sender_id, "✅ Đã chốt đơn! Hàng sẽ giao sớm.")

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

    send_telegram(f"📊 BÁO CÁO HÔM NAY\nĐơn: {count}\nDoanh thu: {revenue}đ")

# ================= LEGAL PAGES =================
@app.route("/")
def home():
    return """
    <h2>Chính sách quyền riêng tư</h2>
    <p>Ứng dụng không chia sẻ dữ liệu người dùng cho bên thứ ba.</p>
    <p>Dữ liệu chỉ dùng để xử lý đơn hàng và trả lời tin nhắn tự động.</p>
    <p>Người dùng có thể yêu cầu xóa dữ liệu tại /delete-data</p>
    """

@app.route("/terms")
def terms():
    return """
    <h2>Điều khoản dịch vụ</h2>
    <p>Ứng dụng cung cấp thông tin sản phẩm và hỗ trợ đặt hàng tự động.</p>
    <p>Chúng tôi không chịu trách nhiệm nếu người dùng sử dụng sai mục đích.</p>
    """

@app.route("/delete-data", methods=["POST","GET"])
def delete_data():
    return jsonify({
        "url": "https://yourdomain.com/delete-data",
        "confirmation_code": "DATA_DELETED"
    })

# ================= WEBHOOK =================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        verify_token = "thuoclao"
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

                customers = load_data(CUSTOMER_FILE)
                customers[sender_id] = {"last_message": str(datetime.now())}
                save_data(CUSTOMER_FILE, customers)

                if not handle_sale_flow(sender_id, text):
                    reply = ai_reply(text)
                    send_message(sender_id, reply)

    return "ok"

# ================= RUN =================
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_report, 'cron', hour=21, minute=0)
    scheduler.add_job(post_daily_content, 'cron', hour=19, minute=30)
    scheduler.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
