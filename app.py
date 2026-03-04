import os
import requests
import re
import csv
import json
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

PRICE = {"nhẹ": 120000, "vừa": 150000, "nặng": 180000}
SHIP_FEE = 30000
FREE_SHIP_FROM = 3

user_data = {}
CSV_FILE = "orders.csv"

# ================== AUTO POST ==================

POST_IMAGES = [
    "https://i.imgur.com/yourimage1.jpg",
    "https://i.imgur.com/yourimage2.jpg",
    "https://i.imgur.com/yourimage3.jpg"
]

def generate_random_post():
    scarcity = random.randint(15, 40)
    content = (
        f"🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n\n"
        f"Hôm nay còn khoảng {scarcity}kg.\n"
        f"• Nhẹ 120k\n"
        f"• Vừa 150k\n"
        f"• Nặng 180k\n"
        f"Từ 3 lạng FREE SHIP 🚀\n"
        f"Inbox ngay giữ hàng!"
    )
    return content, random.choice(POST_IMAGES)

def auto_post():
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return
    message, image_url = generate_random_post()
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"
    requests.post(url, data={
        "url": image_url,
        "caption": message,
        "access_token": PAGE_ACCESS_TOKEN
    })

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post, "cron", hour=8, minute=0)
scheduler.start()

# ===== Anti Sleep =====
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
            writer.writerow(["Time", "Loai", "SoLuong(lạng)", "Tong", "SDT", "DiaChi"])
        writer.writerow(order)

# ================== CALCULATE ==================
def calculate_total(loai, soluong):
    total = PRICE[loai] * soluong
    if soluong >= FREE_SHIP_FROM:
        return total, 0
    return total + SHIP_FEE, SHIP_FEE

# ================== DETECT ==================

def is_price_question(text):
    keywords = [
        "bao nhiêu tiền",
        "nhiu tiền",
        "giá sao",
        "giá",
        "bao nhiêu 1 lạng",
        "1 lạng bao nhiêu"
    ]
    return any(k in text for k in keywords)

def detect_quantity(text):
    kg = re.search(r'(\d+(?:\.\d+)?)\s*(kg|ký)', text)
    lang = re.search(r'(\d+)\s*(lạng|lang)', text)
    if kg:
        return int(float(kg.group(1)) * 10)
    if lang:
        return int(lang.group(1))
    return None

def detect_phone(text):
    m = re.search(r'0\d{9,10}', text)
    return m.group() if m else None

def detect_name(text):
    patterns = [
        r"(?:tên|toi ten|tôi tên|mình tên|mình là|toi la|tôi là)\s+([a-zA-ZÀ-ỹ\s]+)"
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1).strip().title()

    if 1 <= len(text.split()) <= 3 and text.replace(" ", "").isalpha():
        return text.strip().title()
    return None

def detect_address(text):
    if len(text) > 15:
        return text
    if re.search(r'\d+.*(đường|xã|huyện|tỉnh|quận|thôn|ấp)', text):
        return text
    return None

def detect_loai(text):
    if "120" in text or "nhẹ" in text:
        return "nhẹ"
    if "150" in text or "vừa" in text:
        return "vừa"
    if "180" in text or "nặng" in text:
        return "nặng"
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
                text = event["message"].get("text", "").lower()

                if sender not in user_data:
                    user_data[sender] = {
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None,
                        "name": None,
                        "intro_sent": False,
                        "last_reply": ""
                    }

                state = user_data[sender]

                # ===== CHÀO 1 LẦN =====
                if not state["intro_sent"]:
                    welcome = (
                        "Chào bạn đã đến với Thuốc Lào Quảng Định của chúng tôi 👋\n"
                        "• Nhẹ 120k\n• Vừa 150k\n• Nặng 180k\n"
                        "Từ 3 lạng FREE SHIP 🚀"
                    )
                    send_message(sender, welcome)
                    state["intro_sent"] = True
                    state["last_reply"] = welcome
                    return "OK", 200

                # ===== HỎI GIÁ =====
                if is_price_question(text):
                    reply = (
                        "Giá hiện tại:\n"
                        "• Nhẹ: 120k / lạng\n"
                        "• Vừa: 150k / lạng\n"
                        "• Nặng: 180k / lạng\n"
                        "Từ 3 lạng FREE SHIP 🚀"
                    )
                    if state["last_reply"] != reply:
                        send_message(sender, reply)
                        state["last_reply"] = reply
                    return "OK", 200

                # ===== NHẬN DIỆN INFO =====
                state["loai"] = detect_loai(text) or state["loai"]
                state["soluong"] = detect_quantity(text) or state["soluong"]
                state["phone"] = detect_phone(text) or state["phone"]
                state["address"] = detect_address(text) or state["address"]
                state["name"] = detect_name(text) or state["name"]

                # ===== THIẾU INFO → HỎI LẠI =====
                if not state["loai"]:
                    send_message(sender, "Anh lấy loại nhẹ, vừa hay nặng ạ?")
                    return "OK", 200
                if not state["soluong"]:
                    send_message(sender, "Anh lấy bao nhiêu lạng hoặc kg ạ?")
                    return "OK", 200
                if not state["name"]:
                    send_message(sender, "Anh cho shop xin họ tên ạ?")
                    return "OK", 200
                if not state["phone"]:
                    send_message(sender, "Anh cho shop xin số điện thoại nhận hàng ạ?")
                    return "OK", 200
                if not state["address"]:
                    send_message(sender, "Anh cho shop xin địa chỉ nhận hàng chi tiết ạ?")
                    return "OK", 200

                # ===== ĐỦ INFO → TẠO ĐƠN =====
                total, ship = calculate_total(state["loai"], state["soluong"])
                ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                confirm_text = (
                    f"🎉 XÁC NHẬN ĐƠN 🎉\n"
                    f"Tên: {state['name']}\n"
                    f"{state['soluong']} lạng {state['loai']}\n"
                    f"{ship_text}\n"
                    f"Tổng: {total:,}đ\n"
                    f"Giao 2-4 ngày 🚚"
                )

                send_message(sender, confirm_text)

                save_order([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    state["loai"],
                    state["soluong"],
                    total,
                    state["phone"],
                    state["address"]
                ])

                send_telegram(confirm_text)

                # reset nhưng giữ intro
                user_data[sender] = {
                    "loai": None,
                    "soluong": None,
                    "phone": None,
                    "address": None,
                    "name": None,
                    "intro_sent": True,
                    "last_reply": ""
                }

    return "OK", 200

# ================== VERIFY ==================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verify token sai"

@app.route("/")
def home():
    return "BOT AI PRO đang chạy 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
