import os
import requests
import re
import csv
import json
import time
import threading
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

app = Flask(__name__)

# ================= CONFIG (Lấy từ Environment) =================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ID = os.environ.get("PAGE_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Cấu hình sản phẩm
PRICE = {"loại 1": 120000, "loại 2": 150000, "loại 3": 180000}
SHIP_FEE = 30000
FREE_SHIP_THRESHOLD = 3 # 3 lạng freeship
CSV_FILE = "orders.csv"

# Bộ nhớ tạm
users = {} 
last_interact = {} # Chống spam & Follow up

# ================= CÔNG CỤ NHẬN DIỆN THÔNG MINH =================

def detect_info(text):
    text = text.lower()
    info = {}

    # 1. Nhận diện Loại (Dựa trên giá, số, hoặc đặc tính)
    if re.search(r'120|loại 1|l1|nhẹ|êm', text):
        info['loai'] = "loại 1"
    elif re.search(r'150|loại 2|l2|vừa|binh thuong', text):
        info['loai'] = "loại 2"
    elif re.search(r'180|loại 3|l3|nặng|dam|say', text):
        info['loai'] = "loại 3"

    # 2. Nhận diện Số lượng (Hỗ trợ lạng, kg, cân, túi)
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|ký|cân|kí)', text)
    lang_match = re.search(r'(\d+)\s*(lạng|lang|l|lạng)', text)
    if kg_match:
        info['soluong'] = int(float(kg_match.group(1)) * 10)
    elif lang_match:
        info['soluong'] = int(lang_match.group(1))
    elif re.search(r'\b(1|2|3|4|5)\b', text) and 'loai' not in text: 
        # Nếu chỉ nói số khơi khơi khi đang hỏi số lượng
        num = re.findall(r'\d+', text)
        if num: info['soluong'] = int(num[0])

    # 3. Nhận diện SĐT (Chuẩn Việt Nam)
    phone = re.findall(r'(0[3|5|7|8|9][0-9\s.\-]{8,11})', text)
    if phone:
        info['phone'] = re.sub(r'\D', '', phone[0])

    # 4. Nhận diện Tên (Sau các từ khóa)
    name_match = re.search(r'(tên là|mình là|gửi cho|tên|anh|chị)\s+([a-zA-ZÀ-ỹ\s]{2,30})', text)
    if name_match:
        info['name'] = name_match.group(2).strip().title()

    # 5. Nhận diện Địa chỉ (Nếu chuỗi dài và có số nhà hoặc tên đường/tỉnh)
    if len(text) > 15 or re.search(r'(số|ngõ|ngách|đường|phường|xã|huyện|tỉnh|tp|thành phố)', text):
        # Loại trừ các câu hỏi giá
        if "nhiêu" not in text and "giá" not in text:
            info['address'] = text.strip()

    return info

# ================= AI BÁN HÀNG THỰC CHIẾN =================

def get_ai_response(uid, user_msg):
    if not client: return "Dạ anh lấy loại mấy lạng và cho em xin địa chỉ ạ?"
    
    state = users.get(uid, {})
    
    # Đây là bộ não của Bot - Đừng xóa dòng này
    prompt = f"""
    Bạn là chuyên gia chốt đơn của Thuốc Lào Quảng Định. 
    SẢN PHẨM: 
    - Đặc điểm: Chính gốc Quảng Định, Chuẩn Mộc, Êm Say, Không Hồ, Không Pha Trộn.
    - Loại 1: 120k/lạng (Êm, ngọt hậu).
    - Loại 2: 150k/lạng (Vừa tầm, khói thơm).
    - Loại 3: 180k/lạng (Đậm, Phê, Nặng đô).
    - Ưu đãi: Mua từ 3 lạng FREE SHIP.

    TRẠNG THÁI ĐƠN HÀNG HIỆN TẠI: {json.dumps(state, ensure_ascii=False)}

    QUY TẮC BẮT BUỘC:
    1. Tuyệt đối không chat lan man. Mục tiêu duy nhất là lấy đủ: LOẠI, SỐ LƯỢNG, SĐT, ĐỊA CHỈ.
    2. Nếu khách chưa chọn loại: Phải liệt kê lại 3 loại 120k-150k-180k.
    3. Nếu khách mua dưới 3 lạng: Hãy khéo léo mời khách mua lên 3 lạng để được Freeship (Tiết kiệm 30k ship).
    4. Nếu khách hỏi "có ngon không", "có phê không": Cam kết thuốc chuẩn mộc, không hồ, hút chỉ có say.
    5. Ngôn ngữ: Dân dã, gọi khách là 'anh', xưng 'em' hoặc 'nhà em'. Trả lời ngắn gọn, dứt khoát.
    """
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.4 # Để bot trả lời ổn định, không bị "sáng tạo" quá mức
        )
        return res.choices[0].message.content
    except:
        return "Dạ anh lấy loại mấy và mấy lạng để em lên đơn freeship cho mình luôn ạ?"
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}],
            temperature=0.5
        )
        return res.choices[0].message.content
    except:
        return "Dạ anh cho em xin SĐT và Địa chỉ để em gửi thuốc sớm cho mình ạ!"

# ================= XỬ LÝ FACEBOOK API =================

def send_fb_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    requests.post(url, json=payload)

def send_private_reply(comment_id, message_text):
    """Gửi tin nhắn trực tiếp cho người comment"""
    url = f"https://graph.facebook.com/v19.0/{comment_id}/private_replies?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={"message": message_text})

def reply_comment(comment_id):
    """Trả lời comment công khai"""
    url = f"https://graph.facebook.com/v19.0/{comment_id}/comments?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, data={"message": "Dạ anh check inbox em tư vấn loại ngon nhất cho mình nhé!"})

# ================= LOGIC CHỐT ĐƠN & LƯU TRỮ =================

def finalize_order(uid):
    s = users[uid]
    if all([s['loai'], s['soluong'], s['phone'], s['address']]):
        # Tính tiền
        unit_price = PRICE.get(s['loai'], 150000)
        subtotal = unit_price * s['soluong']
        ship = 0 if s['soluong'] >= FREE_SHIP_THRESHOLD else SHIP_FEE
        total = subtotal + ship
        
        order_msg = (
            f"🔔 XÁC NHẬN ĐƠN HÀNG THÀNH CÔNG\n"
            f"---------------------------\n"
            f"👤 Khách hàng: {s.get('name', 'Quý khách')}\n"
            f"📞 SĐT: {s['phone']}\n"
            f"🏠 Địa chỉ: {s['address']}\n"
            f"📦 Hàng: {s['soluong']} lạng {s['loai']}\n"
            f"💰 Tổng thanh toán: {total:,}đ\n"
            f"(Miễn phí ship)" if ship == 0 else f"(Ship: {ship:,}đ)"
        )
        
        # Gửi xác nhận cho khách và Telegram
        send_fb_message(uid, order_msg + "\n\nCảm ơn anh, bên em sẽ gọi xác nhận và gửi hàng ngay ạ!")
        send_to_telegram(f"🔥 CÓ ĐƠN MỚI!\n{order_msg}")
        
        # Lưu CSV
        save_to_csv([datetime.now().strftime("%d/%m %H:%M"), s['loai'], s['soluong'], total, s.get('name',''), s['phone'], s['address']])
        
        # Reset trạng thái
        users[uid] = {k: None for k in users[uid]}
        return True
    return False

def save_to_csv(row):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Thời gian", "Loại", "SL", "Tổng", "Tên", "SĐT", "Địa chỉ"])
        writer.writerow(row)

def send_to_telegram(text):
    if TELEGRAM_BOT_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})

# ================= TỰ ĐỘNG HÓA (CHRON JOBS) =================

def auto_post_daily():
    if not PAGE_ID or not PAGE_ACCESS_TOKEN: return
    posts = [
        "Thuốc lào Quảng Định - Êm say, hậu ngọt. Loại 1 120k, Loại 2 150k, Loại 3 180k. Free ship từ 3 lạng!",
        "Đã là đàn ông phải có tí 'khói'. Thuốc nhà em bao ngon, không nóng cổ. Inbox nhận ưu đãi freeship ngay!",
        "Sáng ra làm biếu thuốc lào - Tỉnh táo cả ngày. Anh em đặt hàng để lại SĐT dưới comment nhé!"
    ]
    import random
    msg = random.choice(posts)
    url = f"https://graph.facebook.com/v19.0/{PAGE_ID}/feed"
    requests.post(url, data={"message": msg, "access_token": PAGE_ACCESS_TOKEN})

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(auto_post_daily, 'cron', hour=8, minute=30)
scheduler.start()

# ================= FLASK ROUTES =================

@app.route("/", methods=["GET"])
def home(): return "BOT THUỐC LÀO PRO MAX IS ACTIVE", 200

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Sai Verify Token", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    
    if data.get("object") == "page":
        for entry in data["entry"]:
            # 1. Xử lý Comment (Auto Reply + Auto Inbox)
            if "changes" in entry:
                for change in entry["changes"]:
                    if change.get("field") == "feed" and change["value"].get("item") == "comment":
                        v = change["value"]
                        if v.get("verb") == "add":
                            comment_id = v.get("comment_id")
                            # Tránh bot tự trả lời mình
                            if v.get("from", {}).get("id") != PAGE_ID:
                                reply_comment(comment_id)
                                send_private_reply(comment_id, "Chào anh, em thấy mình quan tâm thuốc lào Quảng Định. Anh lấy loại nào để em ship ạ?")

            # 2. Xử lý Tin nhắn (Chatbot chốt đơn)
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if sender_id == PAGE_ID: continue
                
                msg_text = event.get("message", {}).get("text", "")
                if not msg_text: continue

                # Chống spam: Nếu nhắn quá nhanh trong 1s thì bỏ qua
                now = time.time()
                if sender_id in last_interact and now - last_interact[sender_id] < 1:
                    continue
                last_interact[sender_id] = now

               # Khởi tạo user nếu mới
                if sender_id not in users:
                    users[sender_id] = {"loai":None, "soluong":None, "phone":None, "address":None, "name":None}
                    
                    # CÂU CHÀO THẦN THÁNH Ở ĐÂY:
                    welcome_msg = (
                        "Chào anh! Cảm ơn anh đã quan tâm Thuốc lào Quảng Định chính gốc.\n\n"
                        "Thuốc nhà em cam kết CHUẨN MỘC - ÊM SAY - KHÔNG HỒ - KHÔNG PHA TRỘN.\n"
                        "Anh tham khảo 3 loại ngon nhất bên em:\n"
                        "🔹 Loại 1: 120k/lạng (Êm, ngọt hậu)\n"
                        "🔹 Loại 2: 150k/lạng (Vừa tầm, khói thơm)\n"
                        "🔹 Loại 3: 180k/lạng (Đậm - Say - Nặng đô)\n\n"
                        "🔥 Mua 3 lạng được FREE SHIP. Anh lấy loại nào và mấy lạng để em ship ạ?"
                    )
                    send_fb_message(sender_id, welcome_msg)
                    continue

                # Cập nhật thông tin từ tin nhắn
                extracted = detect_info(msg_text)
                for k, v in extracted.items():
                    if v: users[sender_id][k] = v

                # Kiểm tra xem đủ đơn chưa
                if finalize_order(sender_id):
                    continue
                
                # Nếu chưa đủ, dùng AI để ép khách
                ai_msg = get_ai_response(sender_id, msg_text)
                send_fb_message(sender_id, ai_msg)

    return "OK", 200

# ================= KEEP ALIVE & RUN =================

def keep_alive():
    while True:
        try: requests.get("https://bot-thuoc-lao.onrender.com/") # Thay link web của bạn
        except: pass
        time.sleep(600)

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

