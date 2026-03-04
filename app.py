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

def reply_comment(comment_id, text):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    requests.post(url, data={
        "message": text,
        "access_token": PAGE_ACCESS_TOKEN
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
            writer.writerow(["Time", "Loai", "SoLuong(lạng)", "Tong", "Ten", "SDT", "DiaChi"])
        writer.writerow(order)

# ================== CALCULATE ==================
def calculate_total(loai, soluong):
    total = PRICE[loai] * soluong
    if soluong >= FREE_SHIP_FROM:
        return total, 0
    return total + SHIP_FEE, SHIP_FEE

# ================== OPENAI TRẢ LỜI NGOÀI LUỒNG ==================
def ask_openai(user_text):
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là nhân viên bán thuốc lào, trả lời ngắn gọn, lịch sự."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content
    except:
        return None

# ================== DETECT ==================
def is_price_question(text):
    keywords = ["bao nhiêu tiền","nhiu tiền","giá sao","giá"]
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
    if 1 <= len(text.split()) <= 3 and text.replace(" ", "").isalpha():
        return text.strip().title()
    return None

def detect_address(text):
    if len(text) > 15:
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

    # ===== XỬ LÝ COMMENT =====
    if data.get("object") == "page":
        for entry in data["entry"]:

            # COMMENT
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        value = change["value"]
                        if value.get("item") == "comment":
                            comment_text = value.get("message","")
                            comment_id = value.get("comment_id")
                            ai_reply = ask_openai(comment_text)
                            if ai_reply:
                                reply_comment(comment_id, ai_reply)

            # INBOX
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
                        "last_reply": "",
                        "order_done": False
                    }

                state = user_data[sender]

                if state.get("order_done"):
                    return "OK", 200

                # CHÀO
                if not state["intro_sent"]:
                    welcome = (
                        "Chào bạn đã đến với Thuốc Lào Quảng Định 👋\n"
                        "• Nhẹ 120k\n• Vừa 150k\n• Nặng 180k\n"
                        "Từ 3 lạng FREE SHIP 🚀"
                    )
                    send_message(sender, welcome)
                    state["intro_sent"] = True
                    return "OK", 200

                # Detect thông tin
                state["loai"] = detect_loai(text) or state["loai"]
                state["soluong"] = detect_quantity(text) or state["soluong"]
                state["phone"] = detect_phone(text) or state["phone"]
                state["address"] = detect_address(text) or state["address"]
                state["name"] = detect_name(text) or state["name"]

                # Nếu chưa đủ info → dùng OpenAI trả lời
                if not all([state["loai"], state["soluong"], state["phone"], state["address"], state["name"]]):
                    ai_reply = ask_openai(text)
                    if ai_reply:
                        send_message(sender, ai_reply)
                    return "OK", 200

                # ĐỦ INFO → CHỐT
                total, ship = calculate_total(state["loai"], state["soluong"])
                confirm_text = (
                    f"🎉 CHỐT ĐƠN 🎉\n"
                    f"Tên: {state['name']}\n"
                    f"SĐT: {state['phone']}\n"
                    f"Địa chỉ: {state['address']}\n"
                    f"{state['soluong']} lạng {state['loai']}\n"
                    f"Tổng: {total:,}đ\n"
                    f"Cảm ơn anh/chị đã ủng hộ 🙏"
                )

                send_message(sender, confirm_text)
                send_telegram(confirm_text)

                save_order([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    state["loai"],
                    state["soluong"],
                    total,
                    state["name"],
                    state["phone"],
                    state["address"]
                ])

                state["order_done"] = True

    return "OK", 200


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
