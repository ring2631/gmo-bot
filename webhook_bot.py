from flask import Flask, request, jsonify
import requests
import time
import hmac
import hashlib
import json
import os
import logging
from dotenv import load_dotenv

# Flask setup
app = Flask(__name__)
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Constants from .env
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT_UMCBL")
LEVERAGE = int(os.getenv("LEVERAGE", 2))
MARGIN_RATIO = 0.35

# Endpoint and headers
BASE_URL = "https://api.bitget.com"

# --- Signature Generation ---
def generate_signature(timestamp, method, request_path, body_str):
    message = f"{timestamp}{method}{request_path}{body_str}"
    mac = hmac.new(API_SECRET.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256)
    return mac.hexdigest()

# --- Headers ---
def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# --- Get BTC Price ---
def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}&productType=umcbl"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data["data"]["last"])

# --- Get Account Balance ---
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    query = f"?symbol={SYMBOL}"
    headers = get_headers("GET", path + query)
    res = requests.get(BASE_URL + path + query, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    return float(data["data"]["available"])

# --- Place Order ---
def send_order(side, volatility):
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * MARGIN_RATIO
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 6)

    trail_width = max(float(volatility) * 1.5, 15)
    stop_loss = round(price * 0.975, 2)

    path = "/api/mix/v1/order/placePlan"
    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side.lower(),
        "orderType": "market",
        "triggerPrice": str(price),
        "planType": "track_plan",
        "triggerType": "market_price",
        "executePrice": "",
        "presetStopLossPrice": str(stop_loss),
        "triggerProfitPrice": "",
        "rangeRate": str(trail_width / price)
    }

    body_str = json.dumps(body)
    headers = get_headers("POST", path, body_str)
    res = requests.post(BASE_URL + path, headers=headers, data=body_str)
    logger.info(f"[send_order] Response: {res.status_code} {res.text}")
    return res.json()

# --- Extract volatility from webhook ---
def extract_volatility(payload):
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx が見つかりません")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# --- Webhook route ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if 'BUY' in raw_data:
            logger.info("[webhook] Detected BUY signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("BUY", vol))
        elif 'SELL' in raw_data:
            logger.info("[webhook] Detected SELL signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("SELL", vol))
        else:
            logger.warning("[webhook] Invalid signal received")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Index route ---
@app.route('/')
def index():
    return "Bitget Webhook Bot is running"

# --- Run ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
