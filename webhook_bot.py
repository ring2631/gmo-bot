import os
import time
import hmac
import hashlib
import json
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Flaskと環境変数の初期化
app = Flask(__name__)
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数の取得
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
MARGIN_COIN = "USDT"
SYMBOL = "BTCUSDT_UMCBL"
BASE_URL = "https://api.bitget.com"

# 署名付きヘッダー作成関数
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

# 現在のBTC価格を取得
def get_btc_price():
    path = f"/api/mix/v1/market/ticker"
    url = f"{BASE_URL}{path}?symbol={SYMBOL}"
    res = requests.get(url).json()
    logger.info(f"[get_btc_price] Ticker: {res}")
    return float(res["data"]["last"])

# 証拠金残高を取得
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

# 注文実行（仮：SDKで使ってた元ロジックを流用予定）
def execute_order(signal, volatility):
    btc_price = get_btc_price()
    balance = get_margin_balance()
    stake_ratio = 0.35
    leverage = 2
    order_value = balance * stake_ratio * leverage
    size = round(order_value / btc_price, 3)
    logger.info(f"[execute_order] Calculated order size: {size} BTC")
    # 注文処理は後で追加（ここはSDKベースに合わせてカスタマイズ）
    return size

# Webhook受信エンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw: {raw_data}")

        if "BUY" in raw_data:
            logger.info("[webhook] BUY signal detected")
            try:
                volatility = float(raw_data.split("VOL=")[1])
                logger.info(f"[webhook] Extracted volatility: {volatility}")
            except Exception as e:
                return f"Failed to extract volatility: {e}", 400

            execute_order("BUY", volatility)
            return "Buy order executed", 200

        return "No valid signal detected", 400

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return f"Webhook error: {e}", 500

# メイン
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)





