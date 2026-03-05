import os
import requests
import re
from flask import Flask, request

app = Flask(__name__)

# ================= CONFIG =================

PAGE_ACCESS_TOKEN = "PAGE_ACCESS_TOKEN"
VERIFY_TOKEN = "VERIFY_TOKEN"

TELEGRAM_TOKEN = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "CHAT_ID"

# lưu thông tin khách
customers = {}

# ================= HÀM GỬI TIN NHẮN =================

def send_message(psid, text):

    url = "https://graph.facebook.com/v18.0/me/messages"

    params = {"access_token": PAGE_ACCESS_TOKEN}

    headers = {"Content-Type": "application/json"}

    data = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }

    requests.post(url, params=params, headers=headers, json=data)

# ================= GỬI TELEGRAM =================

def send_telegram(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }

    requests.post(url, data=data)

# ================= NHẬN DIỆN TỪ KHÓA =================

def detect_question(msg):

    msg = msg.lower()

    if "thuốc phê ko" in msg:
        return "phê"

    if "thuốc ngon ko" in msg or "ngon ko" in msg:
        return "ngon"

    if "nhiu 1 lạng" in msg or "nhiêu 1 lạng" in msg or "thuốc nhiêu" in msg:
        return "giá"

    if "free ship ko" in msg:
        return "ship"

    return None


# ================= XỬ LÝ TIN NHẮN =================

def handle_message(psid, msg):

    global customers

    if psid not in customers:

        customers[psid] = {
            "name": "",
            "phone": "",
            "address": ""
        }

        send_message(psid,
        """Chào bạn đã đến với Thuốc Lào Quảng Định

Thuốc lào nhà em:
êm say
không hồ
không tẩm
đúng nguyên chất
không pha tạp
hàng chuẩn quê 100%

Bên em có 3 loại:

Loại nhẹ: 120k / lạng  
Loại vừa: 150k / lạng  
Loại nặng: 180k / lạng  

Anh chị muốn đặt loại nào ạ?""")

        return

    question = detect_question(msg)

    if question == "phê":

        send_message(psid,
        "Thuốc bên em êm say phê đều anh nhé, hàng nguyên chất không pha tạp.")

    elif question == "ngon":

        send_message(psid,
        "Thuốc lào Quảng Định chuẩn quê 100% hút rất đậm và thơm.")

    elif question == "giá":

        send_message(psid,
        """Giá thuốc bên em:

Loại nhẹ: 120k / lạng
Loại vừa: 150k / lạng
Loại nặng: 180k / lạng

Anh muốn lấy loại nào ạ?""")

    elif question == "ship":

        send_message(psid,
        "Bên em có hỗ trợ ship COD toàn quốc anh nhé.")

    # nhận diện SĐT
    phone = re.findall(r'\d{9,11}', msg)

    if phone:

        customers[psid]["phone"] = phone[0]

        send_message(psid, "Anh gửi giúp em địa chỉ nhận hàng với ạ")

        return

    # nhận diện địa chỉ
    if len(msg) > 10 and customers[psid]["phone"] != "" and customers[psid]["address"] == "":

        customers[psid]["address"] = msg

        order_text = f"""
ĐƠN HÀNG MỚI

SĐT: {customers[psid]['phone']}
Địa chỉ: {customers[psid]['address']}
"""

        send_telegram(order_text)

        send_message(psid,
        "Em đã nhận đơn. Bên em sẽ gửi hàng sớm nhất cho anh ạ.")

# ================= WEBHOOK =================

@app.route("/webhook", methods=["GET"])
def verify():

    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge

    return "error"

@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    if "entry" in data:

        for entry in data["entry"]:

            for messaging in entry["messaging"]:

                if "message" in messaging:

                    psid = messaging["sender"]["id"]

                    msg = messaging["message"].get("text")

                    if msg:

                        handle_message(psid, msg)

    return "ok", 200


# ================= TRẢ LỜI COMMENT =================

def reply_comment(comment_id, text):

    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"

    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "message": text
    }

    requests.post(url, params=params)

# ================= CHẠY SERVER =================

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000)
