import os
import json
import hmac
import hashlib
import threading
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

load_dotenv()
app = Flask(__name__)

# ================= ENV =================

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET = os.getenv("APP_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PAGE_ID = os.getenv("PAGE_ID")
POST_IMAGE_URL = os.getenv("POST_IMAGE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not PAGE_ACCESS_TOKEN or not VERIFY_TOKEN or not APP_SECRET:
    raise Exception("Thiếu biến môi trường quan trọng!")

client = OpenAI(api_key=OPENAI_API_KEY)
GRAPH_URL = "https://graph.facebook.com/v19.0"

# ================= MEMORY + LOCK =================

user_data = {}
user_locks = {}
global_lock = threading.Lock()

def get_user_lock(uid):
    with global_lock:
        if uid not in user_locks:
            user_locks[uid] = threading.Lock()
        return user_locks[uid]

# ================= SECURITY =================

def verify_signature(req):
    signature = req.headers.get("X-Hub-Signature-256")
    if not signature:
        return False
    try:
        sha_name, signature = signature.split("=")
        mac = hmac.new(
            APP_SECRET.encode(),
            msg=req.data,
            digestmod=hashlib.sha256
        )
        return hmac.compare_digest(mac.hexdigest(), signature)
    except:
        return False

# ================= FACEBOOK =================

def send_message(uid, text):
    try:
        url = f"{GRAPH_URL}/me/messages"
        payload = {"recipient": {"id": uid}, "message": {"text": text}}
        params = {"access_token": PAGE_ACCESS_TOKEN}
        requests.post(url, params=params, json=payload, timeout=5)
    except:
        pass

def reply_comment(comment_id, message):
    try:
        url = f"{GRAPH_URL}/{comment_id}/comments"
        params = {"message": message, "access_token": PAGE_ACCESS_TOKEN}
        requests.post(url, params=params, timeout=5)
    except:
        pass

# ================= TELEGRAM =================

def send_telegram(message):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================= AI =================

def ai_reply(text):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Bạn là nhân viên bán hàng chuyên nghiệp, luôn hướng khách về đặt hàng."},
                {"role": "user", "content": text}
            ],
            timeout=10
        )
        return completion.choices[0].message.content
    except:
        return "Anh cần em hỗ trợ thêm gì để chốt đơn ạ?"

# ================= FLOW BÁN =================

def handle_sale(uid, text):
    lock = get_user_lock(uid)
    with lock:

        if uid not in user_data:
            user_data[uid] = {"step": "choose"}

        step = user_data[uid]["step"]

        if step == "choose":
            send_message(uid,
                "Bên em có:\n"
                "1️⃣ Nhẹ – 120k\n"
                "2️⃣ Vừa – 150k\n"
                "3️⃣ Nặng – 180k\n\n"
                "Anh dùng mức nào ạ?"
            )
            user_data[uid]["step"] = "confirm"
            return

        if step == "confirm":
            if "120" in text:
                price = 120000
            elif "150" in text:
                price = 150000
            elif "180" in text:
                price = 180000
            else:
                send_message(uid, "Anh chọn 120k, 150k hoặc 180k giúp em ạ.")
                return

            user_data[uid]["price"] = price
            user_data[uid]["step"] = "quantity"
            send_message(uid, "Anh lấy 1 hay 2 gói để em hỗ trợ phí ship tốt hơn?")
            return

        if step == "quantity":
            qty = 2 if "2" in text else 1
            user_data[uid]["qty"] = qty
            user_data[uid]["step"] = "phone"
            send_message(uid, "Anh cho em xin số điện thoại nhận hàng ạ?")
            return

        if step == "phone":
            user_data[uid]["phone"] = text
            user_data[uid]["step"] = "address"
            send_message(uid, "Anh gửi giúp em địa chỉ nhận hàng ạ?")
            return

        if step == "address":
            user_data[uid]["address"] = text

            price = user_data[uid]["price"]
            qty = user_data[uid]["qty"]
            total = price * qty

            send_message(uid,
                f"Xác nhận đơn:\n"
                f"Số lượng: {qty}\n"
                f"Tổng tiền: {total}đ\n"
                f"Thanh toán khi nhận hàng (COD)"
            )

            send_telegram(
                f"🔥 ĐƠN MỚI 🔥\n"
                f"SĐT: {user_data[uid]['phone']}\n"
                f"Địa chỉ: {text}\n"
                f"Tổng: {total}đ"
            )

            # TỰ ĐỘNG XÓA DỮ LIỆU SAU KHI CHỐT
            user_data.pop(uid, None)
            return

# ================= WEBHOOK =================

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Sai token"

@app.route("/webhook", methods=["POST"])
def webhook():
    if not verify_signature(request):
        return "Invalid signature", 403

    try:
        data = request.get_json()
    except:
        return "Bad JSON", 400

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            # COMMENT
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "comment_id" in value:
                    comment_id = value["comment_id"]
                    message = value.get("message", "").lower()
                    sender_id = value.get("from", {}).get("id")

                    if "giá" in message:
                        reply_comment(comment_id, "Em đã inbox anh ạ 🔥")
                        if sender_id:
                            handle_sale(sender_id, "mua")

            # INBOX
            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]
                if "message" in messaging:
                    text = messaging["message"].get("text", "").lower()

                    if any(x in text for x in ["mua", "giá"]):
                        handle_sale(sender_id, text)
                        return "ok"

                    reply = ai_reply(text)
                    send_message(sender_id, reply)

    return "ok"

# ================= AUTO POST =================

def auto_post():
    try:
        message = "Thuốc lào chuẩn vị 🔥 Inbox để được tư vấn ngay!"
        url = f"{GRAPH_URL}/{PAGE_ID}/photos"
        payload = {
            "url": POST_IMAGE_URL,
            "caption": message,
            "access_token": PAGE_ACCESS_TOKEN
        }
        requests.post(url, data=payload, timeout=10)
    except:
        pass

scheduler = BackgroundScheduler()
scheduler.add_job(auto_post, "interval", days=1)
scheduler.start()

# ================= CHÍNH SÁCH & DATA DELETE =================

@app.route("/privacy-policy")
def privacy():
    return """
    <h2>Chính sách quyền riêng tư</h2>
    <p>Chúng tôi chỉ lưu dữ liệu khách hàng phục vụ xử lý đơn hàng.</p>
    <p>Dữ liệu được xóa ngay sau khi hoàn tất đơn.</p>
    """

@app.route("/data-deletion", methods=["POST"])
def data_deletion():
    data = request.get_json()
    uid = data.get("user_id")
    user_data.pop(uid, None)

    return jsonify({
        "url": "https://yourdomain.com/data-deletion-status",
        "confirmation_code": str(int(time.time()))
    })

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
