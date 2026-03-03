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
    "• Nhẹ 120k\n"
    "• Vừa 150k\n"
    "• Nặng 180k\n"
    "Từ 3 lạng FREE SHIP 🚀\n"
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
def detect_quantity(text):
    kg_match = re.search(r'(\d+)\s*(kg|ký)', text)
    lang_match = re.search(r'(\d+)\s*(lạng|lang)', text)

    if kg_match:
        return int(kg_match.group(1)) * 10

    if lang_match:
        return int(lang_match.group(1))

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
        return text
    return None

# ================== AI ==================
def ai_reply(text):
    if not client:
        return "Anh/chị cho em xin loại và số lượng để em chốt đơn ạ 🚀"

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Bạn là nhân viên bán thuốc lào.
Nếu khách hỏi ngoài lề → trả lời ngắn gọn rồi dẫn về hỏi loại và số lượng.
Nếu có ý định mua → yêu cầu họ tên + địa chỉ + SĐT để chốt.
"""
                },
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content
    except:
        return "Anh/chị cho em xin loại và số lượng để em chốt đơn ạ 🚀"

# ================== AUTO POST ==================
def auto_post():
    if not PAGE_ID or not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    message = INTRO_MESSAGE
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

            # ===== COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        comment = change["value"]
                        if "comment_id" in comment:
                            comment_id = comment["comment_id"]
                            message = comment.get("message", "").lower()

                            reply_comment(
                                comment_id,
                                "🔥 Thuốc lào Quảng Định\n"
                                "• Nhẹ 120k\n• Vừa 150k\n• Nặng 180k\n"
                                "Anh/chị inbox em loại và số lượng để chốt đơn nhé 🚀"
                            )

            # ===== INBOX =====
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

                # ===== NHẬN DIỆN LOẠI =====
                for loai in PRICE:
                    if loai in text:
                        state["loai"] = loai
                        send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                        break

                qty = detect_quantity(text)
                if qty:
                    state["soluong"] = qty
                    if state["loai"]:
                        send_message(sender, "Anh/chị gửi giúp em HỌ TÊN + ĐỊA CHỈ + SĐT để em chốt đơn ạ 🚀")
                        continue

                phone = detect_phone(text)
                if phone:
                    state["phone"] = phone

                address = detect_address(text)
                if address:
                    state["address"] = address

                name = detect_name(text)
                if name:
                    state["name"] = name

                # ===== CHỐT ĐƠN NGAY KHI ĐỦ =====
                if state["loai"] and state["soluong"] and state["phone"] and state["address"] and state["name"]:
                    total, ship = calculate_total(state["loai"], state["soluong"])
                    ship_text = "Miễn phí ship 🚀" if ship == 0 else f"Ship {SHIP_FEE:,}đ"

                    send_message(
                        sender,
                        f"🎉 CẢM ƠN ANH/CHỊ {state['name']} ĐÃ TIN TƯỞNG SHOP QUANG ANH 🎉\n"
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
                        f"Tên: {state['name']}\n"
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
