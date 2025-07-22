from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import json
import os
import time
import logging
from dotenv import load_dotenv

# Flask初期化
app = Flask(__name__)
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.environ.get("BITGET_API_KEY")
API_SECRET = os.environ.get("BITGET_API_SECRET")
API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2

# Bitget用ヘッダ作成

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
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

# 証拠金取得

def get_margin_balance():
    path = "/api/mix/v1/account/account?symbol=BTCUSDT_UMCBL"
    headers = make_headers("GET", path)
    res = requests.get(BASE_URL + path, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    if data["code"] != "00000":
        raise ValueError("Margin API failed")
    return float(data["data"]["available"])

# 注文送信

def send_order(side, volatility):
    price = get_btc_price()
    margin = get_margin_balance()
    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 4)  # Bitgetの単位数により調整

    trail_width = max(float(volatility) * 1.5, 15)
    stop_loss = round(price * 0.975, 2)

    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side.lower(),
        "orderType": "market",
        "timeInForceValue": "normal",
        "leverage": str(LEVERAGE),
        "presetStopLossPrice": str(stop_loss),
        "triggerType": "fill_price",
        "presetTrailingStopCallbackRatio": str(trail_width / price)  # 平衡点、bitgetの基準に合わせる
    }
    path = "/api/mix/v1/order/place-order"
    body_json = json.dumps(body)
    headers = make_headers("POST", path, body_json)

    try:
        res = requests.post(BASE_URL + path, headers=headers, data=body_json)
        logger.info(f"[send_order] Response: {res.status_code} {res.text}")
        return res.json()
    except Exception as e:
        logger.error(f"[send_order] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/', methods=['GET'])
def index():
    return "Webhook Bot is running"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if 'BUY' in raw_data:
            logger.info("[webhook] Detected BUY signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("BUY", vol))
        elif 'SELL' in raw_data:
            logger.info("[webhook] Detected SELL signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("SELL", vol))
        else:
            logger.warning("[webhook] Invalid signal received")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# WebhookからVOL値を抽出

def extract_volatility(payload):
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx が見つかりません")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)

