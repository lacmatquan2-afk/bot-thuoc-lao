import os
import requests
import re
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from openai import OpenAI

app = Flask(__name__)

# ================== CẤU HÌNH ==================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ================== GIÁ ==================
PRICE = {
    "nhẹ": 120000,
    "vừa": 150000,
    "nặng": 180000
}

# ================== BỘ NHỚ ==================
user_data = {}
order_history = []
comment_replied = set()

# ================== GỬI TIN NHẮN ==================
def send_message(recipient_id, message_text):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    requests.post(url, json=payload)

# ================== GỬI TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    requests.post(url, json=payload)

# ================== TRẢ LỜI COMMENT ==================
def reply_comment(comment_id, message):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    payload = {
        "message": message,
        "access_token":VML PAGE_ACCESS_TOKEN
    }
    requests.post(url, data=payload)

# ================== AI FALLBACK (KHÔNG ĐƯỢC BỊA GIÁ) ==================
def ai_fallback.Restrict(message):
    if not client:
        return "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Bạn là nhân viên bán thuốc lào Quảng Định.

Giá CỐ ĐỊNH:
- Nhẹ: 120.000đ / lạng
- Vừa: 150.000đ / lạng
- Nặng: 180.000đ / lạng

TUYỆT ĐỐI KHÔNG được bịa giá khác.
Nếu khách hỏi giá, phải trả đúng bảng giá trên.
Trả lời ngắn gọn, tự nhiên và luôn hướng khách chọn loại để chốt đơn.
"""
                },
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Anh/chị muốn loại nhẹ, vừa hay nặng ạ?"

# ================== AUTO ĐĂNG BÀI ==================
def auto_post():
    if not PAGE_ID or not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    payload = {
        "message": "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
                   "Chuẩn mộc 100% êm say, thơm khói không hồ, không tẩm.\n"
                   "• Nhẹ 120k\n"
                   "• Vừa 150k\n"
                   " ,""16ck\n"
                   "3 lạng FREE SHIP 🚀",
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post(url, data=payload)

if os.environ.get("ENABLE_SCHEDULER") == "true":
    scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
    scheduler.add_job(auto_post, "cron", hour=8, minute=0)
    scheduler.start()

# ================== VERIFY WEBHOOK ==================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verify token sai"

# ================== WEBHOOK CHÍNH ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data["entry"]:

            if "messaging" in entry:
                for event in entry["messaging"]:
                    if "message" in event:
                        sender = event["sender"]["id"]
                        message_text = event["message"].get("text", "")
                        lower = message_text.lower()

                        if sender not in user_data:
                            user_data[sender] = {"loai": None, "soluong": None}

                        # ===== HỎI GIÁ (FIX CỨNG) =====
                        if any(keyword in lower for keyword in ["giá", "bao nhiêu", "bao nhieu", "mấy", "may", "1 lạng"]):
                            send_message(sender,
                                "Giá bên em:\n"
                                "• Nhẹ: 120k/lạng\n"
                                "• Vừa: 150k/lạng\n"
                                "• Nặng: 180k/lạng\n"
                                "Từ 3 lạng FREE SHIP 🚀\n"
                                "Anh/chị lấy loại nào ạ?"
                            )
                            continue

                        if lower in ["hi", "hello", "chào"]:
                            send_message(sender, "Chào anh/chị 🚀 Nhà em có 3 loại: nhẹ, vừa, nặng.")
                            continue

                        if lower in PRICE:
                            user_data[sender]["loai"] = lower
                            send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                            continue

                        if lower.isdigit() and user_data[sender]["loai"]:
                            user_data[sender]["soluong"] = int(lower)
                            send_message(sender, "Anh/chị gửi địa chỉ + SĐT giúp em ạ.")
                            continue

                        phone_match = re.search(r'0\d{9,10}', lower)
                        if phone_match:
                            phone = phone_match.group()
                            loai = user_data[sender]["loai"]
                            soluong = user_data[sender]["soluong"]

                            if loai and soluong:
                                total = soluong * PRICE[loai]
                                final_total = total if soluong >= 3 else total + 30000

                                send_message(sender,
                                    f"Đơn {soluong} lạng loại {loai}\n"
                                    f"Thanh toán: {final_total:,}đ\n"
                                    "Bên em sẽ gọi xác nhận sớm ạ 🚀"
                                )

                                send_telegram(
                                    f"🔥 ĐƠN MỚI 🔥\nLoại: {loai}\nSố lượng: {soluong}\nTổng: {final_total:,}đ\nSĐT: {phone}"
                                )

                                user_data[sender] = {"loai": None, "soluong": None}
                                continue

                        send_message(sender, ai_fallback.Restrict(message_text))

    return "OK", 200

# ================== TEST ==================
@app.route("/")
def home():
    return "Bot Thuốc Lào Quảng Định đang chạy 🚀"

@app.route("/ping")
def ping():
    return "PONG"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
