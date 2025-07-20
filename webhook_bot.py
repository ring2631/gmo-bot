from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import requests
import time
import hmac
import hashlib
import json
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)
load_dotenv()

API_KEY = os.environ.get('GMO_API_KEY')
API_SECRET = os.environ.get('GMO_API_SECRET')
BASE_URL = 'https://api.coin.z.com'
PRODUCT_CODE = 'BTC_JPY'
LEVERAGE = 2
MARGIN_JPY = 30000  # 証拠金

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    text = timestamp + method + path + body
    sign = hmac.new(API_SECRET.encode(), text.encode(), hashlib.sha256).hexdigest()
    return {
        'API-KEY': API_KEY,
        'API-TIMESTAMP': timestamp,
        'API-SIGN': sign,
        'Content-Type': 'application/json'
    }

def get_btc_price():
    path = '/public/v1/ticker?symbol=BTC_JPY'
    url = BASE_URL + path
    res = requests.get(url)
    json_data = res.json()
    logger.info(f"[get_btc_price] Response: {json_data}")
    if 'data' not in json_data or not isinstance(json_data['data'], list):
        raise ValueError(f"Invalid 'data' field: {json_data}")
    return float(json_data['data'][0]['last'])

def get_volatility():
    path = '/public/v1/klines?symbol=BTC_JPY&interval=1min&limit=100'
    url = BASE_URL + path
    res = requests.get(url)
    json_data = res.json()
    logger.info(f"[get_volatility] Response: {json_data}")
    if 'data' not in json_data or not isinstance(json_data['data'], list):
        raise ValueError(f"Invalid 'data' field: {json_data}")
    vol_list = [float(c['high']) - float(c['low']) for c in json_data['data']]
    return sum(vol_list) / len(vol_list)

def send_order(side):
    try:
        price = get_btc_price()
        volatility = get_volatility()

        position_value = MARGIN_JPY * 0.35 * LEVERAGE
        size = round(position_value / price, 6)

        trail_width = max(volatility * 1.5, 1500)
        stop_loss_price = round(price * 0.975, 0)

        logger.info(f"[send_order] {side} order: size={size}, price={price}, trail={trail_width}, SL={stop_loss_price}")

        path = '/private/v1/order'
        body = {
            "symbol": PRODUCT_CODE,
            "side": side,
            "executionType": "MARKET",
            "size": size,
            "leverageLevel": LEVERAGE,
            "lossCutPrice": stop_loss_price,
            "trailWidth": round(trail_width, 0)
        }

        body_json = json.dumps(body)
        headers = make_headers("POST", path, body_json)
        res = requests.post(BASE_URL + path, headers=headers, data=body_json)

        logger.info(f"[send_order] Response status: {res.status_code}, body: {res.text}")
        return res.json()
    except Exception as e:
        logger.error(f"[send_order] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return "Webhook bot is running"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_data(as_text=True).strip()
        logger.info(f"[webhook] Raw data: '{data}'")
        if 'BUY' in data:
            logger.info("[webhook] Detected BUY signal")
            return jsonify(send_order("BUY"))
        elif 'SELL' in data:
            logger.info("[webhook] Detected SELL signal")
            return jsonify(send_order("SELL"))
        else:
            logger.warning("[webhook] Invalid signal received")
            return jsonify({'status': 'ignored'}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


