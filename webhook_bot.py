from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import os
import logging
from dotenv import load_dotenv

# ロード環境変数
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
LEVERAGE = 2
TRADE_RATIO = 0.35

app = Flask(__name__)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ヘッダー生成

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}{body}"
    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# 現在価格取得

def get_btc_price():
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url).json()
    logger.info(f"[get_btc_price] Ticker: {res}")
    return float(res["data"]["last"])

# 証拠金残高取得

def get_margin_balance():
    path = "/api/mix/v1/account/account"
    query = f"marginCoin={MARGIN_COIN}"
    url = f"{BASE_URL}{path}?{query}"
    headers = make_headers("GET", path)
    res = requests.get(url, headers=headers).json()
    logger.info(f"[get_margin_balance] Account: {res}")
    if res["code"] != "00000":
        raise Exception(f"Margin API error: {res['msg']}")
    return float(res["data"]["usdtEquity"])

# 注文送信

def place_order(volatility):
    price = get_btc_price()
    balance = get_margin_balance()
    order_value = balance * TRADE_RATIO * LEVERAGE
    size = round(order_value / price, 4)

    logger.info(f"[execute_order] Calculated order size: {size} BTC")

    path = "/api/mix/v1/order/place-order"
    url = f"{BASE_URL}{path}"

    body_dict = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "size": str(size),
        "price": str(price),
        "side": "open_long",
        "orderType": "market",
        "timeInForceValue": "normal"
    }

    body = json.dumps(body_dict)
    headers = make_headers("POST", path, body)

    res = requests.post(url, headers=headers, data=body).json()
    logger.info(f"[execute_order] Order response: {res}")
    if res["code"] != "00000":
        raise Exception(f"Order failed: {res['msg']}")
    return res

# Webhookエンドポイント

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw: {raw_data}")

        if "BUY" in raw_data:
            logger.info("[webhook] BUY signal detected")
            try:
                vol_str = raw_data.split("VOL=")[1].strip()
                volatility = float(vol_str)
                logger.info(f"[webhook] Extracted volatility: {volatility}")
            except Exception as e:
                logger.error(f"[webhook] Volatility parse error: {e}")
                return jsonify({"error": "Invalid VOL format"}), 400

            res = place_order(volatility)
            return jsonify({"status": "ok", "response": res})
        else:
            return jsonify({"status": "ignored"})
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"error": str(e)}), 500

# テスト用エンドポイント

@app.route("/")
def index():
    return "Webhook bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)





