from flask import Flask, request
import os

app = Flask(__name__)

VERIFY_TOKEN = "thuoclao123"

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
        return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


