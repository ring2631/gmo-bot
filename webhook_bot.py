from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import json
import os
import time
import logging
from dotenv import load_dotenv

# 初期化
app = Flask(__name__)
load_dotenv()

# ログ設定
import logging
logging.basicConfig(level=logging.DEBUG)  # ← INFO → DEBUG に変更
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.environ.get("GMO_API_KEY")
API_SECRET = os.environ.get("GMO_API_SECRET")
BASE_URL = 'https://api.coin.z.com'
SYMBOL = 'BTC_JPY'
LEVERAGE = 2

# APIヘッダー作成
def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

    # ← これらの print が今まだ見えてない！
    print(f"[DEBUG] timestamp: {timestamp}")
    print(f"[DEBUG] method: {method}")
    print(f"[DEBUG] path: {path}")
    print(f"[DEBUG] body: '{body}'")  # ''つけて空かどうか確認しやすく
    print(f"[DEBUG] message: {message}")
    print(f"[DEBUG] sign: {sign}")

    return {
        "API-KEY": API_KEY,
        "API-TIMESTAMP": timestamp,
        "API-SIGN": sign,
        "Content-Type": "application/json"
    }



# 現在価格取得
def get_btc_price():
    url = f"{BASE_URL}/public/v1/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data["data"][0]["last"])

# 証拠金取得
def get_margin_balance():
    path = "/private/v1/account/margin"
    headers = make_headers("GET", path)
    res = requests.get(BASE_URL + path, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    if data["status"] != 0:
        raise ValueError("Margin API failed")
    return float(data["data"]["availableMargin"])

# 注文送信
def send_order(side, volatility):
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 6)

    trail_width = max(float(volatility) * 1.5, 1500)
    stop_loss = round(price * 0.975, 0)

    body = {
        "symbol": SYMBOL,
        "side": side,
        "executionType": "MARKET",
        "size": size,
        "leverageLevel": LEVERAGE,
        "lossCutPrice": stop_loss,
        "trailWidth": round(trail_width)
    }
    path = "/private/v1/order"
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

# WebhookからVOL値を取り出す
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
