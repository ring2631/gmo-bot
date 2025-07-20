import os
import json
import logging
from flask import Flask, request
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

API_KEY = os.environ.get("GMO_API_KEY")
API_SECRET = os.environ.get("GMO_API_SECRET")

BASE_URL = "https://api.coin.z.com"
SYMBOL = "BTC_JPY"
LEVERAGE = 2
MARGIN_RATIO = 0.35


def get_btc_price():
    url = f"{BASE_URL}/public/v1/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info("[get_btc_price] Response: %s", data)

    if data["status"] == 0 and isinstance(data["data"], list):
        return int(float(data["data"][0]["ask"]))
    else:
        logger.error("[get_btc_price] Error: Invalid 'data' field: %s", data)
        return None


def get_margin():
    url = f"{BASE_URL}/private/v1/account/assets"
    headers = {"API-KEY": API_KEY}
    res = requests.get(url, headers=headers)
    data = res.json()
    logger.info("[get_margin] Response: %s", data)

    if data["status"] == 0:
        for asset in data["data"]:
            if asset["symbol"] == SYMBOL:
                return int(float(asset["available"]))
    logger.error("[get_margin] Error: Invalid 'data' field: %s", data)
    return None


def get_volatility():
    url = f"{BASE_URL}/public/v1/klines?symbol={SYMBOL}&interval=1min&limit=100"
    res = requests.get(url)
    data = res.json()
    logger.info("[get_volatility] Response: %s", data)

    if data["status"] == 0 and isinstance(data["data"], list):
        prices = [float(d["high"]) - float(d["low"]) for d in data["data"]]
        avg_volatility = sum(prices) / len(prices)
        return avg_volatility
    else:
        logger.error("[get_volatility] Error: Invalid 'data' field: %s", data)
        return None


def send_order(side, price, size):
    url = f"{BASE_URL}/private/v1/order"
    headers = {
        "API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "symbol": SYMBOL,
        "side": side,
        "executionType": "MARKET",
        "size": str(size),
        "price": str(price),
        "timeInForce": "FAK",
        "leverageLevel": LEVERAGE
    }
    res = requests.post(url, headers=headers, data=json.dumps(body))
    data = res.json()
    logger.info("[send_order] Response: %s", data)

    if data["status"] != 0:
        logger.error("[send_order] Error: Invalid 'data' field: %s", data)


@app.route("/", methods=["GET"])
def index():
    return "Webhook Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_data = request.data.decode("utf-8").strip()
    logger.info("[webhook] Raw data: '%s'", raw_data)

    if raw_data == "BUY":
        logger.info("[webhook] Detected BUY signal")

        price = get_btc_price()
        if price is None:
            return "Failed to get price", 500

        volatility = get_volatility()
        if volatility is None:
            return "Failed to get volatility", 500

        margin = get_margin()
        if margin is None:
            return "Failed to get margin", 500

        # 取引サイズを計算
        margin_to_use = margin * MARGIN_RATIO
        size = round(margin_to_use * LEVERAGE / price, 6)

        send_order("BUY", price, size)
        return "Order sent", 200

    return "Invalid signal", 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Renderなら環境変数、ローカルなら5000
    app.run(host="0.0.0.0", port=port)

