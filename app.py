import os
import requests
import re
from flask import Flask, request

app = Flask(__name__)

# ===== CONFIG =====
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GRAPH_URL = "https://graph.facebook.com/v18.0/me/messages"

orders = {}

# ===== SEND MESSAGE =====
def send_message(psid, text):
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }

    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }

    requests.post(GRAPH_URL, params=params, json=payload)


# ===== TELEGRAM =====
def send_telegram(msg):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }

    requests.post(url, data=data)


# ===== KEYWORD REPLY =====
def auto_reply(text):

    text = text.lower()

    if "thuốc ngon ko" in text or "ngon ko" in text:
        return "Thuốc lào Quảng Định chuẩn quê 100% hút êm và rất đậm."

    if "phê ko" in text:
        return "Thuốc lào nhà em hút rất phê và say nhé anh."

    if "nhiêu 1 lạng" in text or "bao nhiêu" in text or "thuốc nhiêu" in text:
        return """
Thuốc lào Quảng Định có 3 loại

Loại nhẹ: 120k / lạng  
Loại vừa: 150k / lạng  
Loại nặng: 180k / lạng

Anh lấy loại nào em gửi nhé.
"""

    if "ship" in text:
        return "Bên em có hỗ trợ ship COD toàn quốc nhé."

    return None


# ===== ORDER BOT =====
def handle_order(psid, text):

    if psid not in orders:
        orders[psid] = {"step": 0}

    step = orders[psid]["step"]

    if step == 0:
        orders[psid]["name"] = text
        orders[psid]["step"] = 1
        return "Anh cho em xin số điện thoại nhận hàng."

    elif step == 1:
        orders[psid]["phone"] = text
        orders[psid]["step"] = 2
        return "Anh gửi giúp em địa chỉ nhận hàng."

    elif step == 2:

        orders[psid]["address"] = text

        name = orders[psid]["name"]
        phone = orders[psid]["phone"]
        address = orders[psid]["address"]

        msg = f"""
ĐƠN HÀNG MỚI

Tên: {name}
SĐT: {phone}
Địa chỉ: {address}
"""

        send_telegram(msg)

        orders.pop(psid)

        return "Em đã nhận đơn. Bên em sẽ gửi hàng sớm nhất."



# ===== WEBHOOK VERIFY =====
@app.route("/webhook", methods=["GET"])
def verify():

    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge

    return "Error"


# ===== RECEIVE MESSAGE =====
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    if "entry" in data:

        for entry in data["entry"]:

            if "messaging" in entry:

                for event in entry["messaging"]:

                    if "message" in event:

                        sender = event["sender"]["id"]
                        text = event["message"].get("text", "")

                        # greeting
                        if text.lower() in ["hi", "hello", "alo", "chào"]:
                            send_message(sender,
                            """Chào bạn đã đến với thuốc lào Quảng Định.

Thuốc lào nhà em êm say không hồ không tẩm đúng nguyên chất 100%.

Thuốc có 3 loại

120k / lạng
150k / lạng
180k / lạng

Bạn cần tư vấn hay đặt hàng cứ nhắn nhé."""
                            )
                            continue


                        # auto reply
                        reply = auto_reply(text)

                        if reply:
                            send_message(sender, reply)
                            continue


                        # order
                        reply = handle_order(sender, text)

                        send_message(sender, reply)


    return "ok", 200


# ===== RUN SERVER =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
