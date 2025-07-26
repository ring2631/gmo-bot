from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging
from dotenv import load_dotenv

# 環境変数の読み込み（Render でも動作）
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Flaskアプリ
app = Flask(__name__)

# 署名付きヘッダー作成
def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}{query}{body}"
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
    }
    if method.upper() != "GET":
        headers["Content-Type"] = "application/json"
    return headers

# 現在の価格取得（署名付き）
def get_ticker():
    path = "/api/mix/v1/market/ticker"
    query = "?symbol=BTCUSDT_UMCBL"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", path, query=query)
    response = requests.get(url, headers=headers)
    logger.info("[get_ticker] Response: %s", response.json())
    return response.json()

# 証拠金残高の取得（修正済み）
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    query = ""  # ← symbolを付けないことで署名ミスマッチを防ぐ
    url = f"{BASE_URL}{path}"
    headers = make_headers("GET", path, query=query)
    response = requests.get(url, headers=headers)
    logger.info("[get_margin_balance] Response: %s", response.json())
    return response.json()

# Webhook受信エンドポイント
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
                raise Exception("Ticker fetch failed")

            account = get_margin_balance()
            if account["code"] != "00000":
                raise Exception(f"Margin API error: {account['msg']}")

            return jsonify({
                "status": "success",
                "volatility": volatility,
                "price": ticker["data"]["last"],
                "margin_balance": account["data"]
            })

        except Exception as e:
            logger.error("[webhook] Error: %s", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ignored"})

# テストエンドポイント
@app.route("/test", methods=["GET"])
def test():
    return jsonify(get_ticker())

# 起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)








