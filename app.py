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

# ================= AI ENGINE =================

def ai_process(uid, user_text):

    history = user_data.get(uid, {}).get("history", [])

    history.append({"role": "user", "content": user_text})

    system_prompt = """
Bạn là nhân viên bán hàng chuyên nghiệp.
Mục tiêu: CHỐT ĐƠN.
Luôn hướng khách đến đặt hàng.

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
Chỉ trả JSON, không thêm chữ.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_prompt}] + history,
            temperature=0.7
        )

        content = completion.choices[0].message.content
        result = json.loads(content)

        history.append({"role":"assistant","content":result["reply"]})

        user_data[uid] = user_data.get(uid, {})
        user_data[uid]["history"] = history
        user_data[uid]["order"] = merge_order(uid, result.get("order_data", {}))

        return result["reply"]

    except:
        return "Anh cần em hỗ trợ thêm gì để chốt đơn ạ?"

def merge_order(uid, new_data):
    old = user_data.get(uid, {}).get("order", {})
    merged = old.copy()
    for k,v in new_data.items():
        if v:
            merged[k] = v
    return merged

def check_complete_order(uid):
    order = user_data.get(uid, {}).get("order", {})
    return all(order.get(x) for x in ["price","qty","phone","address"])

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

    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "comment_id" in value:
                    comment_id = value["comment_id"]
                    message = value.get("message", "").lower()
                    sender_id = value.get("from", {}).get("id")

                    if "giá" in message:
                        reply_comment(comment_id, "Em đã inbox anh 🔥")

            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]

                if "message" in messaging:
                    text = messaging["message"].get("text","")

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

# ================= POLICY =================

@app.route("/privacy-policy")
def privacy():
    return """
    <h2>Chính sách quyền riêng tư</h2>
    <p>Dữ liệu chỉ dùng để xử lý đơn hàng.</p>
    <p>Hệ thống tự xóa dữ liệu sau khi hoàn tất đơn.</p>
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
