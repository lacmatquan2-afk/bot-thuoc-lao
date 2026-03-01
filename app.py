from flask import Flask, request
import requests
import os
from openai import OpenAI

# ====== KHỞI TẠO APP ======
app = Flask(__name__)

# ====== ENV VARIABLES ======
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== ROUTE TEST (BẮT BUỘC CHO RENDER) ======
@app.route("/", methods=["GET"])
def home():
    return "Bot thuốc lào Quảng Định đang chạy!", 200


# ====== FACEBOOK VERIFY ======
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verification failed", 403


# ====== FACEBOOK RECEIVE MESSAGE ======
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
                        reply = ask_openai(message_text)
                        send_message(sender_id, reply)

    return "OK", 200


# ====== HỎI OPENAI ======
def ask_openai(user_message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Bạn là nhân viên bán thuốc lào Quảng Định. Trả lời ngắn gọn, thân thiện, luôn kèm số điện thoại 0868862907."
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
