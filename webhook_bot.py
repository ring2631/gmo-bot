import os
import time
import json
import hmac
import base64
import hashlib
import requests
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 環境変数読み込み（.envファイルや環境に設定してください）
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

BASE_URL = "https://api.bitget.com"  # 必要により変更してください

SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
RISK_RATIO = 0.35
LEVERAGE = 2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

def sign_request(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    """Bitget APIの署名を生成"""
    message = timestamp + method.upper() + request_path + body
    hmac_key = base64.b64decode(API_SECRET)
    signature = hmac.new(hmac_key, message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

def call_api(method: str, path: str, params: dict = None, body: dict = None):
    """Bitget REST APIを呼び出す共通関数"""
    # クエリ文字列生成
    query = ""
    if params:
        query = "?" + "&".join(f"{key}={params[key]}" for key in params)
    request_path = path + query

    body_str = json.dumps(body) if body else ""

    timestamp = str(int(time.time() * 1000))
    signature = sign_request(timestamp, method, request_path, body_str)

    headers = {
        "Content-Type": "application/json",
        "X-BG-API-KEY": API_KEY,
        "X-BG-API-SIGN": signature,
        "X-BG-API-TIMESTAMP": timestamp,
        "X-BG-API-PASSPHRASE": API_PASSPHRASE,
    }

    url = BASE_URL + request_path

    logger.info(f"API call: {method} {url} Body={body_str}")

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, headers=headers, data=body_str)
        else:
            raise ValueError(f"Unsupported method: {method}")

        resp.raise_for_status()
        res_json = resp.json()

        if res_json.get("code") != "00000":
            logger.error(f"API error response: {res_json}")
            raise Exception(f"API error: {res_json}")

        return res_json.get("data")
    except Exception as e:
        logger.error(f"API call failed: {e}")
        raise

def get_btc_price() -> float:
    """BTCの現在価格を取得"""
    # 最新のAPIドキュメントに合わせてパスやパラメータをご確認ください
    data = call_api("GET", "/api/v1/market/tickers", params={"symbol": SYMBOL})
    ticker = data.get("list")[0]  # APIの返却構造によって変わるかもしれません
    price = float(ticker["last"])
    logger.info(f"[get_btc_price] price={price}")
    return price

def get_margin_balance():
    """証拠金残高を取得"""
    data = call_api("GET", "/api/mix/v1/account/accounts", params={"marginCoin": MARGIN_COIN})
    for account in data:
        if account.get("marginCoin") == MARGIN_COIN:
            logger.info(f"[get_margin_balance] found: {account}")
            return account
    raise Exception(f"Margin coin {MARGIN_COIN} account not found")

def execute_order(volatility: float):
    """注文発注 処理"""
    btc_price = get_btc_price()
    margin = get_margin_balance()

    usdt_equity = float(margin["usdtEquity"])

    order_margin = usdt_equity * RISK_RATIO
    position_value = order_margin * LEVERAGE
    order_size = round(position_value / btc_price, 3)
    logger.info(f"[execute_order] Calculated order size: {order_size} BTC")

    if order_size <= 0:
        raise ValueError("Order size is zero or less. Skipping order.")

    stop_loss_price = round(btc_price * 0.975, 1)
    trail_width = max(volatility * 1.5, 15)
    callback_rate = round(trail_width / btc_price, 4)

    order_body = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "side": "open_long",
        "orderType": "market",
        "size": str(order_size),
        "price": "",  # 成行注文なので空文字
        "timeInForceValue": "normal",
        "presetStopLossPrice": str(stop_loss_price),
        "presetTrailingStopCallbackRate": str(callback_rate),
    }

    path = "/api/mix/v1/order/placeOrder"
    data = call_api("POST", path, body=order_body)
    logger.info(f"[execute_order] Order response: {data}")
    return data

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw payload: {raw}")

        if "BUY" in raw.upper():
            logger.info("[webhook] BUY signal detected")

            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw, re.IGNORECASE)
            volatility = float(match.group(1)) if match else 100.0
            logger.info(f"[webhook] Extracted volatility: {volatility}")

            order_result = execute_order(volatility)
            return jsonify({"status": "success", "order": order_result}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Exception: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget Webhook Bot is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



