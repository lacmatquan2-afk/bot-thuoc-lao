from flask import Flask, request
app = Flask(__name__)
VERIFY_TOKEN = "thuoclao123"
@app.route("/")
def home():
      return "Bot thuốc lào Quảng Định đang chạy!"
@app.route("wedhook", methods=["GET", "POST"])
def wedhook():
      if request.method =="GET":
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            if token == VERIFY_TOKEN:
                  return challenge
             alse:
                  return "Verify token mismatch", 403
       if request.method == "POST":
             data = request.get_json()
             print(data)
             return "OK", 200
if __name__ == "__main__":
    app.run()
