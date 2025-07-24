from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging
from dotenv import load_dotenv

# .envの読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Flask初期化
app = Flask(__name__)

# 環境変数
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"

# 署名作成

def make_headers(method: str, path: str, body: str = "", query: str = "") -> dict:
    timestamp = str(int(time.time() * 1000))
    message_path = path + (f"?{query}" if query else "")
    message = f"{timestamp}{method.upper()}{message_path}{body}"
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

    logger.warning(f"[SIGN DEBUG] timestamp: {timestamp}")
    logger.warning(f"[SIGN DEBUG] method: {method}")
    logger.warning(f"[SIGN DEBUG] path: {path}")
    logger.warning(f"[SIGN DEBUG] query: {query}")
    logger.warning(f"[SIGN DEBUG] body: {body}")
    logger.warning(f"[SIGN DEBUG] message: {message}")
    logger.warning(f"[SIGN DEBUG] sign: {sign}")

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# BTC価格取得

def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data["data"]["last"])

# 証拠金取得 (symbolなし)

def get_margin_balance():
    path = "/api/mix/v1/account/account"
    url = f"{BASE_URL}{path}"
    headers = make_headers("GET", path)
    res = requests.get(url, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    if data.get("code") != "00000":
        raise ValueError(f"Margin API failed: {data.get('msg')}")
    return float(data["data"]["available"])

# Webhook受信

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.data.decode("utf-8")
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if "BUY" in raw_data:
            logger.info("[webhook] Detected BUY signal")
            price = get_btc_price()
            balance = get_margin_balance()
            logger.info(f"[webhook] Current price: {price}, Balance: {balance}")
            return jsonify({"status": "success", "price": price, "balance": balance})
        else:
            logger.info("[webhook] No BUY signal detected")
            return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# index

@app.route("/")
def index():
    return "Bitget Webhook Bot is running."

# ローカルサーバー
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

