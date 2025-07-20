from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import time
import requests
import hmac
import hashlib
import json

load_dotenv()

API_KEY = os.environ.get('GMO_API_KEY')
API_SECRET = os.environ.get('GMO_API_SECRET')
BASE_URL = 'https://api.coin.z.com'
PRODUCT_CODE = 'BTC_JPY'
LEVERAGE = 2
MARGIN_JPY = 30000  # 証拠金

app = Flask(__name__)

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

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
    res = requests.get(BASE_URL + path)
    data = res.json()['data']

    if isinstance(data, list) and len(data) > 0:
        return float(data[0]['last'])  # リスト対応
    elif isinstance(data, dict):
        return float(data['last'])     # 辞書対応
    else:
        raise ValueError("Unexpected ticker format: " + str(data))

def get_volatility():
    path = '/public/v1/klines?symbol=BTC_JPY&interval=1m&limit=100'
    res = requests.get(BASE_URL + path)
    data = res.json()['data']
    vol_list = [float(c['high']) - float(c['low']) for c in data]
    return sum(vol_list) / len(vol_list)

def send_order(side):
    price = get_btc_price()
    volatility = get_volatility()

    position_value = MARGIN_JPY * 0.35 * LEVERAGE
    size = round(position_value / price, 6)

    trail_width = max(volatility * 1.5, 1500)
    stop_loss_price = round(price * 0.975, 0)

    log(f"{side} order: size={size}, price={price}, trail={trail_width}, SL={stop_loss_price}")

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

    headers = make_headers("POST", path, json.dumps(body))
    res = requests.post(BASE_URL + path, headers=headers, data=json.dumps(body))
    log(res.text)
    return res.json()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_data(as_text=True)
    if 'BUY' in data:
        return jsonify(send_order("BUY"))
    elif 'SELL' in data:
        return jsonify(send_order("SELL"))
    else:
        log("Invalid signal received")
        return jsonify({'status': 'ignored'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


