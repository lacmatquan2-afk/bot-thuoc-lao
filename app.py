import os
import requests
from flask import Flask, request

from openai import OpenAI

app = Flask(__name__)

# ====== CẤU HÌNH ======
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_openai_client():
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY not found")
        return None
    return OpenAI(api_key=OPENAI_API_KEY)
# ====== WEBHOOK VERIFY ======
@app.route("/webhook", methods=["GET"])
def verify():
    token_sent = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token_sent == VERIFY_TOKEN:
        return challenge
    return "Invalid verification token"


# ====== WEBHOOK RECEIVE MESSAGE ======
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "entry" in data:
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event and "text" in messaging_event["message"]:
                    message_text = messaging_event["message"]["text"]
                    handle_message(sender_id, message_text)

    return "OK", 200


# ====== AI HANDLE MESSAGE ======
def handle_message(sender_id, message_text):
    client = get_openai_client()

    if not client:
        return
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": """Bạn là nhân viên tư vấn thuốc lào Quảng Định.

Nhiệm vụ:
- Tư vấn nhiệt tình, nói chuyện tự nhiên như người thật.
- Trả lời ngắn gọn, dễ hiểu.
- Không spam số điện thoại quá nhiều.
- Luôn khuyến khích khách chốt đơn.

Thông tin sản phẩm:
- Loại 1: 100k/gói
- Loại đặc biệt: 150k/gói
- Mua 3 gói trở lên freeship
- Giao hàng toàn quốc
- Hàng thơm, đậm, nguyên chất Quảng Định

Khi khách hỏi giá → báo giá rõ ràng.
Khi khách hỏi mạnh nhẹ → tư vấn loại phù hợp.
Khi khách phân vân → tạo động lực chốt đơn.

Chỉ đưa số điện thoại khi khách hỏi trực tiếp."""
        },
        {
            "role": "user",
            "content": message_text
        }
    ]
)

reply = response.choices[0].message.content
send_message(sender_id, reply)


# ====== SEND MESSAGE TO FACEBOOK ======
def send_message(sender_id, message):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }

    requests.post(url, json=payload)


# ====== RUN ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))







