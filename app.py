from flask import Flask, request
import requests
import os
from openai import OpenAI

app = Flask(_name_)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Verification failed"


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
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "Bạn là nhân viên bán thuốc lào Quảng Định. Trả lời ngắn gọn."
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


def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }

    requests.post(url, json=payload)


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=10000)
