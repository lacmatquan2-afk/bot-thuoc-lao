import os
import requests
import re
import csv
import random
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
import threading
import time

app = Flask(__name__)

# ================== CONFIG ==================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

PRICE = {"loại 1": 120000, "loại 2": 150000, "loại 3": 180000}
TYPE_MAP = {
    "120": "loại 1",
    "150": "loại 2",
    "180": "loại 3",
    "nhẹ": "loại 1",
    "vừa": "loại 2",
    "nặng": "loại 3",
    "1": "loại 1",
    "2": "loại 2",
    "3": "loại 3",
}
SHIP_FEE = 30000
FREE_SHIP_FROM = 3

user_data = {}
CSV_FILE = "orders.csv"

# ================== AUTO POST ==================

def auto_post():
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return
    content = (
        "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
        "• Loại 1: 120k/lạng\n"
        "• Loại 2: 150k/lạng\n"
        "• Loại 3: 180k/lạng\n"
        "Từ 3 lạng FREE SHIP 🚀"
    )
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    requests.post(url, data={
        "message": content,
        "access_token": PAGE_ACCESS_TOKEN
    })

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post, "cron", hour=8)
scheduler.start()

# ================== ANTI SLEEP ==================
def keep_alive():
    while True:
        try:
            requests.get("https://bot-thuoc-lao.onrender.com/")
        except:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive, daemon=True).start()

# ================== SEND FB ==================
def send_message(uid, text):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={
        "recipient": {"id": uid},
        "message": {"text": text}
    })

# ================== TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

# ================== SAVE CSV ==================
def save_order(order):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Time","Loai","SoLuong(lạng)","Tong","Ten","SDT","DiaChi"])
        writer.writerow(order)

# ================== CALCULATE ==================
def calculate_total(loai, soluong):
    total = PRICE[loai] * soluong
    if soluong >= FREE_SHIP_FROM:
        return total, 0
    return total + SHIP_FEE, SHIP_FEE

# ================== DETECT ==================
def detect_quantity(text):
    kg = re.search(r'(\d+(?:\.\d+)?)\s*(kg|ký)', text)
    lang = re.search(r'(\d+)\s*(lạng)', text)
    if kg:
        return int(float(kg.group(1)) * 10)
    if lang:
        return int(lang.group(1))
    return None

def detect_phone(text):
    m = re.search(r'0\d{9,10}', text)
    return m.group() if m else None

def detect_name(text):
    match = re.search(r"(?:tên|tôi là|toi la|mình là)\s+([a-zA-ZÀ-ỹ\s]+)", text)
    if match:
        return match.group(1).strip().title()
    return None

def detect_address(text):
    if len(text) > 15 and any(k in text for k in ["đường","xã","huyện","tỉnh","quận","thôn","ấp"]):
        return text
    return None

def detect_loai(text):
    for key in TYPE_MAP:
        if key in text:
            return TYPE_MAP[key]
    return None

def is_price_question(text):
    return any(k in text for k in ["bao nhiêu","giá","nhiu tiền","bao tiền"])

# ================== OPENAI TRẢ LỜI NGOÀI LUỒNG ==================
def ai_reply(text):
    if not client:
        return None
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": """Bạn là nhân viên bán thuốc lào Quảng Định.
Thuốc êm, say, không hồ, không tẩm, không pha trộn.
Tư vấn nhiệt tình, chăm sóc khách chu đáo.
Nếu khách hỏi ngon không, có sạch không thì khẳng định thuốc chuẩn gốc.
Luôn hướng khách về đặt hàng."""
                },
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content
    except:
        return None

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                if "message" not in event:
                    continue

                sender = event["sender"]["id"]
                text = event["message"].get("text","").lower()

                if sender not in user_data:
                    user_data[sender] = {
                        "loai":None,"soluong":None,"phone":None,
                        "address":None,"name":None,"intro_sent":False
                    }

                state = user_data[sender]

                # ===== CHÀO ĐẦU =====
                if not state["intro_sent"]:
                    welcome = (
                        "🔥 ĐẶC SẢN THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
                        "Êm, say, không hồ không tẩm không pha trộn.\n"
                        "Cam kết thuốc sạch chuẩn gốc Quảng Định.\n\n"
                        "Thuốc nhà em gồm 3 loại:\n"
                        "• Loại 1: 120k / 1 lạng\n"
                        "• Loại 2: 150k / 1 lạng\n"
                        "• Loại 3: 180k / 1 lạng\n"
                        "Mua từ 3 lạng FREE SHIP 🚀"
                    )
                    send_message(sender, welcome)
                    state["intro_sent"] = True
                    return "OK",200

                # ===== NHẬN DIỆN =====
                state["loai"] = detect_loai(text) or state["loai"]
                state["soluong"] = detect_quantity(text) or state["soluong"]
                state["phone"] = detect_phone(text) or state["phone"]
                state["address"] = detect_address(text) or state["address"]
                state["name"] = detect_name(text) or state["name"]

                # ===== KIỂM TRA ĐỦ INFO =====
if all([state["loai"], state["soluong"], state["phone"], state["address"], state["name"]]):

    # Chuẩn hóa lại loại và giá
    loai = state["loai"]
    gia_mot_lang = PRICE.get(loai, 0)

    # Nhận diện lại theo giá
    if gia_mot_lang == 120000:
        loai_text = "Loại 1 (120k/lạng)"
    elif gia_mot_lang == 150000:
        loai_text = "Loại 2 (150k/lạng)"
    elif gia_mot_lang == 180000:
        loai_text = "Loại 3 (180k/lạng)"
    else:
        loai_text = loai

    total, ship = calculate_total(loai, state["soluong"])
    ship_text = "Miễn phí ship" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

    # ===== Nội dung chốt đơn gửi khách =====
    confirm = (
        f"🎉 CHỐT ĐƠN THÀNH CÔNG 🎉\n\n"
        f"Họ tên: {state['name']}\n"
        f"SĐT: {state['phone']}\n"
        f"Địa chỉ: {state['address']}\n\n"
        f"Sản phẩm: {state['soluong']} lạng {loai_text}\n"
        f"{ship_text}\n"
        f"Tổng thanh toán: {total:,}đ\n\n"
        f"✅ Bên em sẽ liên hệ giao hàng sớm nhất.\n"
        f"Cảm ơn anh/chị đã ủng hộ Thuốc Lào Quảng Định 🙏"
    )

    send_message(sender, confirm)

    # ===== Lưu CSV =====
    save_order([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        loai_text,
        state["soluong"],
        total,
        state["name"],
        state["phone"],
        state["address"]
    ])

    # ===== Gửi Telegram đầy đủ thông tin =====
    telegram_text = (
        f"🚨 ĐƠN HÀNG MỚI 🚨\n\n"
        f"Họ tên: {state['name']}\n"
        f"SĐT: {state['phone']}\n"
        f"Địa chỉ: {state['address']}\n\n"
        f"Sản phẩm: {state['soluong']} lạng {loai_text}\n"
        f"Phí ship: {ship_text}\n"
        f"Tổng tiền: {total:,}đ"
    )

    send_telegram(telegram_text)

    # Reset trạng thái sau khi chốt
    user_data[sender] = {
        "loai": None,
        "soluong": None,
        "phone": None,
        "address": None,
        "name": None,
        "intro_sent": True
    }

                    total, ship = calculate_total(state["loai"],state["soluong"])
                    ship_text = "Miễn phí ship" if ship==0 else f"Ship {SHIP_FEE:,}đ"

                    confirm = (
                        f"🎉 XÁC NHẬN ĐƠN 🎉\n"
                        f"Tên: {state['name']}\n"
                        f"SĐT: {state['phone']}\n"
                        f"Địa chỉ: {state['address']}\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ"
                    )

                    send_message(sender, confirm)

                    save_order([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        state["loai"],
                        state["soluong"],
                        total,
                        state["name"],
                        state["phone"],
                        state["address"]
                    ])

                    send_telegram(confirm)

                    user_data[sender] = {
                        "loai":None,"soluong":None,
                        "phone":None,"address":None,
                        "name":None,"intro_sent":True
                    }

                else:
                    reply = ai_reply(text)
                    if reply:
                        send_message(sender, reply)

    return "OK",200

# ================== VERIFY ==================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verify token sai"

@app.route("/")
def home():
    return "BOT AI PRO đang chạy 🚀"

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)

