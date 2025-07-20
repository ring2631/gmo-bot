from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import time
import hmac
import hashlib
import json
import requests

load_dotenv()  # .env 読み込み

API_KEY = os.environ.get('GMO_API_KEY')
API_SECRET = os.environ.get('GMO_API_SECRET')
BASE_URL = 'https://api.coin.z.com'
PRODUCT_CODE = 'BTC_JPY'
LEVERAGE = 2
MARGIN_JPY = 30000  # 証拠金
SLIPPAGE_THRESHOLD = 0.015  # 1.5% 以上の価格乖離でキャンセル
MAX_DRAWDOWN = 0.1  # 証拠金の10%以上の損失で強制停止

app = Flask(__name__)

trade_active = True  # 強制停止状態を管理するフラグ


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
    return float(res.json()['data']['last'])


def get_volatility():
    path = '/public/v1/klines?symbol=BTC_JPY&interval=1m&limit=100'
    res = requests.get(BASE_URL + path)
    data = res.json()['data']
    vol_list = [float(c['high']) - float(c['low']) for c in data]
    return sum(vol_list) / len(vol_list)


def get_equity():
    # 仮の実装。GMOの口座資産確認APIがあるならここで使う
    return MARGIN_JPY


def send_order(side):
    global trade_active
    if not trade_active:
        log("取引停止中。スキップします。")
        return {'status': 'trading_disabled'}

    price = get_btc_price()
    volatility = get_volatility()
    
    # スリッページ検出（過去数分の平均値と比較なども可）
    recent_price = price  # 最新価格とアラート価格が一致してる前提（ここを改良可）
    alert_price = price   # Webhookトリガー時に埋め込まれる想定値に置換すること
    slippage = abs(price - alert_price) / alert_price
    if slippage > SLIPPAGE_THRESHOLD:
        log(f"スリッページ大: {slippage:.2%} - 注文中止")
        return {'status': 'slippage_detected'}

    position_value = MARGIN_JPY * 0.35 * LEVERAGE
    size = round(position_value / price, 6)

    trail_width = max(volatility * 1.5, 1500)
    stop_loss_price = round(price * 0.975, 0)

    # 強制カット判定：equity < 証拠金の90%
    if get_equity() < MARGIN_JPY * (1 - MAX_DRAWDOWN):
        trade_active = False
        log("損失が大きすぎるため、取引を一時停止します。")
        return {'status': 'force_stopped'}

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
        log("Invalid signal")
        return jsonify({'status': 'ignored'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


