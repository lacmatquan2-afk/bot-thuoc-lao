import os
import requests
import re
import csv
import json
import time
import threading
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

app = Flask(__name__)

# ================= CONFIG =================

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

PRICE = {
    "loại 1":120000,
    "loại 2":150000,
    "loại 3":180000
}

SHIP = 30000
FREE_SHIP = 3

CSV_FILE="orders.csv"

users={}
last_message={}

# ================= AUTO POST =================

def auto_post():

    if not PAGE_ACCESS_TOKEN:
        return

    msg=(
        "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n\n"
        "Loại 1:120k/lạng\n"
        "Loại 2:150k/lạng\n"
        "Loại 3:180k/lạng\n\n"
        "Mua 3 lạng FREE SHIP 🚀\n"
        "Inbox đặt hàng ngay!"
    )

    url=f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

    try:
        requests.post(url,data={
            "message":msg,
            "access_token":PAGE_ACCESS_TOKEN
        })
    except:
        pass

scheduler=BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post,"cron",hour=8)
scheduler.start()

# ================= ANTI SLEEP =================

def keep_alive():

    while True:
        try:
            requests.get("https://bot-thuoc-lao.onrender.com/")
        except:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive,daemon=True).start()

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

    try:
        requests.post(url,json={
            "chat_id":TELEGRAM_CHAT_ID,
            "text":text
        })
    except:
        pass

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

    if re.search(r'loai\s*1|loại\s*1|\b1\b|120k|nhẹ',text):
        return "loại 1"

    if re.search(r'loai\s*2|loại\s*2|\b2\b|150k|vừa',text):
        return "loại 2"

    if re.search(r'loai\s*3|loại\s*3|\b3\b|180k|nặng',text):
        return "loại 3"

    return None


def detect_quantity(text):

    kg=re.search(r'(\d+(?:\.\d+)?)\s*(kg|ký)',text)

    lang=re.search(r'(\d+)\s*(lạng|lang)',text)

    if kg:
        return int(float(kg.group(1))*10)

    if lang:
        return int(lang.group(1))

    return None


def detect_phone(text):

    phone=re.findall(r'0\d[\d\s\.]{8,12}',text)

    if phone:
        return re.sub(r'\D','',phone[0])

    return None


def detect_name(text):

    match=re.search(r'(?:tên|toi la|tôi là|em là|anh là)\s+([a-zA-ZÀ-ỹ\s]{2,40})',text)

    if match:
        return match.group(1).title()

    return None


def detect_address(text):

    if len(text)>8:
        return text

    return None

# ================= CALCULATE =================

def calculate(loai,soluong):

    total=PRICE[loai]*soluong

    if soluong>=FREE_SHIP:
        return total,0

    return total+SHIP,SHIP

# ================= AI OUTSIDE =================

def ai_reply(text):

    if not client:
        return None

    try:

        res=client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {
                    "role":"system",
                    "content":
                    "Bạn là nhân viên bán thuốc lào Quảng Định. "
                    "Chỉ trả lời câu hỏi của khách và luôn hướng khách đặt hàng."
                },
                {"role":"user","content":text}
            ]
        )

        return res.choices[0].message.content

    except:
        return None

# ================= CHECK ORDER =================

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

        ship_text="Miễn phí ship" if ship==0 else f"Ship {SHIP}"

        msg=(
            f"🎉 XÁC NHẬN ĐƠN 🎉\n"
            f"Tên: {state['name']}\n"
            f"SĐT: {state['phone']}\n"
            f"Địa chỉ: {state['address']}\n\n"
            f"{state['soluong']} lạng {state['loai']}\n"
            f"{ship_text}\n"
            f"Tổng: {total:,}đ"
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
            "phone":None,
            "address":None,
            "name":None
        }

        return True

    return False

# ================= FOLLOW UP =================

def follow_up():

    now=time.time()

    for uid in last_message:

        if now-last_message[uid]>300:

            send_message(uid,
                "Anh vẫn cần thuốc lào không ạ?\n"
                "Hôm nay bên em free ship từ 3 lạng 🚀"
            )

            last_message[uid]=now

scheduler.add_job(follow_up,"interval",minutes=5)

# ================= COMMENT AUTO =================

def reply_comment(comment_id):

    url=f"https://graph.facebook.com/v18.0/{comment_id}/comments"

    try:
        requests.post(url,data={
            "message":"Bạn check inbox giúp mình nhé 📩",
            "access_token":PAGE_ACCESS_TOKEN
        })
    except:
        pass

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

                sender=event["sender"]["id"]

                text=event["message"].get("text","").lower()

                last_message[sender]=time.time()

                if sender not in users:

                    users[sender]={
                        "loai":None,
                        "soluong":None,
                        "phone":None,
                        "address":None,
                        "name":None
                    }

                    send_message(
                        sender,
                        "Chào bạn 👋\n"
                        "Thuốc lào Quảng Định có:\n"
                        "Loại 1:120k\n"
                        "Loại 2:150k\n"
                        "Loại 3:180k\n\n"
                        "Bạn lấy loại mấy ạ?"
                    )

                    continue

                state=users[sender]

                state["loai"]=detect_loai(text) or state["loai"]
                state["soluong"]=detect_quantity(text) or state["soluong"]
                state["phone"]=detect_phone(text) or state["phone"]
                state["name"]=detect_name(text) or state["name"]
                state["address"]=detect_address(text) or state["address"]

                if check_order(sender):
                    continue

                if not state["loai"]:
                    send_message(sender,"Bạn lấy loại 1 2 hay 3 ạ?")
                    continue

                if not state["soluong"]:
                    send_message(sender,"Bạn lấy mấy lạng ạ?")
                    continue

                if not state["name"]:
                    send_message(sender,"Bạn cho mình xin tên người nhận")
                    continue

                if not state["phone"]:
                    send_message(sender,"Bạn gửi giúp mình số điện thoại")
                    continue

                if not state["address"]:
                    send_message(sender,"Bạn gửi giúp mình địa chỉ nhận hàng")
                    continue

                reply=ai_reply(text)

                if reply:
                    send_message(sender,reply)

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
    return "BOT AI PRO MAX RUNNING 🚀"

if __name__=="__main__":

    port=int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0",port=port)
