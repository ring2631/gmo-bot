import os
import time
import hmac
import hashlib
import requests
import logging
import re
import json
from urllib.parse import urlencode
from flask import Flask, request, jsonify

# --- 環境変数 ---
API_KEY = os.environ["BITGET_API_KEY"]
API_SECRET = os.environ["BITGET_API_SECRET"]
API_PASSPHRASE = os.environ["BITGET_API_PASSPHRASE"]

SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
RISK_RATIO = 0.35
LEVERAGE = 2

# --- Flask & ログ ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# --- HMACヘッダー作成 ---
def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    full_path = path + ("?" + query if method == "GET" and query else "")
    prehash = timestamp + method + full_path + body
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# --- 現在価格取得 ---
def get_btc_price():
    url = "https://api.bitget.com/api/mix/v1/market/ticker"
    params = {"symbol": SYMBOL}
    headers = make_headers("GET", "/api/mix/v1/market/ticker", urlencode(params))
    res = requests.get(url, headers=headers, params=params).json()
    logger.info(f"[get_btc_price] Ticker: {res}")
    return float(res["data"]["last"])

# --- 証拠金取得 ---
def get_margin_balance():
    url = "https://api.bitget.com/api/mix/v1/account/account"
    params = {"symbol": SYMBOL, "marginCoin": MARGIN_COIN}
    headers = make_headers("GET", "/api/mix/v1/account/account", urlencode(params))
    res = requests.get(url, headers=headers, params=params).json()
    logger.info(f"[get_margin_balance] Account: {res}")
    return float(res["data"]["usdtEquity"])

# --- 注文実行 ---
def execute_order(volatility):
    btc_price = get_btc_price()
    usdt_equity = get_margin_balance()

    order_margin = usdt_equity * RISK_RATIO
    position_value = order_margin * LEVERAGE
    order_size = round(position_value / btc_price, 3)
    logger.info(f"[execute_order] Calculated order size: {order_size} BTC")

    if order_size <= 0:
        raise ValueError("Order size is zero or less. Skipping order.")

    stop_loss_price = round(btc_price * 0.975, 1)
    trail_width = max(volatility * 1.5, 15)
    callback_rate = round(trail_width / btc_price, 4)

    # --- 注文作成 ---
    url = "https://api.bitget.com/api/mix/v1/order/placeOrder"
    body_dict = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "side": "open_long",
        "orderType": "market",
        "size": str(order_size),
        "price": "",
        "timeInForceValue": "normal",
        "presetStopLossPrice": str(stop_loss_price),
        "presetTrailingStopCallbackRate": str(callback_rate)
    }
    body = json.dumps(body_dict)
    headers = make_headers("POST", "/api/mix/v1/order/placeOrder", body=body)
    response = requests.post(url, headers=headers, data=body)
    logger.info(f"[execute_order] Order response: {response.text}")
    return response.json()

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")
            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw)
            volatility = float(match.group(1)) if match else 100.0
            logger.info(f"[webhook] Extracted volatility: {volatility}")

            result = execute_order(volatility)
            return jsonify({"status": "success", "order": result}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget Webhook Bot is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



