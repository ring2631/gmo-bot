from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import json
import os
import time
import logging
from dotenv import load_dotenv

# ----- 初期化 -----
app = Flask(__name__)
load_dotenv()

# ----- ログ設定 -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ----- 環境変数 -----
API_KEY = os.environ.get("BITGET_API_KEY")
API_SECRET = os.environ.get("BITGET_API_SECRET")
API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"
SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2

# 環境変数チェック（デバッグ用。実運用時はコメントアウト推奨）
logger.info(f"Loaded API_KEY: {API_KEY is not None}, API_SECRET: {API_SECRET is not None}, API_PASSPHRASE: {API_PASSPHRASE is not None}")

# ----- Bitget署名付きヘッダー作成関数 -----
def make_headers(method: str, path: str, body: str = "") -> dict:
    timestamp = str(int(time.time() * 1000))
    method = method.upper()
    message = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    logger.debug(f"Signing message: {message}")
    logger.debug(f"Signature: {sign}")
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# ----- 現在価格取得 -----
def get_btc_price() -> float:
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    if data.get("code") != "00000":
        raise ValueError(f"Failed to get price: {data}")
    return float(data["data"]["last"])

# ----- 証拠金保持額取得 -----
def get_margin_balance() -> float:
    path = "/api/mix/v1/account/account"
    query = f"symbol={SYMBOL}"
    url = f"{BASE_URL}{path}?{query}"
    # 重要: 署名はクエリパラメータを含めずpathのみで作成する
    headers = make_headers("GET", path, "")
    res = requests.get(url, headers=headers)
    data = res.json()
    logger.info(f"[get_margin_balance] Response: {data}")
    if data.get("code") != "00000":
        raise ValueError(f"Margin API failed: {data.get('msg')}")
    return float(data["data"]["available"])

# ----- 注文送信 -----
def send_order(side: str, volatility: float) -> dict:
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 3)  # Bitgetの精度制限に合わせて小数点3桁

    trail_width = max(volatility * 1.5, 15)
    stop_loss = round(price * 0.975, 1)

    path = "/api/mix/v1/order/place-order"
    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side.lower(),
        "orderType": "market",
        "tradeSide": side.lower(),
        "leverage": str(LEVERAGE),
        "presetStopLossPrice": str(stop_loss),
        # trailing stop ratio = trail_width / price の比率、小数点4桁まで
        "presetTrailingStopCallbackRate": str(round(trail_width / price, 4))
    }
    body_json = json.dumps(body)
    headers = make_headers("POST", path, body_json)

    res = requests.post(f"{BASE_URL}{path}", headers=headers, data=body_json)
    logger.info(f"[send_order] Response: {res.status_code} {res.text}")
    try:
        return res.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON response from Bitget"}

# ----- VOL値を抽出 -----
def extract_volatility(payload: str) -> float:
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx が見つかりません")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# ----- ルート確認 -----
@app.route("/", methods=["GET"])
def index():
    return "Webhook Bot is running"

# ----- Webhook処理 -----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.get_data(as_text=True).strip()
        logger.info(f"[webhook] Raw data: '{raw_data}'")

        if "BUY" in raw_data:
            logger.info("[webhook] Detected BUY signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("BUY", vol))
        elif "SELL" in raw_data:
            logger.info("[webhook] Detected SELL signal")
            vol = extract_volatility(raw_data)
            return jsonify(send_order("SELL", vol))
        else:
            logger.warning("[webhook] Invalid signal received")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


