import os
import requests
import re
import csv
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
)

# ================== SEND FB MESSAGE ==================
def send_message(uid, text):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={
        "recipient": {"id": uid},
        "message": {"text": text}
    })

# ================== REPLY COMMENT ==================
def reply_comment(comment_id, message):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    requests.post(url, data={
        "message": message,
        "access_token": PAGE_ACCESS_TOKEN
    })

# ================== SEND TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

# ================== SAVE ORDER CSV ==================
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
def detect_quantity(text):
    kg_match = re.search(r'(\d+)\s*(kg|ký)', text)
    lang_match = re.search(r'(\d+)\s*(lạng|lang)', text)

    if kg_match:
        qty = int(kg_match.group(1)) * 10
        if 1 <= qty <= 100:
            return qty

    if lang_match:
        qty = int(lang_match.group(1))
        if 1 <= qty <= 100:
            return qty

    return None

def detect_phone(text):
    match = re.search(r'0\d{9,10}', text)
    return match.group() if match else None

def detect_address(text):
    keywords = ["đường", "xã", "huyện", "tỉnh", "thôn", "phường", "quận"]
    if any(k in text for k in keywords) and len(text) > 10:
        return text
    return None

def detect_name(text):
    if len(text.split()) >= 2 and not detect_phone(text) and not detect_quantity(text):
        return text.title()
    return None

# ================== AI REPLY ==================
def ai_reply(text):
    if not client:
        return "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?"
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Bạn là nhân viên bán thuốc lào Quảng Định.
Luôn kéo khách về trọng tâm mua hàng và chốt đơn.
"""
                },
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content
    except:
        return "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?"

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
                        "intro_sent": False,
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None,
                        "name": None
                    }

                state = user_data[sender]

                # ===== INTRO CHỈ GỬI 1 LẦN =====
                if not state["intro_sent"]:
                    send_message(sender, INTRO_MESSAGE)
                    state["intro_sent"] = True

                # ===== NHẬN DIỆN LOẠI =====
                if any(x in text for x in ["nhẹ", "120"]):
                    state["loai"] = "nhẹ"

                if any(x in text for x in ["vừa", "150"]):
                    state["loai"] = "vừa"

                if any(x in text for x in ["nặng", "180"]):
                    state["loai"] = "nặng"

                # Nếu đã có loại nhưng chưa có số lượng
                if state["loai"] and not state["soluong"]:
                    qty = detect_quantity(text)
                    if qty:
                        state["soluong"] = qty
                    else:
                        send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                        continue

                # Nếu chưa có loại
                if not state["loai"]:
                    send_message(sender, "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?")
                    continue

                # Nếu đã có loại + số lượng nhưng thiếu thông tin giao hàng
                if state["loai"] and state["soluong"]:

                    if not state["name"]:
                        name = detect_name(text)
                        if name:
                            state["name"] = name
                        else:
                            send_message(sender, "Anh/chị gửi giúp em họ tên ạ?")
                            continue

                    if not state["phone"]:
                        phone = detect_phone(text)
                        if phone:
                            state["phone"] = phone
                        else:
                            send_message(sender, "Anh/chị gửi giúp em số điện thoại ạ?")
                            continue

                    if not state["address"]:
                        address = detect_address(text)
                        if address:
                            state["address"] = address
                        else:
                            send_message(sender, "Anh/chị gửi giúp em địa chỉ cụ thể ạ?")
                            continue

                # ===== CHỐT ĐƠN =====
                if all([
                    state["loai"],
                    state["soluong"],
                    state["phone"],
                    state["address"],
                    state["name"]
                ]):

                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(sender,
                        f"🎉 Cảm ơn anh/chị {state['name']} đã tin tưởng shop Quang Anh của chúng tôi ❤️\n\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ\n\n"
                        "Đơn sẽ được giao trong 2-4 ngày 🚚"
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
                        f"Tên: {state['name']}\n"
                        f"Loại: {state['loai']}\n"
                        f"Số lượng: {state['soluong']} lạng\n"
                        f"Tổng: {total:,}đ\n"
                        f"SĐT: {state['phone']}\n"
                        f"Địa chỉ: {state['address']}"
                    )

                    user_data[sender] = {
                        "intro_sent": True,
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None,
                        "name": None
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
    return "BOT FULL PRO đang chạy 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
