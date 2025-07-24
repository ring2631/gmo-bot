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

logger.warning(f"[DEBUG] BITGET_API_KEY loaded: {API_KEY is not None}")
logger.warning(f"[DEBUG] BITGET_API_SECRET loaded: {API_SECRET is not None}")
logger.warning(f"[DEBUG] BITGET_API_PASSPHRASE loaded: {API_PASSPHRASE is not None}")

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

# ----- Bitgetサーバー時間取得 -----
def get_server_time() -> int:
    try:
        url = f"{BASE_URL}/api/v2/public/time"
        res = requests.get(url)
        return int(res.json()["data"]["serverTime"])  # 修正済み
    except Exception as e:
        logger.warning(f"[get_server_time] Failed to get server time: {e}")
        return int(time.time() * 1000)

# ----- 署名付きヘッダー生成（署名デバッグ付き） -----
def make_headers(method: str, path: str, body: str = "") -> dict:
    timestamp = str(get_server_time())
    method_upper = method.upper()
    message = f"{timestamp}{method_upper}{path}{body}"
    sign = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

    # 🔍 デバッグログ追加（署名検証用）
    logger.warning(f"[SIGN DEBUG] timestamp: {timestamp}")
    logger.warning(f"[SIGN DEBUG] method: {method_upper}")
    logger.warning(f"[SIGN DEBUG] path: {path}")
    logger.warning(f"[SIGN DEBUG] body: {body}")
    logger.warning(f"[SIGN DEBUG] message: {message}")
    logger.warning(f"[SIGN DEBUG] sign: {sign}")

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# ----- BTC価格取得 -----
def get_btc_price() -> float:
    url = f"{BASE_URL}/api/mix/v1/market/ticker?symbol={SYMBOL}"
    res = requests.get(url)
    data = res.json()
    logger.info(f"[get_btc_price] Response: {data}")
    if data.get("code") != "00000":
        raise ValueError(f"Failed to get price: {data}")
    return float(data["data"]["last"])

# ----- 証拠金残高取得 -----
def get_margin_balance() -> float:
    path = "/api/mix/v1/account/account"
    query = f"?symbol={SYMBOL}"
    url = f"{BASE_URL}{path}{query}"
    headers = make_headers("GET", path, "")  # クエリは署名に含めない

    logger.debug(f"[get_margin_balance] URL: {url}")
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
    size = round(position_value / price, 3)

    trail_width = max(volatility * 1.5, 15)
    stop_loss = round(price * 0.975, 1)

    path = "/api/mix/v1/order/place-order"
    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side.lower(),
        "orderType": "market",
        "leverage": str(LEVERAGE),
        "presetStopLossPrice": str(stop_loss),
        "presetTrailingStopCallbackRate": str(round(trail_width / price, 4))
    }
    body_json = json.dumps(body, separators=(',', ':'))  # ← ← ← ← ★重要★ JSONを圧縮して空白除去！
    headers = make_headers("POST", path, body_json)

    res = requests.post(f"{BASE_URL}{path}", headers=headers, data=body_json)
    logger.info(f"[send_order] Request body: {body_json}")
    logger.info(f"[send_order] Response: {res.status_code} {res.text}")
    try:
        return res.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON response from Bitget"}

# ----- VOL=xxx 抽出 -----
def extract_volatility(payload: str) -> float:
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx が見つかりません")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# ----- root確認 -----
@app.route("/", methods=["GET"])
def index():
    return "Bitget Webhook Bot is running."

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
            return jsonify({"status": "ignored", "message": "No BUY or SELL detected"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ----- 起動 -----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


