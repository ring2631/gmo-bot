import os
import time
import hmac
import hashlib
import requests
import logging
import re
import json
from flask import Flask, request, jsonify

# --- 環境変数（Renderなどで設定） ---
API_KEY = os.environ["BITGET_API_KEY"]
API_SECRET = os.environ["BITGET_API_SECRET"]
API_PASSPHRASE = os.environ["BITGET_API_PASSPHRASE"]

# --- 各種設定 ---
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
RISK_RATIO = 0.35
LEVERAGE = 2

# --- Flask 初期化 ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")


# --- Bitget署名付きヘッダー生成 ---
def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    full_path = f"{path}?{query}" if method.upper() in ["GET", "DELETE"] and query else path
    prehash = f"{timestamp}{method.upper()}{full_path}{body or ''}"
    sign = hmac.new(
        API_SECRET.encode(),
        prehash.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }


# --- 現在価格取得 ---
def get_btc_price():
    path = "/api/mix/v1/market/ticker"
    query = f"symbol={SYMBOL}"
    url = f"https://api.bitget.com{path}?{query}"
    headers = make_headers("GET", path, query=query)
    res = requests.get(url, headers=headers).json()
    logger.info(f"[get_btc_price] Ticker: {res}")
    return float(res["data"]["last"])


# --- 証拠金（USDT）取得（GET + query + 署名に含める方式）---
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


# --- 注文実行（トレイリングストップ + 損切り）---
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

    body_dict = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "side": "open_long",
        "orderType": "market",
        "size": str(order_size),
        "timeInForceValue": "normal",
        "presetStopLossPrice": str(stop_loss_price),
        "presetTrailingStopCallbackRate": str(callback_rate)
    }

    body = json.dumps(body_dict)
    headers = make_headers("POST", "/api/mix/v1/order/placeOrder", body=body)
    url = "https://api.bitget.com/api/mix/v1/order/placeOrder"
    response = requests.post(url, headers=headers, data=body)
    logger.info(f"[execute_order] Order response: {response.text}")
    return response.json()


# --- Webhook受信エンドポイント ---
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


# --- 動作確認用エンドポイント ---
@app.route("/")
def home():
    return "Bitget Webhook Bot is Running!"


# --- 実行 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)





