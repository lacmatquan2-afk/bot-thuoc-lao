import os
import requests
import re
import time
from flask import Flask, request

app = Flask(__name__)

# ===== CONFIG =====
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GRAPH_URL = "https://graph.facebook.com/v18.0/me/messages"

orders = {}
last_reply = {}

# ===== SEND MESSAGE =====
def send_message(psid, text):

    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }

    params = {"access_token": PAGE_ACCESS_TOKEN}

    requests.post(GRAPH_URL, params=params, json=payload)


# ===== TELEGRAM =====
def send_telegram(msg):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }

    requests.post(url, data=data)


# ===== ANTI SPAM =====
def anti_spam(psid):

    now = time.time()

    if psid in last_reply:

        if now - last_reply[psid] < 3:
            return True

    last_reply[psid] = now
    return False


# ===== KEYWORD BOT =====
def auto_reply(text):

    text = text.lower()

    if any(x in text for x in ["thuốc ngon", "ngon ko", "thuốc ngon ko"]):
        return "Thuốc lào Quảng Định chuẩn quê 100%, hút êm, say và rất đậm."

    if any(x in text for x in ["phê ko", "phê không", "say ko"]):
        return "Thuốc nhà em hút rất phê và say nhé anh."

    if any(x in text for x in ["bao nhiêu", "nhiêu 1 lạng", "thuốc nhiêu", "giá"]):
        return """
Thuốc lào Quảng Định có 3 loại

Loại nhẹ: 120k / lạng
Loại vừa: 150k / lạng
Loại nặng: 180k / lạng

Anh lấy loại nào em gửi nhé.
"""

    if "ship" in text:
        return "Bên em hỗ trợ ship COD toàn quốc nhé."

    if any(x in text for x in ["đặt", "mua", "lấy"]):
        return "Anh cho em xin tên người nhận."

    return None


# ===== ORDER BOT =====
def handle_order(psid, text):

    if psid not in orders:
        orders[psid] = {"step": 0}

    step = orders[psid]["step"]

    # STEP 1 NAME
    if step == 0:

        orders[psid]["name"] = text
        orders[psid]["step"] = 1

        return "Anh cho em xin số điện thoại nhận hàng."

    # STEP 2 PHONE
    elif step == 1:

        phone = re.sub(r"\D", "", text)

        if len(phone) < 9:
            return "Anh gửi đúng số điện thoại giúp em."

        orders[psid]["phone"] = phone
        orders[psid]["step"] = 2

        return "Anh gửi giúp em địa chỉ nhận hàng."

    # STEP 3 ADDRESS
    elif step == 2:

        orders[psid]["address"] = text

        name = orders[psid]["name"]
        phone = orders[psid]["phone"]
        address = orders[psid]["address"]

        msg = f"""
🔥 ĐƠN HÀNG THUỐC LÀO

👤 Tên: {name}
📞 SĐT: {phone}
📍 Địa chỉ: {address}
"""

        send_telegram(msg)

        orders.pop(psid)

        return "✅ Em đã nhận đơn. Bên em sẽ gửi hàng sớm nhất."


# ===== VERIFY =====
@app.route("/webhook", methods=["GET"])
def verify():

    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge

    return "Error"


# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    if "entry" in data:

        for entry in data["entry"]:

            # ===== MESSAGE =====
            if "messaging" in entry:

                for event in entry["messaging"]:

                    if "message" in event:

                        sender = event["sender"]["id"]
                        text = event["message"].get("text", "")

                        if anti_spam(sender):
                            return "ok", 200

                        # GREETING
                        if text.lower() in ["hi", "hello", "alo", "chào"]:

                            send_message(sender,
"""Chào bạn đã đến với thuốc lào Quảng Định.

Thuốc lào nhà em êm say không hồ không tẩm đúng nguyên chất không pha tạp hàng chuẩn quê 100%.

Thuốc có 3 loại

Loại nhẹ 120k
Loại vừa 150k
Loại nặng 180k

Bạn cần tư vấn hay đặt hàng cứ nhắn nhé."""
                            )
                            continue

                        # AUTO REPLY
                        reply = auto_reply(text)

                        if reply:
                            send_message(sender, reply)
                            continue

                        # ORDER
                        reply = handle_order(sender, text)

                        send_message(sender, reply)

            # ===== COMMENT =====
            if "changes" in entry:

                for change in entry["changes"]:

                    if change["field"] == "feed":

                        value = change["value"]

                        if "comment_id" in value:

                            comment = value.get("message", "")
                            user_id = value.get("from", {}).get("id")

                            if comment:

                                reply = auto_reply(comment)

                                if reply:
                                    send_message(user_id, reply)

    return "ok", 200


# ===== RUN =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
