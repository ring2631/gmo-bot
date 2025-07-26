from flask import Flask, request, jsonify
import hmac
import hashlib
import base64
import time
import requests
import os
import logging
import json

# Flask アプリ初期化
app = Flask(__name__)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数から API キーなどを取得（Renderの環境変数設定に依存）
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"

# 署名付きヘッダー生成関数
def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = timestamp + method.upper() + path + body  # ←ここだけ upper()
    logger.info(f"[make_headers] prehash: {prehash}")

    sign = base64.b64encode(
        hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }


# BTC価格取得（GET）
def get_ticker():
    path = f"/api/mix/v1/market/ticker?symbol={SYMBOL}"
    url = BASE_URL + path
    headers = make_headers("GET", path)
    response = requests.get(url, headers=headers)
    logger.info(f"[get_ticker] Response: {response.json()}")
    return response.json()

# 証拠金取得（POST）
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    url = BASE_URL + path
    body_dict = {"symbol": SYMBOL}

    # 🔸 ← ここ超重要！スペースを絶対入れないために使う
    body = json.dumps(body_dict, separators=(',', ':'))

    headers = make_headers("POST", path, body)

    # 🔸 data=body で送る（json=body_dict にしない）
    response = requests.post(url, headers=headers, data=body)
    logger.info(f"[get_margin_balance] Response: {response.json()}")
    return response.json()

# Webhook受信
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.data.decode("utf-8")
        logger.info(f"[webhook] Raw: {data}")

        if "BUY" in data:
            logger.info("[webhook] BUY signal detected")
            try:
                vol_str = data.split("VOL=")[1].strip()
                volatility = float(vol_str)
                logger.info(f"[webhook] Extracted volatility: {volatility}")
            except Exception as e:
                logger.error(f"[webhook] Failed to extract volatility: {e}")
                return jsonify({"error": "Invalid volatility format"}), 400

            # APIテスト
            get_ticker()
            margin_resp = get_margin_balance()
            if margin_resp["code"] != "00000":
                raise Exception(f"Margin API error: {margin_resp['msg']}")

            return jsonify({"status": "success"}), 200

        return jsonify({"message": "No actionable signal"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"error": str(e)}), 500

# アプリ起動
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

