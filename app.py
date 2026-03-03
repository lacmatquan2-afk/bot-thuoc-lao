import requests
import re
impost os
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from openai import OpenAI

app = Flask(__name__)

# ================== CẤU HÌNH ==================
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"
VERIFY_TOKEN = "bot_thuoc_lao_2026"
PAGE_ID = "YOUR_PAGE_ID"

OPENAI_API_KEY = "YOUR_OPENAI_KEY"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

client = OpenAI(api_key=OPENAI_API_KEY)

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
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    requests.post(url, json=payload)

# ================== GỬI TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    requests.post(url, json=payload)

# ================== TRẢ LỜI COMMENT ==================
def reply_comment(comment_id, message):
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    payload = {
        "message": message,
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post(url, data=payload)

# ================== AI FALLBACK ==================
def ai_fallback(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là nhân viên bán thuốc lào Quảng Định. Trả lời tự nhiên, ngắn gọn, luôn hướng khách về chốt đơn."
                },
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Anh/chị cần tư vấn loại nào ạ?"

# ================== AUTO ĐĂNG BÀI ==================
def auto_post():
    print("Đang auto đăng bài...")
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    payload = {
        "message": "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
                   "Chuẩn mộc 100% êm say, thơm khói không hồ, không tẩm.\n"
                   "• Nhẹ 120k\n"
                   "• Vừa 150k\n"
                   "• Nặng 180k\n"
                   "3 lạng FREE SHIP 🚀",
        "access_token": PAGE_ACCESS_TOKEN
    }
    res = requests.post(url, data=payload)
    print("Auto post status:", res.status_code)
    print("Auto post response:", res.text)

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

            # ===== INBOX =====
            if "messaging" in entry:
                for event in entry["messaging"]:
                    if "message" in event:
                        sender = event["sender"]["id"]
                        message_text = event["message"].get("text", "")
                        lower = message_text.lower()

                        if sender not in user_data:
                            user_data[sender] = {"loai": None, "soluong": None}

                        # Chào
                        if lower in ["hi", "hello", "chào"]:
                            send_message(sender,
                                "Chào bạn đến với THUỐC LÀO QUẢNG ĐỊNH 🚀\n"
                                "Nhà em có 3 loại: nhẹ, vừa, nặng.\n"
                                "Anh/chị muốn loại nào ạ?"
                            )
                            continue

                        # Chọn loại
                        if lower in PRICE:
                            user_data[sender]["loai"] = lower
                            send_message(sender, "Anh/chị lấy bao nhiêu lạng ạ?")
                            continue

                        # Số lượng
                        if lower.isdigit() and user_data[sender]["loai"]:
                            user_data[sender]["soluong"] = int(lower)
                            send_message(sender, "Anh/chị gửi địa chỉ + SĐT giúp em ạ.")
                            continue

                        # Nhận SĐT
                        phone_match = re.search(r'0\d{9,10}', lower)
                        if phone_match:
                            phone = phone_match.group()
                            loai = user_data[sender]["loai"]
                            soluong = user_data[sender]["soluong"]

                            if loai and soluong:
                                total = soluong * PRICE[loai]

                                if soluong >= 3:
                                    final_total = total
                                    ship_text = "Miễn phí ship 🚀"
                                else:
                                    final_total = total + 30000
                                    ship_text = "Phí ship 30k"

                                send_message(sender,
                                    f"Đơn {soluong} lạng loại {loai}\n"
                                    f"Tổng: {total:,}đ\n"
                                    f"{ship_text}\n"
                                    f"Thanh toán: {final_total:,}đ\n"
                                    "Bên em sẽ gọi xác nhận sớm ạ 🚀"
                                )

                                order_history.append({
                                    "id": sender,
                                    "loai": loai,
                                    "soluong": soluong,
                                    "tong": final_total,
                                    "sdt": phone
                                })

                                send_telegram(
                                    f"🔥 ĐƠN MỚI 🔥\n"
                                    f"Khách ID: {sender}\n"
                                    f"Loại: {loai}\n"
                                    f"Số lượng: {soluong}\n"
                                    f"Tổng: {final_total:,}đ\n"
                                    f"SĐT: {phone}"
                                )

                                user_data[sender] = {"loai": None, "soluong": None}
                                continue

                        # ===== AI NGOÀI LUỒNG =====
                        ai_reply_text = ai_fallback(message_text)
                        send_message(sender, ai_reply_text)

            # ===== COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        comment_id = change["value"].get("comment_id")
                        from_id = change["value"]["from"]["id"]
                        comment_text = change["value"].get("message", "")

                        if comment_id in comment_replied:
                            continue

                        comment_replied.add(comment_id)

                        ai_comment_reply = ai_fallback(comment_text)

                        reply_comment(comment_id, ai_comment_reply)
                        send_message(from_id, ai_comment_reply)

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


