from flask import Flask, request
import requests
import os
import csv
from datetime import datetime

app = Flask(_name_)

PAGE_ACCESS_TOKEN = "DAN_TOKEN_PAGE_VAO_DAY"
VERIFY_TOKEN = "quanganh_bot"

# ================== TRANG CHỦ ==================
@app.route("/")
def home():
    return "<h1>Bot thuốc lào Quảng Định PRO đang chạy 🔥</h1>"

# ================== PRIVACY ==================
@app.route("/privacy")
def privacy():
    return """
    <h1>Chính sách quyền riêng tư</h1>
    <p>Website dùng để tự động trả lời tin nhắn và bình luận Facebook.</p>
    <p>Không chia sẻ dữ liệu người dùng.</p>
    <p>Liên hệ: 0868862907</p>
    """

# ================== TERMS ==================
@app.route("/terms")
def terms():
    return """
    <h1>Điều khoản dịch vụ</h1>
    <p>Bot dùng để tư vấn và báo giá thuốc lào Quảng Định.</p>
    <p>Free ship từ 3 lạng.</p>
    <p>Liên hệ: 0868862907</p>
    """

# ================== VERIFY WEBHOOK ==================
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Sai token"

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "entry" in data:
        for entry in data["entry"]:

            # ===== XỬ LÝ INBOX =====
            if "messaging" in entry:
                for messaging in entry["messaging"]:

                    # ❌ Bỏ qua tin nhắn của page
                    if messaging.get("message", {}).get("is_echo"):
                        continue

                    sender_id = messaging["sender"]["id"]
                    message_text = messaging.get("message", {}).get("text", "").lower()

                    if message_text:
                        handle_inbox(sender_id, message_text)

            # ===== XỬ LÝ COMMENT =====
            if "changes" in entry:
                for change in entry["changes"]:
                    if change["field"] == "feed":
                        comment = change["value"]
                        if "comment_id" in comment:
                            handle_comment(comment)

    return "ok"

# ================== XỬ LÝ INBOX ==================
def handle_inbox(sender_id, text):

    if text.isdigit():
        so_lang = int(text)

        if so_lang <= 0:
            send_message(sender_id, "Anh nhập số lạng hợp lệ giúp em ạ.")
            return

        gia = so_lang * 90000
        ship = 0 if so_lang >= 3 else 30000
        tong = gia + ship

        save_order(sender_id, so_lang, tong)

        message = f"""
🧾 ĐƠN HÀNG

Số lượng: {so_lang} lạng
Giá: {gia:,}đ
Ship: {ship:,}đ
----------------
TỔNG: {tong:,}đ

Free ship từ 3 lạng 🔥
Gọi xác nhận: 0868862907
"""
        send_message(sender_id, message)
        return

    message = """
Chào anh 👋

🔥 Loại thường: 90.000đ / lạng
🔥 Loại đặc biệt: 150.000đ / lạng

📦 Free ship từ 3 lạng

Anh nhập số lạng muốn mua (ví dụ: 2 hoặc 3)
"""
    send_message(sender_id, message)

# ================== XỬ LÝ COMMENT ==================
def handle_comment(comment):
    comment_id = comment["comment_id"]
    user_id = comment["from"]["id"]

    message = "Anh check inbox giúp em để nhận báo giá chi tiết nhé 🔥"

    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments?access_token={PAGE_ACCESS_TOKEN}"

    requests.post(url, json={"message": message})

# ================== GỬI TIN NHẮN ==================
def send_message(user_id, message):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    requests.post(
        url,
        json={
            "recipient": {"id": user_id},
            "message": {"text": message}
        }
    )

# ================== LƯU ĐƠN ==================
def save_order(user_id, so_lang, tong):

    file_exists = os.path.isfile("orders.csv")

    with open("orders.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(["Thời gian", "User ID", "Số lạng", "Tổng tiền"])

        writer.writerow([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            user_id,
            so_lang,
            tong
        ])

# ================== RUN ==================
if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000)
