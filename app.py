from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "thuoclao123"

@app.route("/")
def home():
    return "Bot thuốc lào Quảng Định đang chạy!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token == VERIFY_TOKEN:
            return challenge
        else:
            return "Verify token mismatch", 403

    if request.method == "POST":
        data = request.get_json()
        print(data)
        return "OK", 200

if _name_ == "_main_":
    app.run()

