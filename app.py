import os
import requests
import re
import csv
import json
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
)

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

# ================== REGEX DETECT ==================
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

# ================== AI PARSE ==================
def ai_extract_info(text):
    if not client:
        return {}

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Trích xuất thông tin đơn hàng từ tin nhắn.
Trả về JSON:
{
"name": "...",
"phone": "...",
"address": "...",
"quantity": số,
"type": "nhẹ/vừa/nặng"
}
Nếu không có thì để null.
"""
                },
                {"role": "user", "content": text}
            ]
        )
        content = res.choices[0].message.content
        return json.loads(content)
    except:
        return {}

# ================== AUTO POST ==================
def auto_post():
    if not PAGE_ID or not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    requests.post(url, data={
        "message": INTRO_MESSAGE,
        "access_token": PAGE_ACCESS_TOKEN
    })

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post, "cron", hour=8, minute=0)
scheduler.start()

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
                        "name": None,
                        "intro_sent": False
                    }

                state = user_data[sender]

                if not state["intro_sent"]:
                    send_message(sender, INTRO_MESSAGE)
                    state["intro_sent"] = True

                # ===== REGEX NHẬN DIỆN =====
                loai = detect_loai(text)
                qty = detect_quantity(text)
                phone = detect_phone(text)
                address = detect_address(text)

                if loai:
                    state["loai"] = loai

                if qty:
                    state["soluong"] = qty

                if phone:
                    state["phone"] = phone

                if address:
                    state["address"] = address

                # ===== AI NHẬN DIỆN BỔ SUNG =====
                ai_data = ai_extract_info(text)

                if ai_data.get("type"):
                    state["loai"] = ai_data["type"]

                if ai_data.get("quantity"):
                    state["soluong"] = ai_data["quantity"]

                if ai_data.get("phone"):
                    state["phone"] = ai_data["phone"]

                if ai_data.get("address"):
                    state["address"] = ai_data["address"]

                if ai_data.get("name"):
                    state["name"] = ai_data["name"]

                # ===== CHỐT ĐƠN =====
                if state["loai"] and state["soluong"] and state["phone"] and state["address"]:
                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(
                        sender,
                        f"🎉 CẢM ƠN ANH/CHỊ ĐÃ TIN TƯỞNG SHOP QUANG ANH 🎉\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ\n"
                        "Đơn sẽ được giao trong 2-4 ngày tùy khu vực 🚚"
                    )

                    order_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        state["loai"],
                        state["soluong"],
                        total,
                        state["phone"],
                        state["address"]
                    ]

                    save_order(order_row)

                    send_telegram(
                        f"🔥 ĐƠN MỚI 🔥\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"Tổng: {total:,}đ\n"
                        f"SĐT: {state['phone']}\n"
                        f"Địa chỉ: {state['address']}"
                    )

                    user_data[sender] = {
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None,
                        "name": None,
                        "intro_sent": True
                    }
                    continue

                # Nếu chưa đủ → gợi ý tiếp
                if not state["loai"]:
                    send_message(sender, "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?")
                elif not state["soluong"]:
                    send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                else:
                    send_message(sender, "Anh/chị gửi giúp em HỌ TÊN + ĐỊA CHỈ + SĐT để em chốt đơn ạ 🚀")

    return "OK", 200

# ================== VERIFY ==================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verify token sai"

@app.route("/")
def home():
    return "BOT FULL PRO đang chạy 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
