import os
import re
import requests
from datetime import datetime
from flask import Flask, request
from openai import OpenAI
import time

app = Flask(__name__)
@app.route("/")
def home():
    return """
<h2>Privacy Policy</h2>
<p>Bot Thuoc Lao Quang Dinh does not collect, store or share personal data.</p>
<p>We only use Messenger data to reply to customer messages.</p>
<p>Contact: lacmatquan2@gmail.com</p>
"""

# ================= CONFIG =================
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}
last_message_time = {}

# ================= HELPER =================
def send_message(psid, text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    requests.post(url, json=payload)

def send_telegram(text):
    if TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        requests.post(url, data=payload)

def is_phone(text):
    return re.fullmatch(r"0\d{9}", text)

# ================= AI CHỈ HỖ TRỢ NGOÀI LUỒNG =================
def ai_reply(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                 "Bạn là trợ lý phụ. Chỉ trả lời các câu hỏi ngoài luồng "
                 "như cách hút, bảo quản, nguồn gốc. "
                 "Không tự chốt đơn. Trả lời ngắn gọn."},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Anh cần tư vấn thêm gì không ạ?"

# ================= FLOW CHỐT ĐƠN =================
def handle_sale_flow(sender_id, text):

    if sender_id not in user_data:
        user_data[sender_id] = {"step": "start"}

    step = user_data[sender_id].get("step")

    # ===== BƯỚC 1: GIỚI THIỆU =====
    if step == "start":
        send_message(sender_id,
            "🔥 Thuốc Lào Quảng Định chính gốc 🔥\n\n"
            "✔ Loại 1: 100k\n"
            "✔ Loại ĐẶC BIỆT: 150k (đậm hơn, hút đã hơn)\n\n"
            "Anh lấy loại 100k hay 150k ạ?"
        )
        user_data[sender_id]["step"] = "choose_product"
        return True

    # ===== BƯỚC 2: CHỌN SẢN PHẨM =====
    if step == "choose_product":
        if "150" in text:
            user_data[sender_id]["product"] = "Loại đặc biệt 150k"
        else:
            user_data[sender_id]["product"] = "Loại 1 - 100k"

        send_message(sender_id, "Anh gửi giúp em SĐT nhận hàng:")
        user_data[sender_id]["step"] = "phone"
        return True

    # ===== BƯỚC 3: NHẬP SĐT =====
    if step == "phone":
        if is_phone(text):
            user_data[sender_id]["phone"] = text
            send_message(sender_id, "Anh gửi giúp em ĐỊA CHỈ nhận hàng:")
            user_data[sender_id]["step"] = "address"
        else:
            send_message(sender_id, "SĐT chưa đúng định dạng. Vui lòng nhập lại.")
        return True

    # ===== BƯỚC 4: NHẬP ĐỊA CHỈ =====
    if step == "address":
        user_data[sender_id]["address"] = text

        order = (
            f"📦 ĐƠN HÀNG MỚI\n"
            f"Sản phẩm: {user_data[sender_id]['product']}\n"
            f"SĐT: {user_data[sender_id]['phone']}\n"
            f"Địa chỉ: {text}\n"
            f"Thời gian: {datetime.now()}"
        )

        send_telegram(order)
        send_message(sender_id, "✅ Đã chốt đơn thành công. Shop sẽ gọi xác nhận ngay!")

        user_data[sender_id] = {}
        return True

    return False

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("object") != "page":
        return "ok"

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            if sender_id == PAGE_ID:
                continue

            if "message" in event:
                text = event["message"].get("text", "").strip().lower()

                # ===== CHỐNG SPAM (3s) =====
                now = time.time()
                if sender_id in last_message_time:
                    if now - last_message_time[sender_id] < 3:
                        return "ok"
                last_message_time[sender_id] = now

                # ===== KEYWORD KÍCH HOẠT FLOW =====
                if any(k in text for k in ["mua", "giá", "thuốc", "ship"]):
                    handled = handle_sale_flow(sender_id, text)
                    if handled:
                        continue

                # ===== NẾU ĐANG TRONG FLOW =====
                if sender_id in user_data:
                    handled = handle_sale_flow(sender_id, text)
                    if handled:
                        continue

                # ===== NGOÀI LUỒNG → AI =====
                reply = ai_reply(text)
                send_message(sender_id, reply)

    return "ok"

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

