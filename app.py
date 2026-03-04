import os
import requests
import re
import csv
import random
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
import threading
import time
import json

app = Flask(__name__)

# ================== CONFIG ==================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

PRICE = {"loại 1": 120000, "loại 2": 150000, "loại 3": 180000}
SHIP_FEE = 30000
FREE_SHIP_FROM = 3

user_data = {}
CSV_FILE = "orders.csv"

# ================== AUTO POST ==================
def auto_post():
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return
    content = (
        "🔥 THUỐC LÀO QUẢNG ĐỊNH 🔥\n"
        "• Loại 1: 120k/lạng\n"
        "• Loại 2: 150k/lạng\n"
        "• Loại 3: 180k/lạng\n"
        "Từ 3 lạng FREE SHIP 🚀"
    )
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
    requests.post(url, data={
        "message": content,
        "access_token": PAGE_ACCESS_TOKEN
    })

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post, "cron", hour=8)
scheduler.start()

# ================== ANTI SLEEP ==================
def keep_alive():
    while True:
        try:
            requests.get("https://bot-thuoc-lao.onrender.com/")
        except:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive, daemon=True).start()

# ================== SEND FB ==================
def send_message(uid, text):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={
        "recipient": {"id": uid},
        "message": {"text": text}
    })

# ================== TELEGRAM ==================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM ENV THIẾU")
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
            writer.writerow(["Time","Loai","SoLuong(lạng)","Tong","Ten","SDT","DiaChi"])
        writer.writerow(order)

# ================== CALCULATE ==================
def calculate_total(loai, soluong):
    total = PRICE[loai] * soluong
    if soluong >= FREE_SHIP_FROM:
        return total, 0
    return total + SHIP_FEE, SHIP_FEE

# ================== DETECT FIX ==================
def detect_quantity(text):
    kg = re.search(r'(\d+(?:\.\d+)?)\s*(kg|ký)', text)
    lang = re.search(r'(\d+)\s*(lạng|lang)', text)
    if kg:
        return int(float(kg.group(1)) * 10)
    if lang:
        return int(lang.group(1))
    return None

def detect_phone(text):
    phone = re.findall(r'0\d[\d\.\s]{8,12}', text)
    if phone:
        cleaned = re.sub(r'\D', '', phone[0])
        if 9 <= len(cleaned) <= 11:
            return cleaned
    return None

def detect_name(text):
    match = re.search(r'(?:tên|tôi là|toi la|mình là|em là|anh là)\s+([a-zA-ZÀ-ỹ\s]{2,40})', text)
    if match:
        return match.group(1).strip().title()
    return None

def detect_address(text):
    if len(text) >= 6:
        return text
    return None

def detect_loai(text):
    if re.search(r'120k?|loại?\s*1|nhẹ', text):
        return "loại 1"
    if re.search(r'150k?|loại?\s*2|vừa', text):
        return "loại 2"
    if re.search(r'180k?|loại?\s*3|nặng', text):
        return "loại 3"
    return None

# ================== OPENAI NGOÀI LUỒNG ==================
def ai_reply(text):
    if not client:
        return None
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {"role": "system","content": "Bạn là nhân viên bán thuốc lào Quảng Định. Luôn hướng khách đặt hàng."},
                {"role": "user","content": text}
            ]
        )
        return res.choices[0].message.content
    except:
        return None

# ================== AI BÓC ĐƠN FIX ==================
def ai_extract_order(text):
    if not client:
        return {}

    try:
        prompt = f"""
Trích xuất thông tin đơn hàng và trả về JSON:
loai (loại 1/2/3 hoặc null)
soluong (số lạng)
phone
name
address
Nếu không có thì null.
Câu: {text}
Chỉ trả JSON.
"""

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role":"user","content":prompt}]
        )

        content = res.choices[0].message.content.strip()

        # TÁCH JSON AN TOÀN
        content = content.replace("```json","").replace("```","").strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end+1]

        data = json.loads(content)

        return {
            "loai": data.get("loai"),
            "soluong": int(data["soluong"]) if data.get("soluong") else None,
            "phone": data.get("phone"),
            "name": data.get("name"),
            "address": data.get("address")
        }

    except Exception as e:
        print("AI EXTRACT ERROR:", e)
        return {}

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                if "message" not in event:
                    continue

                sender = event["sender"]["id"]
                text = event["message"].get("text","").lower()

                if sender not in user_data:
                    user_data[sender] = {
                        "loai":None,"soluong":None,"phone":None,
                        "address":None,"name":None,"intro_sent":False
                    }

                state = user_data[sender]

                if not state["intro_sent"]:
                    send_message(sender,"Chào bạn 👋 Thuốc lào Quảng Định có 3 loại 120k - 150k - 180k. Mua từ 3 lạng free ship 🚀")
                    state["intro_sent"] = True
                    return "OK",200

                state["loai"] = detect_loai(text) or state["loai"]
                state["soluong"] = detect_quantity(text) or state["soluong"]
                state["phone"] = detect_phone(text) or state["phone"]
                state["address"] = detect_address(text) or state["address"]
                state["name"] = detect_name(text) or state["name"]

                if not all([state["loai"],state["soluong"],state["phone"],state["address"],state["name"]]):
                    ai_data = ai_extract_order(text)
                    for key in ["loai","soluong","phone","address","name"]:
                        if not state.get(key) and ai_data.get(key):
                            state[key] = ai_data[key]

                print("STATE HIỆN TẠI:", state)

                if all([state["loai"],state["soluong"],state["phone"],state["address"],state["name"]]):

                    total, ship = calculate_total(state["loai"],state["soluong"])
                    ship_text = "Miễn phí ship" if ship==0 else f"Ship {SHIP_FEE:,}đ"

                    confirm = (
                        f"🎉 XÁC NHẬN ĐƠN 🎉\n"
                        f"Tên: {state['name']}\n"
                        f"SĐT: {state['phone']}\n"
                        f"Địa chỉ: {state['address']}\n"
                        f"{state['soluong']} lạng {state['loai']}\n"
                        f"{ship_text}\n"
                        f"Tổng: {total:,}đ"
                    )

                    send_message(sender, confirm)
                    save_order([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        state["loai"],
                        state["soluong"],
                        total,
                        state["name"],
                        state["phone"],
                        state["address"]
                    ])
                    send_telegram(confirm)

                    user_data[sender] = {
                        "loai":None,"soluong":None,
                        "phone":None,"address":None,
                        "name":None,"intro_sent":True
                    }

                else:
                    reply = ai_reply(text)
                    if reply:
                        send_message(sender, reply)

    return "OK",200

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verify token sai"

@app.route("/")
def home():
    return "BOT AI PRO đang chạy 🚀"

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
