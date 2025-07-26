from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging

# 環境変数取得（Render環境でセット済みであること）
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Flask アプリ初期化
app = Flask(__name__)

# ---- ヘッダー作成（署名） ----
def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    full_path = f"{path}{query}"
    prehash = f"{timestamp}{method.upper()}{full_path}{body}"

    # NoneTypeエラー対策（明示チェック）
    if not API_SECRET:
        raise ValueError("API_SECRET is not set")

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

# ---- 現在価格取得 ----
def get_ticker():
    path = "/api/mix/v1/market/ticker"
    query = "?symbol=BTCUSDT_UMCBL"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", path, query=query)
    response = requests.get(url, headers=headers)
    logger.info("[get_ticker] Response: %s", response.json())
    return response.json()

# ---- 証拠金情報取得（Margin）----
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    query = "?symbol=BTCUSDT_UMCBL"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", path, query=query)
    response = requests.get(url, headers=headers)
    logger.info("[get_margin_balance] Response: %s", response.json())
    return response.json()

# ---- Webhook受信 ----
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
                raise Exception("Failed to fetch ticker")

            account = get_margin_balance()
            if account["code"] != "00000":
                raise Exception("Margin API error: %s" % account["msg"])

            return jsonify({"status": "success", "volatility": volatility})

        except Exception as e:
            logger.error("[webhook] Error: %s", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ignored"})

# ---- テスト用エンドポイント ----
@app.route("/test", methods=["GET"])
def test():
    return jsonify(get_ticker())

# ---- 起動 ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render用ポート
    app.run(host="0.0.0.0", port=port)






