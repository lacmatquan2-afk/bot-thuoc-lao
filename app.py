import os
import requests
import re
import csv
import json
from datetime import datetime
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

user_state = {}

# ===== gửi tin nhắn =====
def send_message(user_id, text):

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }

    requests.post(url, json=payload)

# ===== gửi telegram =====
def send_telegram(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }

    requests.post(url, json=payload)

# ===== lưu csv =====
def save_order(order):

    file = "orders.csv"

    exists = os.path.isfile(file)

    with open(file, "a", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        if not exists:
            writer.writerow(["time","name","phone","address","loai","soluong","tong"])

        writer.writerow([
            datetime.now(),
            order["name"],
            order["phone"],
            order["address"],
            order["loai"],
            order["soluong"],
            order["tong"]
        ])

# ===== AI extract order =====
def ai_extract(text):

    prompt = f"""
    trích xuất thông tin đơn hàng từ tin nhắn:

    {text}

    trả về json:

    loai
    soluong
    name
    phone
    address
    """

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    try:
        data = json.loads(r.choices[0].message.content)
        return data
    except:
        return {}

# ===== giá =====
def get_price(loai):

    if loai == 1:
        return 120000

    if loai == 2:
        return 150000

    if loai == 3:
        return 180000

    return 0

# ===== xử lý tin nhắn =====
def handle_message(user_id, text):

    if user_id not in user_state:
        user_state[user_id] = {}

    state = user_state[user_id]

    data = ai_extract(text)

    if "loai" in data:
        state["loai"] = int(data["loai"])

    if "soluong" in data:
        state["soluong"] = int(data["soluong"])

    if "name" in data:
        state["name"] = data["name"]

    if "phone" in data:
        state["phone"] = data["phone"]

    if "address" in data:
        state["address"] = data["address"]

    if "loai" not in state:

        send_message(user_id,
        """Thuốc lào Quảng Xương có:

Loại 1: 120k/lạng
Loại 2: 150k/lạng
Loại 3: 180k/lạng

Bạn lấy loại mấy ạ?""")

        return

    if "soluong" not in state:

        send_message(user_id,"Bạn lấy mấy lạng ạ?")

        return

    if "name" not in state:

        send_message(user_id,"Bạn cho mình xin tên người nhận")

        return

    if "phone" not in state:

        send_message(user_id,"Bạn cho mình xin số điện thoại")

        return

    if "address" not in state:

        send_message(user_id,"Bạn gửi giúp địa chỉ nhận hàng")

        return

    price = get_price(state["loai"])

    tong = price * state["soluong"]

    msg = f"""
🎉 XÁC NHẬN ĐƠN 🎉

Tên: {state['name']}
SĐT: {state['phone']}
Địa chỉ: {state['address']}

{state['soluong']} lạng loại {state['loai']}

Tổng: {tong}
"""

    send_message(user_id,msg)

    order = state.copy()
    order["tong"] = tong

    save_order(order)

    send_telegram(msg)

    user_state[user_id] = {}

# ===== webhook =====
@app.route("/", methods=["GET"])

def verify():

    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")

    return "error"

@app.route("/", methods=["POST"])

def webhook():

    data = request.json

    if "entry" in data:

        for entry in data["entry"]:

            for messaging in entry.get("messaging", []):

                sender = messaging["sender"]["id"]

                if "message" in messaging:

                    text = messaging["message"].get("text","")

                    handle_message(sender,text)

    return "ok"

if __name__ == "__main__":
    app.run()
