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

INTRO_MESSAGE = (
    "🔥 ĐẶC SẢN THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
    "Êm – Say – Không hồ – Không tẩm – Không pha trộn\n"
    "Cam kết thuốc sạch chuẩn gốc Quảng Định 🚀\n\n"
    "• Nhẹ 120k\n"
    "• Vừa 150k\n"
    "• Nặng 180k\n"
    "Từ 3 lạng FREE SHIP 🚀\n"
    "Anh cho shop xin:\n"
    "- Loại (nhẹ/vừa/nặng)\n"
    "- Số lượng (bao nhiêu lạng)\n"
    "- SĐT\n"
    "- Địa chỉ nhận hàng\n"
)

# ================== AUTO POST 8H ==================

POST_IMAGES = [
    "https://i.imgur.com/yourimage1.jpg",
    "https://i.imgur.com/yourimage2.jpg",
    "https://i.imgur.com/yourimage3.jpg"
]

def generate_random_post():
    text_random = random.choice([
        "Hàng mới phơi sáng nay 🔥",
        "Mẻ này cực êm và đằm 💨",
        "Thuốc khô giòn, đúng chuẩn Quảng Định 🚀",
        "Hàng chọn lọc kỹ từng lá 🔥"
    ])

    scarcity = random.randint(15, 40)

    content = (
        f"🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n\n"
        f"{text_random}\n"
        f"Hôm nay còn khoảng {scarcity}kg.\n\n"
        f"• Nhẹ 120k\n"
        f"• Vừa 150k\n"
        f"• Nặng 180k\n"
        f"Từ 3 lạng FREE SHIP 🚀\n\n"
        f"Inbox ngay giữ hàng!"
    )

    image = random.choice(POST_IMAGES)
    return content, image

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

# ================== REGEX ==================
def detect_quantity(text):
    kg = re.search(r'(\d+)\s*(kg|ký)', text)
    lang = re.search(r'(\d+)\s*(lạng|lang)', text)
    if kg:
        return int(kg.group(1)) * 10
    if lang:
        return int(lang.group(1))
    return None

def detect_phone(text):
    m = re.search(r'0\d{9,10}', text)
    return m.group() if m else None

def detect_address(text):
    keywords = ["đường", "xã", "huyện", "tỉnh", "thôn", "phường", "quận"]
    if any(k in text for k in keywords) and len(text) > 10:
        return text
    return None

def detect_loai(text):
    if "nhẹ" in text or "120" in text:
        return "nhẹ"
    if "vừa" in text or "150" in text:
        return "vừa"
    if "nặng" in text or "180" in text:
        return "nặng"
    return None

# ================== AI CHỈ TRẢ LỜI NGOÀI LUỒNG ==================
def ai_chat_reply(user_message):
    if not client:
        return None
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.8,
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là người bán thuốc lào. Trả lời ngắn gọn, lịch sự. Sau đó luôn kéo khách quay lại việc chọn loại và số lượng."
                },
                {"role": "user", "content": user_message}
            ]
        )
        return res.choices[0].message.content.strip()
    except:
        return None

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data["entry"]:
            if "messaging" not in entry:
                continue

            for event in entry["messaging"]:
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
                        "intro_sent": False
                    }

                state = user_data[sender]

                if not state["intro_sent"]:
                    send_message(sender, INTRO_MESSAGE)
                    state["intro_sent"] = True

                # FORM CỨNG
                state["loai"] = detect_loai(text) or state["loai"]
                state["soluong"] = detect_quantity(text) or state["soluong"]
                state["phone"] = detect_phone(text) or state["phone"]
                state["address"] = detect_address(text) or state["address"]

                # ===== CHỐT ĐƠN CỨNG =====
                if state["loai"] and state["soluong"] and state["phone"] and state["address"]:
                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    confirm_text = (
                        f"🎉 XÁC NHẬN ĐƠN 🎉\n"
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

                    user_data[sender] = {
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None,
                        "intro_sent": True
                    }
                    continue

                # ===== NGOÀI LUỒNG MỚI DÙNG AI =====
                if not (detect_loai(text) or detect_quantity(text) or detect_phone(text)):
                    ai_reply = ai_chat_reply(text)
                    if ai_reply:
                        send_message(sender, ai_reply)

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
