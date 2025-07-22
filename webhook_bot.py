from flask import Flask, request, jsonify
import requests
import time
import hmac
import hashlib
import json
import os
import logging
from dotenv import load_dotenv

# 初期化
app = Flask(__name__)
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
LEVERAGE = int(os.getenv("LEVERAGE", 2))
MARGIN_RATIO = 0.35
VOL_MULTIPLIER = 1.5

# ヘッダー作成
def make_headers(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    sign = hmac.new(API_SECRET.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# BTC価格取得
def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}&productType=umcbl"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data['data']['last'])

# 証拠金取得
def get_balance():
    timestamp = str(int(time.time() * 1000))
    path = "/api/mix/v1/account/account"
    url = BASE_URL + path + f"?symbol={SYMBOL}&marginCoin=USDT"
    headers = make_headers(timestamp, "GET", path + f"?symbol={SYMBOL}&marginCoin=USDT", "")
    res = requests.get(url, headers=headers)
    data = res.json()
    logger.info(f"[get_balance] Response: {data}")
    return float(data['data']['available'])

# 注文送信（成行）
def send_order(side, volatility):
    price = get_btc_price()
    margin = get_balance()
    
    order_margin = margin * MARGIN_RATIO
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 3)

    trail_value = max(float(volatility) * VOL_MULTIPLIER, 15.0)
    stop_loss = round(price * 0.975, 1)

    timestamp = str(int(time.time() * 1000))
    path = "/api/mix/v1/order/placeOrder"
    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "side": side.lower(),
        "orderType": "market",
        "size": str(size),
        "productType": "umcbl",
        "presetStopLossPrice": str(stop_loss),
        "timeInForceValue": "normal"
    }
    body_json = json.dumps(body)
    headers = make_headers(timestamp, "POST", path, body_json)
    res = requests.post(BASE_URL + path, headers=headers, data=body_json)
    logger.info(f"[send_order] Response: {res.status_code} {res.text}")
    return res.json()

# VOL抽出
def extract_volatility(payload):
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL not found")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if 'BUY' in raw_data:
            logger.info("[webhook] Detected BUY signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("buy", vol))
        elif 'SELL' in raw_data:
            logger.info("[webhook] Detected SELL signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("sell", vol))
        else:
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
