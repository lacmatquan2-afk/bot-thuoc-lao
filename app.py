import os
import hmac
import hashlib
import time
import threading
import requests
import re
from flask import Flask, request
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

GRAPH_URL = "https://graph.facebook.com/v19.0"
client = OpenAI(api_key=OPENAI_API_KEY)

# ================= DATA =================

user_data = {}
processed_comments = set()

FIXED_GREETING = "Chào anh/chị đã đến với THUỐC LÀO QUẢNG ĐỊNH 🚀\n"
MAIN_CLOSE = "Anh/chị cho em xin SĐT + địa chỉ để em lên đơn ngay ạ."

PRICE_TABLE = {
    "nhẹ": 120000,
    "vừa": 150000,
    "nặng": 180000
}

# ================= SECURITY =================

def verify_signature(req):
    signature = req.headers.get("X-Hub-Signature-256")
    if not signature:
        return False
    sha_name, signature = signature.split("=")
    mac = hmac.new(APP_SECRET.encode(), msg=req.data, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

# ================= TELEGRAM =================

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    requests.post(url, json=payload)

# ================= MESSAGE =================

def send_message(uid, text):
    now = time.time()
    user = user_data.setdefault(uid, {})
    if user.get("last_message") == text:
        return
    if now - user.get("last_time", 0) < 2:
        return
    url = f"{GRAPH_URL}/me/messages"
    payload = {"recipient": {"id": uid}, "message": {"text": text}}
    requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload)
    user["last_message"] = text
    user["last_time"] = now

def reply_comment(comment_id, text):
    url = f"{GRAPH_URL}/{comment_id}/comments"
    requests.post(url, data={"message": text, "access_token": PAGE_ACCESS_TOKEN})

def private_reply(comment_id, text):
    url = f"{GRAPH_URL}/{comment_id}/private_replies"
    requests.post(url, data={"message": text, "access_token": PAGE_ACCESS_TOKEN})

# ================= DETECT =================

def detect_phone(text):
    match = re.search(r'(0\d{9,10})', text)
    return match.group(0) if match else None

def detect_quantity(text):
    text = text.lower()
    kg = re.search(r'(\d+(?:\.\d+)?)\s*kg', text)
    if kg:
        return float(kg.group(1)) * 10
    gram = re.search(r'(\d+)\s*g', text)
    if gram:
        return float(gram.group(1)) / 100
    lang = re.search(r'(\d+(?:\.\d+)?)\s*l', text)
    if lang:
        return float(lang.group(1))
    return None

def detect_type(text):
    text = text.lower()
    for t in PRICE_TABLE:
        if t in text:
            return t
    return None

# ================= AI =================

def ai_reply(user_text):
    system_prompt = """
Bạn là người bán thuốc lào chuyên nghiệp.
Trả lời tự nhiên như người thật.
Ngắn gọn, tập trung chốt đơn.
Nếu hỏi giá → báo giá.
Nếu hỏi nặng không → giải thích từng loại.
Nếu hỏi ngon → hỏi khách thích nặng hay nhẹ.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_text}
            ],
            temperature=0.6
        )
        return completion.choices[0].message.content.strip()
    except:
        return "Bên em có 3 loại: Nhẹ 120k, Vừa 150k, Nặng 180k ạ."

# ================= REMIND =================

def remind(uid):
    time.sleep(300)
    state = user_data.get(uid, {})
    if not state.get("ordered"):
        send_message(uid, "Anh/chị còn quan tâm không ạ? Em giữ hàng cho mình nhé 🚀")

# ================= AUTO POST =================

def auto_post():
    if not PAGE_ID or not POST_IMAGE_URL:
        return
    message = (
        "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
        "Nhẹ 120k | Vừa 150k | Nặng 180k\n"
        "Từ 3 lạng miễn phí ship 🚀\n"
        "Inbox đặt hàng ngay!"
    )
    url = f"{GRAPH_URL}/{PAGE_ID}/photos"
    requests.post(url, data={
        "url": POST_IMAGE_URL,
        "caption": message,
        "access_token": PAGE_ACCESS_TOKEN
    })

# ================= ROUTES =================

@app.route("/")
def home():
    return "BOT ULTIMATE V5 đang chạy 🚀"

@app.route("/privacy")
def privacy():
    return "<h2>Chính sách quyền riêng tư</h2><p>Không chia sẻ dữ liệu.</p>"

@app.route("/terms")
def terms():
    return "<h2>Điều khoản sử dụng</h2><p>Ứng dụng hỗ trợ bán hàng tự động.</p>"

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Sai token"

@app.route("/webhook", methods=["POST"])
def webhook():
    if not verify_signature(request):
        return "Invalid", 403

    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):

            # ===== COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change.get("field") == "feed":
                        value = change["value"]
                        comment_id = value.get("comment_id")
                        from_id = value.get("from",{}).get("id")

                        if not comment_id or comment_id in processed_comments:
                            continue
                        if from_id == PAGE_ID:
                            continue

                        processed_comments.add(comment_id)

                        reply_comment(comment_id, "Em đã inbox anh/chị rồi ạ 🚀")
                        private_reply(comment_id, FIXED_GREETING + "Em inbox tư vấn chi tiết ạ.")

            # ===== INBOX =====
            for messaging in entry.get("messaging", []):
                sender = messaging["sender"]["id"]

                if "message" in messaging:
                    text = messaging["message"].get("text","")

                    qty = detect_quantity(text)
                    typ = detect_type(text)
                    phone = detect_phone(text)

                    if qty and typ:
                        total = qty * PRICE_TABLE[typ]
                        ship_text = "Miễn phí ship 🚀" if qty >= 3 else "Ship 30k"
                        send_message(sender,
                            FIXED_GREETING +
                            f"Anh/chị lấy {qty} lạng loại {typ}.\n"
                            f"Tổng tiền: {int(total):,}đ\n{ship_text}\n\n"
                            + MAIN_CLOSE
                        )
                        continue

                    if phone:
                        user_data.setdefault(sender,{})["ordered"] = True
                        send_message(sender, "Em đã nhận thông tin. Bên em sẽ gọi xác nhận và giao hàng sớm ạ 🚀")
                        send_telegram(f"🔥 ĐƠN MỚI 🔥\nKhách: {sender}\nNội dung: {text}")
                        continue

                    reply_text = ai_reply(text)
                    send_message(sender, FIXED_GREETING + reply_text + "\n\n" + MAIN_CLOSE)
                    threading.Thread(target=remind, args=(sender,)).start()

    return "ok"

# ================= RUN =================

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_post, 'cron', hour=8, minute=0)
    scheduler.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
