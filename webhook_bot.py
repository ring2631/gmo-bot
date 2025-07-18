from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import json

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ GMO BOT is running!"

API_KEY = "EGxl+85mHoo208TUiZRVSoFWlhodhCxM"
API_SECRET = "Dy4KpK8pzdVtLpfBCh6vS1QwNx1F6npZPeufkqiYMF02i5SBVae9hE2LHWKFaWZT"

def get_gmo_server_time():
    try:
        res = requests.get("https://api.coin.z.com/public/v1/server-time")
        server_time = res.json()["data"]
        return str(server_time)
    except Exception as e:
        print("❌ 時刻取得エラー:", e)
        return str(int(time.time() * 1000))  # fallback

def send_order():
    url = "https://api.coin.z.com/private/v1/order"
    timestamp = get_gmo_server_time()
    body = {
        "symbol": "BTC_JPY",
        "side": "BUY",
        "executionType": "MARKET",
        "size": "0.001"
    }

    text = timestamp + "POST" + "/v1/order" + json.dumps(body)
    sign = hmac.new(API_SECRET.encode(), text.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        "API-KEY": API_KEY,
        "API-TIMESTAMP": timestamp,
        "API-SIGN": sign,
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, data=json.dumps(body))
    print(res.json())
    return res.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("📩 Webhook received:", data)

    if data.get("signal") == "buy":
        result = send_order()
        return jsonify(result)
    else:
        return jsonify({"status": "ignored"}), 200

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


