from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import requests
import time
import hmac
import hashlib
import json
import logging

# 初期設定
app = Flask(__name__)
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.environ.get('GMO_API_KEY')
API_SECRET = os.environ.get('GMO_API_SECRET')
BASE_URL = 'https://api.coin.z.com'
SYMBOL = 'BTC_JPY'
LEVERAGE = 2
POSITION_RATIO = 0.35  # 証拠金のうち取引に使う割合

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    text = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), text.encode(), hashlib.sha256).hexdigest()
    return {
        'API-KEY': API_KEY,
        'API-TIMESTAMP': timestamp,
        'API-SIGN': sign,
        'Content-Type': 'application/json'
    }

def get_btc_price():
    url = f"{BASE_URL}/public/v1/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info("[get_btc_price] Response: %s", data)
    if data["status"] == 0 and isinstance(data["data"], list):
        return float(data["data"][0]["last"])
    raise ValueError(f"Invalid response in get_btc_price: {data}")

def get_margin_amount():
    path = "/private/v1/account/assets"
    headers = make_headers("GET", path)
    res = requests.get(BASE_URL + path, headers=headers)
    data = res.json()
    logger.info("[get_margin_amount] Response: %s", data)
    if data["status"] == 0:
        for asset in data["data"]:
            if asset["symbol"] == "JPY":
                return float(asset["available"])
    raise ValueError(f"Invalid margin data: {data}")

def get_volatility():
    url = f"{BASE_URL}/public/v1/klines?symbol={SYMBOL}&interval=1m&limit=100"
    res = requests.get(url)
    data = res.json()
    logger.info("[get_volatility] Response: %s", data)

    if data["status"] == 0 and isinstance(data["data"], list):
        prices = [float(d["high"]) - float(d["low"]) for d in data["data"]]
        return sum(prices) / len(prices)
    raise ValueError(f"Invalid 'data' field: {data}")

def send_order(side):
    price = get_btc_price()
    volatility = get_volatility()
    margin = get_margin_amount()

    position_value = margin * POSITION_RATIO * LEVERAGE
    size = round(position_value / price, 6)
    trail_width = max(volatility * 1.5, 1500)
    stop_loss_price = round(price * 0.975, 0)

    logger.info("[send_order] %s order: size=%s, price=%s, trail=%s, SL=%s", side, size, price, trail_width, stop_loss_price)

    path = '/private/v1/order'
    body = {
        "symbol": SYMBOL,
        "side": side,
        "executionType": "MARKET",
        "size": size,
        "leverageLevel": LEVERAGE,
        "lossCutPrice": stop_loss_price,
        "trailWidth": round(trail_width, 0)
    }

    body_json = json.dumps(body)
    headers = make_headers("POST", path, body_json)
    res = requests.post(BASE_URL + path, headers=headers, data=body_json)
    logger.info("[send_order] Response: %s", res.text)
    return res.json()

@app.route("/", methods=["GET"])
def index():
    return "Webhook bot is running.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_data(as_text=True).strip()
        logger.info("[webhook] Raw data: %r", data)
        if "BUY" in data:
            logger.info("[webhook] Detected BUY signal")
            return jsonify(send_order("BUY"))
        elif "SELL" in data:
            logger.info("[webhook] Detected SELL signal")
            return jsonify(send_order("SELL"))
        else:
            logger.warning("[webhook] Unknown signal: %s", data)
            return jsonify({'status': 'ignored'}), 400
    except Exception as e:
        logger.error("[webhook] Error: %s", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # 環境変数PORTがなければ5000
    app.run(host='0.0.0.0', port=port)

