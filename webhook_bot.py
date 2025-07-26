import hmac
import hashlib
import time
import json
import base64
import logging
import os
import requests
from flask import Flask, request, jsonify

# 環境変数（Render 側で設定済み想定）
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

# --- 署名付きヘッダー作成 ---
def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    method = method.upper()
    prehash = f"{timestamp}{method}{path}{body}"
    logger.info(f"[make_headers] timestamp: {timestamp}")
    logger.info(f"[make_headers] prehash: {prehash}")
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,  # ← base64不要！
        "Content-Type": "application/json"
    }

# --- 現在価格取得（GET） ---
def get_ticker():
    path = f"/api/mix/v1/market/ticker?symbol={SYMBOL}"
    url = BASE_URL + path
    headers = make_headers("GET", path)
    response = requests.get(url, headers=headers)
    logger.info(f"[get_ticker] Response: {response.json()}")
    return response.json()

# --- 証拠金情報取得（POST） ---
def get_margin_balance():
    path = "/api/mix/v1/account/account"
    url = BASE_URL + path

    try:
        body_dict = {"symbol": SYMBOL}  # 🔴← これが絶対に必要！！
        body = json.dumps(body_dict, separators=(',', ':'))
        headers = make_headers("POST", path, body)

        logger.info(f"[get_margin_balance] body: {body}")
        logger.info(f"[get_margin_balance] headers: {headers}")

        response = requests.post(url, headers=headers, data=body)
        logger.info(f"[get_margin_balance] Response: {response.json()}")
        return response.json()

    except Exception as e:
        logger.error(f"[get_margin_balance] Exception in signing: {e}")
        return {"code": "99999", "msg": f"local error: {str(e)}"}



# --- Webhook受信エンドポイント ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.data.decode("utf-8").strip()
    logger.info(f"[webhook] Raw: {data}")

    try:
        if data.startswith("BUY"):
            logger.info("[webhook] BUY signal detected")
            vol_line = [line for line in data.splitlines() if "VOL=" in line]
            if vol_line:
                vol_str = vol_line[0].split("VOL=")[-1].strip()
                volatility = float(vol_str)
                logger.info(f"[webhook] Extracted volatility: {volatility}")

                # API呼び出しテスト
                get_ticker()
                get_margin_balance()

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


