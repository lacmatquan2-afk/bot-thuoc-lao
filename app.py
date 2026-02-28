import os
from openai import OpenAI
from flask import Flask, request
import requests

app = Flask(_name_)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = "thuoclao123"
def ai_reply(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Bạn là nhân viên bán thuốc lào Quảng Định.
Tư vấn nhiệt tình.
Giới thiệu thuốc lào thơm đậm, nguyên chất, giá rẻ.
Nếu khách hỏi giá thì báo giá rõ ràng.
Nếu khách đồng ý mua thì xin tên, số điện thoại, địa chỉ để chốt đơn.
"""
            },
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

@app.route("/")
def home():
    return "Bot Thuốc Lào Quảng Định đang chạy!"


@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    # ===== XỬ LÝ VERIFY =====
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verify token mismatch", 403

    # ===== XỬ LÝ TIN NHẮN =====
    if request.method == "POST":
        data = request.get_json()

        if "entry" in data:
            for entry in data["entry"]:
                for messaging in entry["messaging"]:
                    if "message" in messaging:
                        sender_id = messaging["sender"]["id"]
                        message = messaging["message"].get("text")

                        if message:
                            reply = ai_reply(message)
                            send_message(sender_id, reply)

        return "OK", 200

        

def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v25.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    requests.post(url, json=payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)




