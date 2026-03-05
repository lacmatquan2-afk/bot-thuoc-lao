import os
import requests
import re
import csv
import time
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

# ================= CONFIG =================

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

PRICE = {
    "loại 1":120000,
    "loại 2":150000,
    "loại 3":180000
}

SHIP = 30000
FREE_SHIP = 3

users={}
last_reply={}

CSV_FILE="orders.csv"

# ================= SEND MESSAGE =================

def send_message(uid,text):

    url=f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    requests.post(url,json={
        "recipient":{"id":uid},
        "message":{"text":text}
    })

# ================= TELEGRAM =================

def send_telegram(text):

    if not TELEGRAM_BOT_TOKEN:
        return

    url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    requests.post(url,json={
        "chat_id":TELEGRAM_CHAT_ID,
        "text":text
    })

# ================= SAVE CSV =================

def save_order(order):

    exist=os.path.isfile(CSV_FILE)

    with open(CSV_FILE,"a",newline="",encoding="utf-8") as f:

        writer=csv.writer(f)

        if not exist:
            writer.writerow([
                "time","loai","soluong","tong","ten","sdt","diachi"
            ])

        writer.writerow(order)

# ================= DETECT =================

def detect_loai(text):

    if re.search(r'loai\s*1|loại\s*1|nhẹ|120k',text):
        return "loại 1"

    if re.search(r'loai\s*2|loại\s*2|vừa|150k',text):
        return "loại 2"

    if re.search(r'loai\s*3|loại\s*3|nặng|180k',text):
        return "loại 3"

    return None


def detect_quantity(text):

    lang=re.search(r'(\d+)\s*(lạng|lang)',text)

    kg=re.search(r'(\d+)\s*(kg|ký)',text)

    if kg:
        return int(kg.group(1))*10

    if lang:
        return int(lang.group(1))

    return None


def detect_phone(text):

    phone=re.findall(r'0\d{9}',text)

    if phone:
        return phone[0]

    return None


def detect_name(text):

    match=re.search(r'(?:tên|toi la|tôi là|em là|anh là)\s+([a-zA-ZÀ-ỹ\s]{2,40})',text)

    if match:
        return match.group(1).title()

    return None


def detect_address(text):

    if len(text)>10:
        return text

    return None

# ================= CALCULATE =================

def calculate(loai,soluong):

    total=PRICE[loai]*soluong

    if soluong>=FREE_SHIP:
        return total,0

    return total+SHIP,SHIP

# ================= KEYWORD REPLY =================

def keyword_reply(text):

    if re.search(r'phê|mạnh',text):
        return "Thuốc bên em phê mạnh và rất êm, không hồ không tẩm, chuẩn thuốc quê 100%."

    if re.search(r'ngon',text):
        return "Thuốc lào Quảng Định bên em rất đậm và êm, hút say nhưng không gắt."

    if re.search(r'nhiu|bao nhiêu|giá',text):
        return (
        "Giá thuốc lào:\n"
        "Loại 1:120k/lạng\n"
        "Loại 2:150k/lạng\n"
        "Loại 3:180k/lạng\n"
        "Mua 3 lạng free ship 🚀"
        )

    if re.search(r'ship',text):
        return "Bên em ship toàn quốc, mua từ 3 lạng free ship."

    return None

# ================= ORDER CHECK =================

def check_order(uid):

    state=users[uid]

    if all([
        state["loai"],
        state["soluong"],
        state["phone"],
        state["name"],
        state["address"]
    ]):

        total,ship=calculate(state["loai"],state["soluong"])

        ship_text="Free ship" if ship==0 else f"Ship {SHIP}"

        msg=(
        f"🎉 CHỐT ĐƠN 🎉\n"
        f"{state['soluong']} lạng {state['loai']}\n"
        f"{ship_text}\n"
        f"Tổng {total:,}đ\n\n"
        f"Tên: {state['name']}\n"
        f"SĐT: {state['phone']}\n"
        f"Địa chỉ: {state['address']}"
        )

        send_message(uid,msg)

        send_telegram(msg)

        save_order([
            datetime.now(),
            state["loai"],
            state["soluong"],
            total,
            state["name"],
            state["phone"],
            state["address"]
        ])

        users[uid]={
            "loai":None,
            "soluong":None,
            "phone":None,
            "address":None,
            "name":None
        }

        return True

    return False

# ================= COMMENT REPLY =================

def reply_comment(comment_id):

    url=f"https://graph.facebook.com/v18.0/{comment_id}/comments"

    requests.post(url,data={
        "message":"Bạn check inbox giúp mình nhé 📩",
        "access_token":PAGE_ACCESS_TOKEN
    })

# ================= WEBHOOK =================

@app.route("/webhook",methods=["POST"])
def webhook():

    data=request.get_json()

    if data.get("object")=="page":

        for entry in data["entry"]:

            if "changes" in entry:

                for change in entry["changes"]:

                    if change["field"]=="feed":

                        value=change["value"]

                        if value.get("comment_id"):

                            reply_comment(value["comment_id"])

            for event in entry.get("messaging",[]):

                if "message" not in event:
                    continue

                uid=event["sender"]["id"]

                text=event["message"].get("text","").lower()

                now=time.time()

                if uid in last_reply and now-last_reply[uid]<2:
                    return "OK",200

                last_reply[uid]=now

                if uid not in users:

                    users[uid]={
                        "loai":None,
                        "soluong":None,
                        "phone":None,
                        "address":None,
                        "name":None
                    }

                    send_message(uid,
                    "Chào bạn 👋\n"
                    "Thuốc lào Quảng Định nhà em êm say không hồ không tẩm.\n\n"
                    "Loại 1:120k\n"
                    "Loại 2:150k\n"
                    "Loại 3:180k\n\n"
                    "Bạn lấy loại mấy ạ?"
                    )

                    return "OK",200

                state=users[uid]

                state["loai"]=detect_loai(text) or state["loai"]
                state["soluong"]=detect_quantity(text) or state["soluong"]
                state["phone"]=detect_phone(text) or state["phone"]
                state["name"]=detect_name(text) or state["name"]
                state["address"]=detect_address(text) or state["address"]

                if check_order(uid):
                    return "OK",200

                reply=keyword_reply(text)

                if reply:
                    send_message(uid,reply)

                elif not state["loai"]:
                    send_message(uid,"Bạn lấy loại 1 2 hay 3 ạ?")

                elif not state["soluong"]:
                    send_message(uid,"Bạn lấy mấy lạng ạ?")

                elif not state["name"]:
                    send_message(uid,"Bạn cho mình xin tên người nhận.")

                elif not state["phone"]:
                    send_message(uid,"Bạn gửi giúp mình số điện thoại.")

                elif not state["address"]:
                    send_message(uid,"Bạn gửi giúp mình địa chỉ nhận hàng.")

    return "OK",200

# ================= VERIFY =================

@app.route("/webhook",methods=["GET"])
def verify():

    if request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge")

    return "verify token sai"

# ================= HOME =================

@app.route("/")
def home():
    return "BOT THUỐC LÀO PRO RUNNING"

# ================= RUN =================

if __name__=="__main__":

    port=int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0",port=port)
