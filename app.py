from flask import Flask, request
import requests
import os
from openai import OpenAI

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# ================== WEBHOOK VERIFY ==================
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Verification failed"


# ================== RECEIVE MESSAGE ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "entry" in data:
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if "message" in messaging_event:
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"].get("text")

                    if message_text:

                        # ==== GPT RESPONSE ====
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "system",
                                    "content": """
Bạn là nhân viên bán thuốc lào Quảng Định.
Giá:
- 1 gói: 150k
- Mua 3 gói miễn phí ship
- Giao hàng toàn quốc
- Hàng thơm, đậm, nguyên chất Quảng Định

Khi khách hỏi giá → báo giá rõ ràng.
Khi khách hỏi mạnh nhẹ → tư vấn loại phù hợp.
Khi khách phân vân → tạo động lực chốt đơn.
Chỉ trả lời ngắn gọn, dễ hiểu.
"""
                                },
                                {
                                    "role": "user",
                                    "content": message_text
                                }
                            ]
                        )

                        reply = response.choices[0].message.content

                        send_message(sender_id, reply)

    return "ok", 200


# ================== SEND MESSAGE ==================
def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }

    requests.post(url, json=payload)


# ================== RUN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
