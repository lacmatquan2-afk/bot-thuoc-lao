from flask import Flask, request
import requests
import os

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

# ===============================
# HÀM GỬI TIN NHẮN
# ===============================
def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    requests.post(url, json=payload)


# ===============================
# TRANG CHỦ (Render kiểm tra sống)
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "Bot thuốc lào Quảng Định đang chạy!"


# ===============================
# XÁC THỰC WEBHOOK FACEBOOK
# ===============================
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Sai verify token"


# ===============================
# NHẬN TIN NHẮN TỪ FACEBOOK
# ===============================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "entry" in data:
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event:
                    user_message = messaging_event["message"].get("text", "")
                    handle_message(sender_id, user_message)

    return "ok", 200


# ===============================
# XỬ LÝ NỘI DUNG TIN NHẮN
# ===============================
def handle_message(sender_id, message):
    text = message.lower()

    # --- Khi khách hỏi giá ---
    if "giá" in text or "bao nhiêu" in text:
        reply = """Dạ bên em có 2 loại thuốc lào Quảng Định:

🔥 Loại thường: 90.000đ / 1 lạng
🔥 Loại đặc biệt: 150.000đ / 1 lạng

Anh muốn chọn loại nào và lấy bao nhiêu lạng để em lên đơn ạ?
Ship toàn quốc.
Liên hệ: 0868862907"""
        
        send_message(sender_id, reply)
        return

    # --- Khi khách muốn đặt ---
    if "đặt" in text or "lấy" in text:
        reply = """Dạ anh cho em xin:

- Loại (90k hay 150k)
- Số lạng
- Địa chỉ nhận hàng
- Số điện thoại

Em sẽ xác nhận đơn ngay ạ.
Hotline: 0868862907"""
        
        send_message(sender_id, reply)
        return

    # --- Tin nhắn mặc định ---
    reply = """Chào anh 👋

Bên em chuyên thuốc lào Quảng Định chính hãng.

🔥 Loại thường: 90.000đ / lạng
🔥 Loại đặc biệt: 150.000đ / lạng

Anh cần tư vấn hay đặt hàng ạ?
Gọi ngay: 0868862907"""

    send_message(sender_id, reply)


# ===============================
# CHẠY SERVER
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

