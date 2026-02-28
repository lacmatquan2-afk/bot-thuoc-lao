from flask import Flask, request
import os

app = Flask(__name__)

VERIFY_TOKEN = "thuoclao123"
PAGE_ACCESS_TOKEN = "EAFwl3GoHM8QBQ9SPSefGm5MblScbGgol066ikCAo8IkzdUpI4WC1dzy0PBBlgKJl8M7U0k0R4UzptgVn1HdyhCDt9aFZA0959fKyKocDXimRiI4SGXZAHoZA1qpODe0DVavpvhVGdeMkO3bUBZAf2U7ZBrE1z6C8EQyxZAX4gHtyIUitb9cX2ElsrDHJ8FmWb72ShCJlZB492rK2GoltZAq7nmFi"

@app.route("/")
def home():
    return "Bot thuốc lào Quảng Định đang chạy!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
    mode = request.args.get("hub_mode")
    token = request.args.get("hub_verify_token")
    challenge = request.args.get("hub_challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verify token mismatch", 403

    if request.method == "POST":
    data = request.get_json()

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging in entry["messaging"]:
                if "message" in messaging:
                    sender_id = messaging["sender"]["id"]
                    send_message(sender_id, "Chào anh/chị 👋 Thuốc lào Quảng Định thơm đậm, nguyên chất. Liên hệ 0868862907 để đặt hàng nhé!")

    return "OK", 200
    import requests

def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v25.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    requests.post(url, json=payload)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))




