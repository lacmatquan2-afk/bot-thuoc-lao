import os
import json
import hmac
import hashlib
import threading
import requests
import time
import re
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

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

# ================= MEMORY =================

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
    except Exception as e:
        logging.error(f"Send message error: {e}")

def reply_comment(comment_id, message):
    try:
        url = f"{GRAPH_URL}/{comment_id}/comments"
        params = {"message": message, "access_token": PAGE_ACCESS_TOKEN}
        requests.post(url, params=params, timeout=5)
    except Exception as e:
        logging.error(f"Reply comment error: {e}")

# ================= TELEGRAM =================

def send_telegram(message):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram error: {e}")

# ================= VALIDATION =================

def is_valid_phone(phone):
    pattern = r"^(0|\+84)[0-9]{8,10}$"
    return re.match(pattern, phone)

# ================= AI ENGINE =================

def merge_order(uid, new_data):
    old = user_data.get(uid, {}).get("order", {})
    merged = old.copy()
    for k, v in new_data.items():
        if v:
            merged[k] = v
    return merged

def check_complete_order(uid):
    order = user_data.get(uid, {}).get("order", {})
    if not all(order.get(x) for x in ["price","qty","phone","address"]):
        return False
    if not is_valid_phone(order["phone"]):
        return False
    return True

def ai_process(uid, user_text):
    history = user_data.get(uid, {}).get("history", [])
    history.append({"role": "user", "content": user_text})
    history = history[-6:]

    system_prompt = """
Bạn là nhân viên bán hàng chuyên nghiệp.
Mục tiêu: CHỐT ĐƠN.
Nếu thiếu thông tin thì PHẢI hỏi tiếp cho đủ.

Sản phẩm có:
- Nhẹ 120k
- Vừa 150k
- Nặng 180k

Trả về JSON đúng format:
{
 "reply": "...",
 "order_data": {
    "price": null,
    "qty": null,
    "phone": null,
    "address": null
 }
}
Chỉ trả JSON.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_prompt}] + history,
            temperature=0.7
        )

        content = completion.choices[0].message.content.strip()

        try:
            result = json.loads(content)
        except:
            logging.warning("AI returned invalid JSON")
            return "Anh cho em xin lại thông tin rõ hơn ạ."

        reply = result.get("reply","Anh cần hỗ trợ gì thêm ạ?")
        order_data = result.get("order_data", {})

        history.append({"role":"assistant","content":reply})

        user_data[uid] = user_data.get(uid, {})
        user_data[uid]["history"] = history
        user_data[uid]["order"] = merge_order(uid, order_data)

        return reply

    except Exception as e:
        logging.error(f"AI error: {e}")
        return "Anh cần em hỗ trợ thêm gì để chốt đơn ạ?"

# ================= WEBHOOK =================
@app.route("/privacy")
def privacy():
    return """
    <h1>Privacy Policy</h1>
    <p>Chúng tôi không lưu trữ hoặc chia sẻ dữ liệu người dùng.</p>
    <p>Dữ liệu chỉ được sử dụng để trả lời tin nhắn tự động.</p>
    """
@app.route("/delete-data")
def delete_data():
    return """
    <h1>Yêu cầu xóa dữ liệu</h1>
    <p>Nếu bạn muốn xóa dữ liệu, vui lòng liên hệ email: lacmatquanz@gmail.com</p>
    """

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Sai token"

@app.route("/webhook", methods=["POST"])
def webhook():
    if not verify_signature(request):
        return "Invalid signature", 403

    data = request.get_json(silent=True)
    if not data:
        return "Bad request", 400

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "comment_id" in value:
                    comment_id = value["comment_id"]
                    message = value.get("message", "").lower()
                    if "giá" in message:
                        reply_comment(comment_id, "Em đã inbox anh 🔥")

            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]

                if "message" in messaging:
                    text = messaging["message"].get("text","")

                    lock = get_user_lock(sender_id)
                    with lock:
                        reply = ai_process(sender_id, text)
                        send_message(sender_id, reply)

                        if check_complete_order(sender_id):
                            order = user_data[sender_id]["order"]
                            total = order["price"] * order["qty"]

                            send_telegram(
                                f"🔥 ĐƠN MỚI 🔥\n"
                                f"SĐT: {order['phone']}\n"
                                f"Địa chỉ: {order['address']}\n"
                                f"Tổng: {total}đ"
                            )

                            user_data.pop(sender_id, None)

    return "ok"

# ================= AUTO POST =================

def auto_post():
    try:
        if not POST_IMAGE_URL:
            return
        message = "Thuốc lào chuẩn vị 🔥 Inbox để được tư vấn ngay!"
        url = f"{GRAPH_URL}/{PAGE_ID}/photos"
        payload = {
            "url": POST_IMAGE_URL,
            "caption": message,
            "access_token": PAGE_ACCESS_TOKEN
        }
        requests.post(url, data=payload, timeout=10)
        logging.info("Auto post success")
    except Exception as e:
        logging.error(f"Auto post error: {e}")

# ================= POLICY =================

@app.route("/privacy-policy")
def privacy():
    return """
    <h2>Chính sách quyền riêng tư</h2>
    <p>Chúng tôi thu thập số điện thoại và địa chỉ để xử lý đơn hàng.</p>
    <p>Dữ liệu chỉ dùng cho mục đích giao hàng.</p>
    <p>Không chia sẻ cho bên thứ ba.</p>
    <p>Dữ liệu được xóa sau khi hoàn tất đơn.</p>
    <p>Yêu cầu xóa dữ liệu qua endpoint /data-deletion.</p>
    """

@app.route("/data-deletion", methods=["POST"])
def data_deletion():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error":"Invalid request"}), 400

    uid = data.get("user_id")
    if uid:
        user_data.pop(uid, None)

    return jsonify({
        "url": "https://yourdomain.com/data-deletion-status",
        "confirmation_code": str(int(time.time()))
    })

# ================= RUN =================

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_post, "cron", hour=19, minute=30)
    scheduler.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

