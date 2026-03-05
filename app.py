import os
import requests
import re
import csv
import json
from datetime import datetime
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# ===== CONFIG =====
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== USER STATE =====
users = {}

# ===== SEND FB MESSAGE =====
def send_message(user_id, text):

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    data = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }

    requests.post(url, json=data)


# ===== TELEGRAM =====
def send_telegram(text):

    if not TELEGRAM_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }

    requests.post(url, json=payload)


# ===== SAVE CSV =====
def save_order(order):

    file = "orders.csv"

    exists = os.path.isfile(file)

    with open(file, "a", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        if not exists:
            writer.writerow(["time","name","phone","address","loai","soluong","total"])

        writer.writerow([
            datetime.now(),
            order["name"],
            order["phone"],
            order["address"],
            order["loai"],
            order["soluong"],
            order["total"]
        ])


# ===== PRICE =====
def get_price(loai):

    if loai == 1:
        return 120000

    if loai == 2:
        return 150000

    if loai == 3:
        return 180000

    return 0


# ===== AI OUTSIDE ANSWER =====
def ai_reply(question):

    try:

        prompt = f"""
Bạn là nhân viên bán thuốc lào Quảng Xương.

Bảng giá:
Loại 1: 120k/lạng
Loại 2: 150k/lạng
Loại 3: 180k/lạng

Trả lời ngắn gọn và cố gắng dẫn khách quay lại đặt hàng.

Câu hỏi khách:
{question}
"""

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )

        return res.choices[0].message.content

    except:
        return "Anh lấy loại mấy ạ?"


# ===== EXTRACT DATA =====
def extract_info(text):

    data = {}

    loai = re.search(r"loại\s*(\d)", text.lower())
    if loai:
        data["loai"] = int(loai.group(1))

    sl = re.search(r"(\d+)\s*lạng", text.lower())
    if sl:
        data["soluong"] = int(sl.group(1))

    phone = re.search(r"0\d{9}", text)
    if phone:
        data["phone"] = phone.group()

    return data


# ===== HANDLE ORDER FLOW =====
def handle_message(user_id, text):

    if user_id not in users:

        users[user_id] = {
            "step": "start"
        }

    state = users[user_id]

    info = extract_info(text)

    for k,v in info.items():
        state[k] = v

    step = state["step"]

    # ===== START =====
    if step == "start":

        send_message(user_id,
"""Chào bạn 👋

Thuốc lào Quảng Xương có:

Loại 1: 120k/lạng
Loại 2: 150k/lạng
Loại 3: 180k/lạng

Mua từ 3 lạng FREE SHIP 🚚

Bạn lấy loại mấy ạ?""")

        state["step"] = "ask_loai"
        return


    # ===== LOAI =====
    if step == "ask_loai":

        if "loai" not in state:

            send_message(user_id,"Bạn lấy loại 1 2 hay 3 ạ?")
            return

        send_message(user_id,"Bạn lấy mấy lạng ạ?")
        state["step"] = "ask_sl"
        return


    # ===== SOLUONG =====
    if step == "ask_sl":

        if "soluong" not in state:

            send_message(user_id,"Bạn lấy mấy lạng ạ?")
            return

        send_message(user_id,"Bạn cho mình xin tên người nhận")
        state["step"] = "ask_name"
        return


    # ===== NAME =====
    if step == "ask_name":

        if len(text) < 2:

            send_message(user_id,"Bạn nhập tên giúp mình")
            return

        state["name"] = text
        send_message(user_id,"Bạn cho mình xin số điện thoại")

        state["step"] = "ask_phone"
        return


    # ===== PHONE =====
    if step == "ask_phone":

        phone = re.search(r"0\d{9}", text)

        if not phone:

            send_message(user_id,"SĐT chưa đúng, bạn nhập lại giúp mình")
            return

        state["phone"] = phone.group()

        send_message(user_id,"Bạn gửi địa chỉ nhận hàng")

        state["step"] = "ask_address"
        return


    # ===== ADDRESS =====
    if step == "ask_address":

        state["address"] = text

        price = get_price(state["loai"])

        total = price * state["soluong"]

        msg = f"""
🎉 XÁC NHẬN ĐƠN 🎉

Tên: {state['name']}
SĐT: {state['phone']}
Địa chỉ: {state['address']}

{state['soluong']} lạng loại {state['loai']}

Tổng: {total}đ
"""

        send_message(user_id,msg)

        order = state.copy()
        order["total"] = total

        save_order(order)

        send_telegram(msg)

        users[user_id] = {"step":"start"}

        return


    # ===== OUTSIDE QUESTION =====
    reply = ai_reply(text)
    send_message(user_id,reply)



# ===== WEBHOOK VERIFY =====
@app.route("/", methods=["GET"])
def verify():

    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")

    return "wrong token"


# ===== WEBHOOK MESSAGE =====
@app.route("/", methods=["POST"])
def webhook():

    data = request.json

    if "entry" in data:

        for entry in data["entry"]:

            for messaging in entry.get("messaging", []):

                sender = messaging["sender"]["id"]

                if "message" in messaging:

                    text = messaging["message"].get("text","")

                    if text:
                        handle_message(sender,text)

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
