import os
import requests
import re
import csv
from flask import Flask, request
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ================= CONFIG =================

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CSV_FILE = "orders.csv"

PRICE = {
    "loai1":120000,
    "loai2":150000,
    "loai3":180000
}

SHIP = 30000
FREE_SHIP = 3

user_data = {}

# ================= SEND FB =================

def send_message(uid,text):

    url=f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    requests.post(url,json={
        "recipient":{"id":uid},
        "message":{"text":text}
    })


# ================= TELEGRAM =================

def send_telegram(msg):

    if not TELEGRAM_TOKEN:
        return

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url,json={
        "chat_id":TELEGRAM_CHAT_ID,
        "text":msg
    })


# ================= SAVE ORDER =================

def save_order(data):

    file_exist=os.path.isfile(CSV_FILE)

    with open(CSV_FILE,"a",newline="",encoding="utf8") as f:

        writer=csv.writer(f)

        if not file_exist:
            writer.writerow([
                "time","loai","soluong","ten","sdt","diachi"
            ])

        writer.writerow(data)


# ================= AUTO POST =================

def auto_post():

    content=(
    "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n\n"
    "Thuốc lào nhà em êm say không hồ không tẩm\n"
    "đúng nguyên chất không pha tạp\n"
    "hàng chuẩn quê 100%\n\n"
    "Loại 1: 120k/lạng\n"
    "Loại 2: 150k/lạng\n"
    "Loại 3: 180k/lạng\n\n"
    "Mua 3 lạng FREE SHIP 🚀\n"
    "Comment hoặc inbox để đặt hàng"
    )

    url=f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

    requests.post(url,data={
        "message":content,
        "access_token":PAGE_ACCESS_TOKEN
    })


scheduler=BackgroundScheduler()
scheduler.add_job(auto_post,"cron",hour=8)
scheduler.start()


# ================= DETECT TEXT =================

def detect_loai(text):

    if "nhẹ" in text or "loại 1" in text:
        return "loai1"

    if "vừa" in text or "loại 2" in text:
        return "loai2"

    if "nặng" in text or "loại 3" in text:
        return "loai3"

    return None


def detect_quantity(text):

    lang=re.search(r'(\d+)\s*lạng',text)

    if lang:
        return int(lang.group(1))

    kg=re.search(r'(\d+)\s*kg',text)

    if kg:
        return int(kg.group(1))*10

    return None


def detect_phone(text):

    phone=re.findall(r'0\d{9}',text)

    if phone:
        return phone[0]

    return None


# ================= COMMENT REPLY =================

def reply_comment(comment_id):

    url=f"https://graph.facebook.com/v18.0/{comment_id}/comments"

    requests.post(url,data={
        "message":"Bạn check inbox giúp mình nhé 📩",
        "access_token":PAGE_ACCESS_TOKEN
    })


# ================= FAQ =================

def faq_answer(text):

    if "thuốc phê" in text or "ngon ko" in text:

        return(
        "Thuốc lào Quảng Định bên em êm say\n"
        "không hồ không tẩm\n"
        "nguyên chất 100% nhé anh"
        )

    if "nhiu 1 lạng" in text or "nhiêu 1 lạng" in text or "thuốc nhiêu" in text:

        return(
        "Thuốc nhà em có 3 loại:\n"
        "Loại nhẹ 120k/lạng\n"
        "Loại vừa 150k/lạng\n"
        "Loại nặng 180k/lạng"
        )

    if "free ship" in text:

        return(
        "Bên em free ship khi mua từ 3 lạng trở lên 🚚"
        )

    return None


# ================= WEBHOOK =================

@app.route("/webhook",methods=["POST"])
def webhook():

    data=request.get_json()

    if data["object"]=="page":

        for entry in data["entry"]:

            # COMMENT
            if "changes" in entry:

                for change in entry["changes"]:

                    if change["field"]=="feed":

                        value=change["value"]

                        if "comment_id" in value:

                            reply_comment(value["comment_id"])

                            send_message(
                                value["from"]["id"],
                                "Chào bạn đã đến với thuốc lào Quảng Định.\n"
                                "Thuốc lào nhà em êm say không hồ không tẩm\n"
                                "đúng nguyên chất không pha tạp\n"
                                "hàng chuẩn quê 100%\n\n"
                                "Thuốc có 3 loại:\n"
                                "Loại nhẹ 120k\n"
                                "Loại vừa 150k\n"
                                "Loại nặng 180k\n\n"
                                "Bạn cần loại nào ạ?"
                            )

            # MESSAGE
            for event in entry.get("messaging",[]):

                if "message" not in event:
                    continue

                sender=event["sender"]["id"]
                text=event["message"].get("text","").lower()

                if sender not in user_data:

                    user_data[sender]={
                        "step":0,
                        "loai":None,
                        "soluong":None,
                        "phone":None,
                        "address":None,
                        "name":None
                    }

                state=user_data[sender]

                # FAQ
                faq=faq_answer(text)

                if faq:
                    send_message(sender,faq)
                    return "OK",200


                if state["step"]==0:

                    send_message(sender,"Bạn lấy loại nhẹ vừa hay nặng ạ?")
                    state["step"]=1
                    return "OK",200


                if state["step"]==1:

                    loai=detect_loai(text)

                    if loai:

                        state["loai"]=loai
                        send_message(sender,"Bạn lấy mấy lạng ạ?")
                        state["step"]=2

                    else:
                        send_message(sender,"Bạn chọn nhẹ vừa hay nặng ạ")

                    return "OK",200


                if state["step"]==2:

                    qty=detect_quantity(text)

                    if qty:

                        state["soluong"]=qty
                        send_message(sender,"Bạn cho mình xin tên người nhận")
                        state["step"]=3

                    return "OK",200


                if state["step"]==3:

                    state["name"]=text
                    send_message(sender,"Bạn gửi số điện thoại giúp mình")
                    state["step"]=4
                    return "OK",200


                if state["step"]==4:

                    phone=detect_phone(text)

                    if phone:

                        state["phone"]=phone
                        send_message(sender,"Bạn gửi địa chỉ nhận hàng")
                        state["step"]=5

                    return "OK",200


                if state["step"]==5:

                    state["address"]=text

                    order=(
                    f"ĐƠN HÀNG MỚI\n"
                    f"{state['name']}\n"
                    f"{state['phone']}\n"
                    f"{state['address']}\n"
                    f"{state['soluong']} lạng {state['loai']}"
                    )

                    send_message(sender,"Đơn hàng đã ghi nhận ✅")
                    send_telegram(order)

                    save_order([
                        datetime.now(),
                        state["loai"],
                        state["soluong"],
                        state["name"],
                        state["phone"],
                        state["address"]
                    ])

                    user_data[sender]={"step":0}

    return "OK",200


# ================= VERIFY =================

@app.route("/webhook",methods=["GET"])
def verify():

    if request.args.get("hub.verify_token")==VERIFY_TOKEN:

        return request.args.get("hub.challenge")

    return "token sai"


# ================= HOME =================

@app.route("/")
def home():

    return "BOT THUOC LAO DANG CHAY"


if __name__=="__main__":

    port=int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)
