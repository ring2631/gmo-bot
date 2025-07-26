import os
import hmac
import hashlib
import time
import json
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
MARGIN_COIN = "USDT"
SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2
TRADE_MARGIN_RATE = 0.35

# Init app and logger
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Create headers for Bitget REST API
def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    if method.upper() in ["GET", "DELETE"] and query:
        prehash = f"{timestamp}{method.upper()}{path}?{query}"
    else:
        prehash = f"{timestamp}{method.upper()}{path}{body}"

    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Get latest BTC price
def get_btc_price():
    url = f"https://api.bitget.com/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url).json()
    logger.info(f"[get_btc_price] Ticker: {res}")
    return float(res["data"]["last"])

# Get margin balance
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    query = f"marginCoin={MARGIN_COIN}"
    url = f"https://api.bitget.com{path}?{query}"
    headers = make_headers("GET", path, query=query)
    res = requests.get(url, headers=headers).json()
    logger.info(f"[get_margin_balance] Account: {res}")
    if res["code"] != "00000":
        raise Exception(f"Margin API error: {res['msg']}")
    return float(res["data"]["usdtEquity"])

# Place order
def place_order(price, vol):
    equity = get_margin_balance()
    trade_amt_usdt = equity * TRADE_MARGIN_RATE
    trade_amt_base = round((trade_amt_usdt * LEVERAGE) / price, 4)

    callback_rate = round(min(max((vol * 1.5 / price) * 100, 0.1), 5), 2)
    stop_loss_price = round(price * 0.975, 1)

    body_dict = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "size": str(trade_amt_base),
        "side": "open_long",
        "orderType": "market",
        "presetStopLossPrice": str(stop_loss_price),
        "presetTrailingStopCallbackRate": str(callback_rate)
    }
    body = json.dumps(body_dict, separators=(',', ':'))
    path = "/api/mix/v1/order/placeOrder"
    url = f"https://api.bitget.com{path}"
    headers = make_headers("POST", path, body=body)

    res = requests.post(url, headers=headers, data=body).json()
    logger.info(f"[place_order] Order response: {res}")
    return res

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw: {data}")

        if "BUY" in data:
            logger.info("[webhook] BUY signal detected")
            try:
                vol = float(data.split("VOL=")[1].strip())
                logger.info(f"[webhook] Extracted volatility: {vol}")
            except:
                return jsonify({"error": "VOL parse failed"}), 400

            price = get_btc_price()
            res = place_order(price, vol)
            return jsonify(res), 200

        return jsonify({"message": "No valid signal"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"error": str(e)}), 500

# Start
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)





