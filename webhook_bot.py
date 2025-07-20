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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.environ.get('GMO_API_KEY')
API_SECRET = os.environ.get('GMO_API_SECRET')
BASE_URL = 'https://api.coin.z.com'
SYMBOL = 'BTC_JPY'
LEVERAGE = 2

# ---- APIヘッダー作成 ----
def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "API-KEY": API_KEY,
        "API-TIMESTAMP": timestamp,
        "API-SIGN": sign,
        "Content-Type": "application/json"
    }

# ---- 現在価格取得 ----
def get_btc_price():
    url = f"{BASE_URL}/public/v1/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    return float(data["data"][0]["last"])

# ---- 証拠金情報取得 ----
def get_margin_balance():
    path = "/private/v1/account/margin"
    headers = make_headers("GET", path)
    res = requests.get(BASE_URL + path, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    return float(data["data"]["availableMargin"])

# ---- ボラティリティ計算 ----
def get_volatility():
    url = f"{BASE_URL}/public/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": "1H",  # 公式仕様通り
        "limit": 24        # 直近24本
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        logger.info(f"[get_volatility] Response: {data}")
        if data["status"] != 0 or "data" not in data:
            raise ValueError(f"Invalid 'data' field: {data}")
        prices = [float(d["high"]) - float(d["low"]) for d in data["data"]]
        return sum(prices) / len(prices)
    except Exception as e:
        logger.error(f"[get_volatility] Error: {e}")
        raise

# ---- 注文送信 ----
def send_order(side):
    price = get_btc_price()
    volatility = get_volatility()
    margin = get_margin_balance()

    order_margin = margin * 0.35  # 証拠金の35%
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 6)  # 取引数量

    # トレイリング幅（最低1500円）
    trail_width = max(volatility * 1.5, 1500)
    stop_loss = round(price * 0.975, 0)  # 損切ライン（仮）

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

# ---- Flaskルート ----
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
            return jsonify(send_order("BUY"))
        elif 'SELL' in raw_data:
            logger.info("[webhook] Detected SELL signal")
            return jsonify(send_order("SELL"))
        else:
            logger.warning("[webhook] Invalid signal received")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)


