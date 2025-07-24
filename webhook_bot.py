import os
import hmac
import hashlib
import time
import json
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Flask アプリ
app = Flask(__name__)

# 環境変数
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"

# ---- 署名付きヘッダー作成 ----
def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    logger.warning(f"[SIGN DEBUG] timestamp: {timestamp}")
    logger.warning(f"[SIGN DEBUG] method: {method}")
    logger.warning(f"[SIGN DEBUG] path: {path}")
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

# ---- 現在価格取得 ----
def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    response = requests.get(url)
    data = response.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data["data"]["last"])

# ---- 証拠金取得 ----
def get_margin_balance():
    path = f"/api/mix/v1/account/account"
    url = BASE_URL + path + f"?symbol={SYMBOL}"
    headers = make_headers("GET", path)
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        logger.info(f"[get_margin_balance] Response: {data}")
        return data
    except Exception as e:
        logger.error(f"[get_margin_balance] Exception: {e}")
        return None

# ---- Webhook受信 ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.data.decode("utf-8")
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if "BUY" in raw_data:
            logger.info("[webhook] Detected BUY signal")
            price = get_btc_price()
            margin = get_margin_balance()
            if not margin or margin.get("code") != "00000":
                raise Exception("Margin API failed: sign signature error")
            return jsonify({"status": "executed", "price": price})

        return jsonify({"status": "ignored"})

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "Bitget Webhook Bot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

