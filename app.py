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

Giá:
- Nhẹ 120k
- Vừa 150k
- Nặng 180k

Nếu khách hỏi giá → báo đúng giá.
Nếu khách nói có, đặt, lấy, chốt hoặc có số lượng
→ yêu cầu gửi địa chỉ + SĐT để chốt.
"""
                },
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content
    except:
        return "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?"

# ================== AUTO POST ==================
def auto_post():
    if not PAGE_ID or not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    message = (
        "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
        "• Nhẹ 120k\n"
        "• Vừa 150k\n"
        "• Nặng 180k\n"
        "Từ 3 lạng FREE SHIP 🚀"
    )
    requests.post(url, data={
        "message": message,
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

            # ===== XỬ LÝ COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        comment = change["value"]
                        if "comment_id" in comment:
                            comment_id = comment["comment_id"]
                            user_id = comment.get("from", {}).get("id")
                            message = comment.get("message", "").lower()

                            qty = detect_quantity(message)

                            # Trả lời comment
                            if qty:
                                reply_comment(comment_id, "Inbox em để chốt đơn và nhận báo giá chi tiết nhé 🚀")
                            else:
                                reply_comment(comment_id, "Anh/chị quan tâm inbox em để được tư vấn và báo giá ạ 🚀")

                            # Tự động inbox khách
                            if user_id:
                                send_message(user_id, "Em đã inbox mình rồi ạ, mình check tin nhắn giúp em nhé 🚀")

            # ===== XỬ LÝ INBOX (GIỮ NGUYÊN LOGIC CŨ) =====
            if "messaging" not in entry:
                continue

            for event in entry["messaging"]:
                if "message" not in event:
                    continue

                sender = event["sender"]["id"]
                text = event["message"].get("text", "").lower()

                if sender not in user_data:
                    user_data[sender] = {"loai": None, "soluong": None, "phone": None, "address": None}

                state = user_data[sender]

                qty = detect_quantity(text)

                if text in PRICE:
                    state["loai"] = text
                    send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                    continue

                if qty:
                    state["soluong"] = qty

                    if not state["loai"]:
                        send_message(sender, "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?")
                        continue

                    total, ship = calculate_total(state["loai"], qty)
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(sender,
                        f"{qty} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ\n"
                        "Anh/chị gửi giúp em địa chỉ + SĐT để em chốt đơn ạ 🚀")
                    continue

                phone = detect_phone(text)
                if phone:
                    state["phone"] = phone

                address = detect_address(text)
                if address:
                    state["address"] = address

                if all(state.values()):
                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(sender,
                        f"XÁC NHẬN ĐƠN\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ\n"
                        "Bên em sẽ ship nhanh nhất 🚀")

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

                    user_data[sender] = {"loai": None, "soluong": None, "phone": None, "address": None}
                    continue

                send_message(sender, ai_reply(text))

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
