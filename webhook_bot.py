from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging
import json

# 環境変数からAPIキー類を取得（Render環境）
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}{body}"
    logger.info("[make_headers] timestamp: %s", timestamp)
    logger.info("[make_headers] prehash: %s", prehash)

    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }
    return headers

def get_ticker():
    path = "/api/mix/v1/market/ticker"
    query = "?symbol=BTCUSDT_UMCBL"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", f"{path}{query}")
    response = requests.get(url, headers=headers)
    logger.info("[get_ticker] Response: %s", response.json())
    return response.json()

def get_margin_balance():
    path = "/api/mix/v1/account/account"
    body_dict = {"symbol": "BTCUSDT_UMCBL"}
    body_str = json.dumps(body_dict, separators=(",", ":"))
    url = f"{BASE_URL}{path}"
    headers = make_headers("POST", path, body=body_str)
    response = requests.post(url, headers=headers, data=body_str)
    logger.info("[get_margin_balance] Response: %s", response.json())
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    raw_data = request.data.decode("utf-8")
    logger.info("[webhook] Raw: %s", raw_data)

    if raw_data.startswith("BUY"):
        logger.info("[webhook] BUY signal detected")

        try:
            vol_part = raw_data.split("VOL=")[1]
            volatility = float(vol_part.strip())
            logger.info("[webhook] Extracted volatility: %s", volatility)

            ticker = get_ticker()
            if ticker["code"] != "00000":
                raise Exception("Failed to fetch ticker")

            account = get_margin_balance()
            if account["code"] != "00000":
                raise Exception(f"Margin API error: {account['msg']}")

            return jsonify({"status": "success", "volatility": volatility})

        except Exception as e:
            logger.error("[webhook] Error: %s", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ignored"})

@app.route("/test", methods=["GET"])
def test():
    return jsonify(get_ticker())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

