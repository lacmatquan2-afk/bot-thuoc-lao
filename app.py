from flask import Flask, request
import requests
import os

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = "thuoclao123"

# ====== VERIFY WEBHOOK ======
@app.route("/webhook", methods=["GET"])
def verify():
    token_sent = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token_sent == VERIFY_TOKEN:
        return challenge
    return "Verify token mismatch", 403


# ====== HANDLE MESSAGE ======
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging["sender"]["id"]

                if "message" in messaging:
                    message_text = messaging["message"].get("text", "")
                    handle_message(sender_id, message_text)

    return "ok", 200


def handle_message(sender_id, message_text):
    message_text = message_text.lower()

    if "giá" in message_text or "bao nhiêu" in message_text:
        reply = (
            "🔥 Thuốc lào Quảng Định:\n"
            "💰 Loại 1: 100k/gói\n"
            "💰 Loại đặc biệt: 150k/gói\n"
            "Anh/chị cần lấy loại nào ạ?"
        )

    elif "ship" in message_text or "giao" in message_text:
        reply = "🚚 Bên em giao hàng toàn quốc, nhận hàng kiểm tra rồi thanh toán."

    elif "chốt" in message_text or "đặt" in message_text or "mua" in message_text:
        reply = (
            "✅ Anh/chị cho em xin:\n"
            "📍 Địa chỉ nhận hàng\n"
            "📞 Số điện thoại\n"
            "📦 Số lượng cần lấy\n\n"
            "Bên em lên đơn ngay ạ!"
        )

    elif "sỉ" in message_text or "buôn" in message_text:
        reply = "📦 Có giá sỉ khi lấy số lượng lớn. Gọi 0868862907 để được giá tốt nhất!"

    else:
        reply = (
            "Chào anh/chị 👋\n"
            "Thuốc lào Quảng Định thơm đậm, nguyên chất.\n"
            "💰 100k và 150k tuỳ loại.\n"
            "Anh/chị cần tư vấn gì thêm ạ?"
        )

    send_message(sender_id, reply)


def send_message(recipient_id, message_text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    requests.post(url, params=params, headers=headers, json=payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


