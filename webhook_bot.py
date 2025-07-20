import os
import requests
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = "https://api.coin.z.com"
SYMBOL = "BTC_JPY"
LEVERAGE = 2

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

def get_btc_price():
    url = f"{BASE_URL}/public/v1/ticker"
    params = {"symbol": SYMBOL}
    response = requests.get(url, params=params)
    data = response.json()
    logger.info("[get_btc_price] Response: %s", data)
    return data

def get_volatility():
    url = f"{BASE_URL}/public/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": "1H",
        "limit": 24  # 過去24時間分
    }
    response = requests.get(url, params=params)
    data = response.json()
    logger.info("[get_volatility] Response: %s", data)
    return data

def get_margin():
    url = f"{BASE_URL}/private/v1/account/assets"
    headers = {
        "API-KEY": API_KEY,
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    logger.info("[get_margin] Response: %s", data)
    if data.get("status") == 0 and "data" in data:
        for asset in data["data"]:
            if asset["symbol"] == SYMBOL:
                return float(asset["available"])
    return None

def send_order(price, size):
    url = f"{BASE_URL}/private/v1/order"
    headers = {
        "API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "symbol": SYMBOL,
        "side": "BUY",
        "executionType": "MARKET",
        "size": str(size),
        "price": str(price),
        "leverageLevel": LEVERAGE
    }
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    logger.info("[send_order] Response: %s", data)
    return data

@app.route("/", methods=["GET"])
def index():
    return "GMO Webhook Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    raw_data = request.data.decode("utf-8")
    logger.info("[webhook] Raw data: %r", raw_data)

    if "BUY" in raw_data.upper():
        logger.info("[webhook] Detected BUY signal")

        price_data = get_btc_price()
        volatility_data = get_volatility()

        if price_data.get("status") != 0 or "data" not in price_data:
            logger.error("[webhook] Error: Invalid price data: %s", price_data)
            return jsonify({"error": "Invalid price data"}), 500

        if volatility_data.get("status") != 0 or "data" not in volatility_data:
            logger.error("[webhook] Error: Invalid volatility data: %s", volatility_data)
            return jsonify({"error": "Invalid volatility data"}), 500

        last_price = float(price_data["data"][0]["last"])
        margin = get_margin()
        if margin is None:
            logger.error("[webhook] Error: Could not retrieve margin")
            return jsonify({"error": "Could not retrieve margin"}), 500

        amount_to_use = margin * 0.35
        size = round((amount_to_use * LEVERAGE) / last_price, 4)

        result = send_order(last_price, size)
        return jsonify(result)

    return jsonify({"status": "ignored"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)

