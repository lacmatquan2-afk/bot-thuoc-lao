import os
import re
import csv
import time
import requests
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ================= CONFIG =================

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CSV_FILE="orders.csv"

PRICE={
"loai1":120000,
"loai2":150000,
"loai3":180000
}

SHIP=30000
FREE_SHIP=3

users={}
last_reply={}

# ================= SEND MESSAGE =================

def send_message(uid,text):

    if last_reply.get(uid)==text:
        return

    url=f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    requests.post(url,json={
        "recipient":{"id":uid},
        "message":{"text":text}
    })

    last_reply[uid]=text


# ================= TELEGRAM =================

def send_telegram(msg):

    if not TELEGRAM_BOT_TOKEN:
        return

    url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    requests.post(url,json={
        "chat_id":TELEGRAM_CHAT_ID,
        "text":msg
    })


# ================= SAVE ORDER =================

def save_order(order):

    exist=os.path.isfile(CSV_FILE)

    with open(CSV_FILE,"a",newline="",encoding="utf8") as f:

        writer=csv.writer(f)

        if not exist:
            writer.writerow([
                "time","loai","soluong","tong","ten","sdt","diachi"
            ])

        writer.writerow(order)


# ================= DETECT =================

def detect_loai(text):

    if re.search(r'loai\s*1|loại\s*1|120k|nhẹ',text):
        return "loai1"

    if re.search(r'loai\s*2|loại\s*2|150k|vừa',text):
        return "loai2"

    if re.search(r'loai\s*3|loại\s*3|180k|nặng|mạnh',text):
        return "loai3"

    return None


def detect_quantity(text):

    kg=re.search(r'(\d+)\s*(kg|ký)',text)

    lang=re.search(r'(\d+)\s*(lạng|lang)',text)

    if kg:
        return int(kg.group(1))*10

    if lang:
        return int(lang.group(1))

    return None


def detect_phone(text):

    phone=re.findall(r'0\d{9,10}',text)

    if phone:
        return phone[0]

    return None


def detect_name(text):

    match=re.search(r'(tên|tôi là|toi la|em là|anh là)\s+([a-zA-ZÀ-ỹ\s]{2,40})',text)

    if match:
        return match.group(2).title()

    return None


def detect_address(text):

    if any(x in text for x in ["thôn","xã","huyện","tỉnh","đường","phố","tp","hà nội","sài gòn","hcm"]):
        return text

    return None


# ================= CALCULATE =================

def calculate(loai,soluong):

    total=PRICE[loai]*soluong

    if soluong>=FREE_SHIP:
        return total,0

    return total+SHIP,SHIP


# ================= CHECK ORDER =================

def check_order(uid):

    state=users[uid]

    if not all([
        state["loai"],
        state["soluong"],
        state["name"],
        state["phone"],
        state["address"]
    ]):
        return False

    total,ship=calculate(state["loai"],state["soluong"])

    ship_text="FREE SHIP" if ship==0 else f"{SHIP}đ"

    msg=(
    f"🎉 XÁC NHẬN ĐƠN\n\n"
    f"{state['soluong']} lạng {state['loai']}\n"
    f"Tổng tiền: {total:,}đ\n\n"
    f"Tên: {state['name']}\n"
    f"SĐT: {state['phone']}\n"
    f"Địa chỉ: {state['address']}"
    )

    send_message(uid,msg)
    send_telegram(msg)

    save_order([
    datetime.now().strftime("%Y-%m-%d %H:%M"),
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
    "name":None,
    "phone":None,
    "address":None
    }

    return True


# ================= COMMENT REPLY =================

def reply_comment(comment_id):

    url=f"https://graph.facebook.com/v18.0/{comment_id}/comments"

    requests.post(url,data={
    "message":"Shop đã inbox bạn nhé 📩",
    "access_token":PAGE_ACCESS_TOKEN
    })


# ================= AUTO POST =================

def auto_post():

    msg=(
    "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n\n"
    "Loại 1:120k\n"
    "Loại 2:150k\n"
    "Loại 3:180k\n\n"
    "Mua 3 lạng FREE SHIP 🚀"
    )

    url=f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

    requests.post(url,data={
    "message":msg,
    "access_token":PAGE_ACCESS_TOKEN
    })


scheduler=BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post,"cron",hour=8)
scheduler.start()


# ================= WEBHOOK =================

@app.route("/webhook",methods=["POST"])
def webhook():

    data=request.get_json()

    if data.get("object")!="page":
        return "ok"

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

            if uid not in users:

                users[uid]={
                "loai":None,
                "soluong":None,
                "name":None,
                "phone":None,
                "address":None
                }

                send_message(uid,
                "Chào bạn 👋\n"
                "Thuốc lào Quảng Định:\n"
                "Loại 1:120k\n"
                "Loại 2:150k\n"
                "Loại 3:180k\n\n"
                "Bạn lấy loại mấy ạ?"
                )

                continue

            state=users[uid]

            state["loai"]=detect_loai(text) or state["loai"]
            state["soluong"]=detect_quantity(text) or state["soluong"]
            state["phone"]=detect_phone(text) or state["phone"]
            state["name"]=detect_name(text) or state["name"]
            state["address"]=detect_address(text) or state["address"]

            if check_order(uid):
                continue

            if not state["loai"]:
                send_message(uid,"Bạn lấy loại 1 2 hay 3 ạ?")
                continue

            if not state["soluong"]:
                send_message(uid,"Bạn lấy mấy lạng ạ?")
                continue

            if not state["name"]:
                send_message(uid,"Bạn cho mình xin tên người nhận")
                continue

            if not state["phone"]:
                send_message(uid,"Bạn gửi giúp mình số điện thoại")
                continue

            if not state["address"]:
                send_message(uid,"Bạn gửi giúp mình địa chỉ nhận hàng")
                continue

    return "OK",200


# ================= VERIFY =================

@app.route("/webhook",methods=["GET"])
def verify():

    if request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge")

    return "verify token sai"


@app.route("/")
def home():
    return "BOT THUỐC LÀO PRO MAX RUNNING 🚀"


if __name__=="__main__":

    port=int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0",port=port)
