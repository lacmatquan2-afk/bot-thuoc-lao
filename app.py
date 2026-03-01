from flask import Flask, request
import requests
import os
from openai import OpenAI

app = Flask(__name__)

# ====== ENV ======
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== LƯU TRẠNG THÁI KHÁCH ======
user_state = {}

# ====== TRANG CHỦ (CHO RENDER) ======
@app.route("/", methods=["GET"])
def home():
    return "Bot thuốc lào Quảng Định PRO đang chạy!", 200


# ====== VERIFY FACEBOOK ======
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


# ====== NHẬN TIN NHẮN ======
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data and "entry" in data:
        for entry in data["entry"]:
            for messaging_event in entry.get("messaging", []):
                if "message" in messaging_event:
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"].get("text")

                    if message_text:
                        handle_message(sender_id, message_text.lower())

    return "OK", 200


# ====== XỬ LÝ KỊCH BẢN BÁN HÀNG ======
def handle_message(sender_id, text):

    # Nếu khách đang trong quy trình đặt hàng
    if sender_id in user_state:
        state = user_state[sender_id]

        if state == "ask_quantity":
            user_state[sender_id] = {"quantity": text, "step": "ask_address"}
            send_message(sender_id, "Anh gửi giúp em địa chỉ nhận hàng nhé 📦")
            return

        if isinstance(state, dict) and state.get("step") == "ask_address":
            state["address"] = text
            state["step"] = "ask_phone"
            send_message(sender_id, "Anh cho em xin số điện thoại nhận hàng ☎️")
            return

        if isinstance(state, dict) and state.get("step") == "ask_phone":
            state["phone"] = text

            summary = f"""✅ XÁC NHẬN ĐƠN HÀNG:

Số lượng: {state['quantity']}
Địa chỉ: {state['address']}
SĐT: {state['phone']}

Bên em sẽ gọi xác nhận và giao sớm nhất 🚚
Liên hệ nhanh: 0868862907"""

            send_message(sender_id, summary)
            del user_state[sender_id]
            return

    # ====== CÂU HỎI PHỔ BIẾN ======

    if "giá" in text:
        send_message(sender_id,
                     "Thuốc lào Quảng Định loại ngon giá chỉ từ 120k/kg 🔥\n"
                     "Anh muốn lấy bao nhiêu kg ạ?")
        user_state[sender_id] = "ask_quantity"
        return

    if "ship" in text or "giao" in text:
        send_message(sender_id,
                     "Bên em giao hàng toàn quốc 🚚\n"
                     "Phí ship tùy khu vực anh nhé.\n"
                     "Anh muốn đặt mấy kg ạ?")
        user_state[sender_id] = "ask_quantity"
        return

    if "loại" in text or "ngon" in text:
        send_message(sender_id,
                     "Hiện có:\n"
                     "1️⃣ Loại thơm nhẹ\n"
                     "2️⃣ Loại nặng đô\n"
                     "3️⃣ Loại đặc biệt chọn lọc 🔥\n\n"
                     "Anh thích loại nào ạ?")
        return

    # ====== NGOÀI KỊCH BẢN → DÙNG AI ======
    reply = ask_openai(text)
    send_message(sender_id, reply)


# ====== HỎI OPENAI ======
def ask_openai(user_message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Bạn là nhân viên bán thuốc lào Quảng Định. Trả lời ngắn gọn, thân thiện, luôn kèm số 0868862907."
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    return response.choices[0].message.content


# ====== GỬI TIN NHẮN FACEBOOK ======
def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }

    requests.post(url, json=payload)


# ====== CHẠY LOCAL ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

