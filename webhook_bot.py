from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging

# --- 環境変数から読み込み ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

# --- 署名付きヘッダー作成 ---
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

# --- テスト用：ticker取得 ---
def get_ticker():
    path = "/api/mix/v1/market/ticker"
    query = "?symbol=BTCUSDT_UMCBL"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", path, query)
    res = requests.get(url, headers=headers)
    logger.info("[get_ticker] %s", res.json())
    return res.json()

# --- Webhook エンドポイント ---
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.data.decode("utf-8")
    logger.info("[webhook] Raw: %s", raw)

    if raw.startswith("BUY"):
        logger.info("[webhook] BUY signal detected")
        try:
            vol = float(raw.split("VOL=")[1].strip())
            logger.info("[webhook] Extracted volatility: %s", vol)

            ticker = get_ticker()
            if ticker["code"] != "00000":
                raise Exception("Failed to fetch ticker")

            return jsonify({"status": "ok", "volatility": vol, "price": ticker["data"]["last"]})
        except Exception as e:
            logger.error("[webhook] Error: %s", str(e))
            return jsonify({"status": "error", "msg": str(e)}), 500

    return jsonify({"status": "ignored"})

# --- テストエンドポイント ---
@app.route("/test", methods=["GET"])
def test():
    return jsonify(get_ticker())

# --- 起動 ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render対応
    app.run(host="0.0.0.0", port=port)





