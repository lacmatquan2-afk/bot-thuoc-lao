import os
import re
import requests
from datetime import datetime
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

# ================= CONFIG =================
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}
last_post_date = None

# ================= HELPER =================
def send_message(psid, text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    requests.post(url, json=payload)

def reply_comment(comment_id, text):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={"message": text})

def send_telegram(text):
    if TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        requests.post(url, data=payload)

def auto_post():
    global last_post_date
    today = datetime.now().date()

    if last_post_date == today:
        return

    message = (
        "🔥 THUỐC LÀO QUẢNG ĐỊNH CHÍNH GỐC 🔥\n\n"
        "✔ Loại 1: 100k\n"
        "✔ Loại đặc biệt: 150k\n\n"
        "Ship toàn quốc 🚚\n"
        "Comment 'mua' để được tư vấn ngay!"
    )

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, data={"message": message})

    last_post_date = today

def is_phone(text):
    return re.fullmatch(r"0\d{9}", text)

def ai_reply(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                 "Bạn là nhân viên bán thuốc lào Quảng Định. "
                 "Giá 100k và 150k. "
                 "Ưu tiên upsell loại 150k. "
                 "Trả lời ngắn gọn, chốt đơn khéo léo."},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Anh quan tâm loại 100k hay 150k ạ?"

# ================= HOME =================
@app.route("/")
def home():
    auto_post()
    return "KING MAXIMUM V5 TITAN MODE 👑 ĐANG HOẠT ĐỘNG"

# ================= PRIVACY =================
@app.route("/privacy")
def privacy():
    return """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>Privacy Policy</title>
</head>
<body>
<h1>Chính sách quyền riêng tư</h1>
<p>Bot dùng để trả lời tin nhắn và xử lý đơn hàng.</p>
<ul>
<li>Loại 1: 100.000 VNĐ</li>
<li>Loại đặc biệt: 150.000 VNĐ</li>
</ul>
<p>Dữ liệu chỉ dùng để giao hàng.</p>
</body>
</html>"""

# ================= DATA DELETE =================
@app.route("/data-deletion")
def delete():
    return "<h1>Yêu cầu xóa dữ liệu: gửi email về lacmatquan2@gmail.com</h1>"

# ================= VERIFY =================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verification failed", 403

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=true) or {}

    if data.get("object") != "page":
        return "ok"

    for entry in data.get("entry", []):

        # ===== Messenger =====
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            if sender_id == PAGE_ID:
                continue

            if "message" in event:
                text = event["message"].get("text", "").strip()

                if sender_id not in user_data:
                    user_data[sender_id] = {}

                # AUTO detect phone
                if is_phone(text):
                    user_data[sender_id]["phone"] = text
                    send_message(sender_id, "Anh gửi giúp em ĐỊA CHỈ nhận hàng:")
                    user_data[sender_id]["step"] = "address"
                    continue

                # ADDRESS step
                if user_data[sender_id].get("step") == "address":
                    user_data[sender_id]["address"] = text

                    order = (
                        f"📦 ĐƠN HÀNG TITAN\n"
                        f"SĐT: {user_data[sender_id].get('phone')}\n"
                        f"Địa chỉ: {text}\n"
                        f"Thời gian: {datetime.now()}"
                    )

                    send_telegram(order)
                    send_message(sender_id, "✅ Đã chốt đơn thành công.")
                    user_data[sender_id] = {}
                    continue

                # AI MODE
                reply = ai_reply(text)
                send_message(sender_id, reply)

        # ===== COMMENT AUTO =====
        for change in entry.get("changes", []):
            if change.get("field") == "feed":
                value = change.get("value", {})
                comment_id = value.get("comment_id")
                message = value.get("message", "").lower()
                from_id = value.get("from", {}).get("id")

                if from_id == PAGE_ID:
                    continue

                if any(word in message for word in ["giá", "bao nhiêu", "mua"]):
                    reply_comment(comment_id,
                        "Giá 100k & 150k. Shop đã inbox tư vấn chi tiết 🔥")

    return "ok"

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT"), 10000)
    app.run(host="0.0.0.0", port=port)

