import os
import requests
import re
import csv
from datetime import datetime
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

# ================== CONFIG ==================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
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
    "• Nặng 180k\n\n"
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

# ================== SEND TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

# ================== SAVE ORDER ==================
def save_order(order):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Time", "HoTen", "Loai", "SoLuong", "Tong", "SDT", "DiaChi"])
        writer.writerow(order)

# ================== DETECT ==================
def detect_quantity(text):
    match = re.search(r'(\d+)', text)
    if match:
        qty = int(match.group(1))
        if 1 <= qty <= 100:
            return qty
    return None

def detect_phone(text):
    match = re.search(r'0\d{9,10}', text)
    return match.group() if match else None

def detect_address(text):
    keywords = ["đường", "xã", "huyện", "tỉnh", "thôn", "phường", "quận"]
    if any(k in text for k in keywords):
        return text
    return None

def detect_name(text):
    if len(text.split()) >= 2 and not detect_phone(text):
        return text.title()
    return None

def calculate_total(loai, soluong):
    total = PRICE[loai] * soluong
    if soluong >= FREE_SHIP_FROM:
        return total, 0
    return total + SHIP_FEE, SHIP_FEE

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
                        "name": None,
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None
                    }

                state = user_data[sender]

                # ===== INTRO CHỈ GỬI 1 LẦN =====
                if not state["intro_sent"]:
                    send_message(sender, INTRO_MESSAGE)
                    state["intro_sent"] = True

                # ===== NHẬN DIỆN LOẠI =====
                if "nhẹ" in text or "120" in text:
                    state["loai"] = "nhẹ"

                if "vừa" in text or "150" in text:
                    state["loai"] = "vừa"

                if "nặng" in text or "180" in text:
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

                # Nếu đã có loại + số lượng nhưng thiếu info giao hàng
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
                    state["name"],
                    state["loai"],
                    state["soluong"],
                    state["phone"],
                    state["address"]
                ]):

                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(sender,
                        f"🎉 Cảm ơn anh/chị {state['name']} đã tin tưởng shop Quang Anh ❤️\n\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ\n\n"
                        "Đơn sẽ được giao trong 2-4 ngày 🚚"
                    )

                    order_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        state["name"],
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
                        "name": None,
                        "loai": None,
                        "soluong": None,
                        "phone": None,
                        "address": None
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
