import os
import hmac
import hashlib
import time
import requests
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"

# Initialize app and logger
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ---- Signature Function ----
def generate_signature(timestamp, method, path, query_string="", body=""):
    if method in ["GET", "DELETE"]:
        message = f"{timestamp}{method}{path}{query_string}"
    else:
        message = f"{timestamp}{method}{path}{body}"
    logger.warning(f"[SIGN DEBUG] message: {message}")
    return hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

# ---- Header Function ----
def make_headers(method, path, query_string="", body=""):
    timestamp = str(int(time.time() * 1000))
    sign = generate_signature(timestamp, method, path, query_string, body)
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }
    return headers

# ---- Get BTC Price ----
def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data['data']['last']) if data['code'] == '00000' else None

# ---- Get Margin Balance ----
def get_margin_balance():
    method = "GET"
    path = "/api/mix/v1/account/account"
    query = f"symbol={SYMBOL}"
    url = f"{BASE_URL}{path}?{query}"
    headers = make_headers(method, path, query_string=query)
    logger.warning(f"[SIGN DEBUG] path: {path}")
    logger.warning(f"[SIGN DEBUG] query: {query}")
    res = requests.get(url, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    if data['code'] != '00000':
        raise Exception(f"Margin API failed: {data['msg']}")
    return data['data']

# ---- Execute Order (Mockup) ----
def execute_order(volume):
    logger.info(f"Executing order with volume: {volume}")
    # 実際の注文処理はここに記述（今は割愛）
    return True

# ---- Webhook ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.data.decode('utf-8')
        logger.info(f"[webhook] Raw data: '{data}'")
        if "BUY" in data:
            logger.info("[webhook] Detected BUY signal")
            price = get_btc_price()
            margin = get_margin_balance()
            # 必要に応じて計算処理
            execute_order(volume=0.01)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget Webhook Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)