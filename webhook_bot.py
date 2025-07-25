from flask import Flask, request, jsonify
import os
import logging
from dotenv import load_dotenv
from pybitget.client import MixClient  # ← pybitget の正しいインポート

# 初期化
app = Flask(__name__)
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# 環境変数
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

# クライアント初期化
client = MixClient(
    api_key=API_KEY,
    api_secret=API_SECRET,
    passphrase=API_PASSPHRASE,
    use_server_time=False  # レンダーで時間ズレ対策済みならTrueも可
)

SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2

@app.route("/", methods=["GET"])
def index():
    return "Bitget Webhook Bot is running"

# ボラティリティ抽出
def extract_volatility(payload: str) -> float:
    for token in payload.split():
        if token.startswith("VOL="):
            return float(token.replace("VOL=", ""))
    raise ValueError("VOL=xxxx が見つかりません")

# 現在価格取得
def get_btc_price():
    ticker = client.get_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] Ticker: {ticker}")
    return float(ticker['data']['last'])

# 証拠金情報取得
def get_margin_balance():
    account = client.get_account(symbol=SYMBOL)
    logger.info(f"[get_margin_balance] Account: {account}")
    return float(account['data']['available'])

# 注文実行
def execute_order(side: str, volatility: float):
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 3)

    trail_width = max(volatility * 1.5, 15)
    callback_rate = round(trail_width / price, 4)
    stop_loss = round(price * 0.975, 1)

    body = {
        "symbol": SYMBOL,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side.lower(),
        "orderType": "market",
        "tradeSide": side.lower(),
        "leverage": str(LEVERAGE),
        "presetStopLossPrice": str(stop_loss),
        "presetTrailingStopCallbackRate": str(callback_rate)
    }

    res = client.place_order(body)
    logger.info(f"[execute_order] Response: {res}")
    return res

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw: {raw}")

        vol = extract_volatility(raw)
        logger.info(f"[webhook] Extracted volatility: {vol}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")
            return jsonify(execute_order("BUY", vol))
        elif "SELL" in raw:
            logger.info("[webhook] SELL signal detected")
            return jsonify(execute_order("SELL", vol))
        else:
            return jsonify({"status": "ignored", "message": "No valid signal"}), 400

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)

