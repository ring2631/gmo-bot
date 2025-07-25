import os
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from bitget import BitgetAPI  # ← pip install bitget-python

# 環境変数読み込み
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT"
PRODUCT_TYPE = "USDT-FUTURES"

# Flask & ログ初期化
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Bitgetクライアント初期化
client = BitgetAPI(
    api_key=API_KEY,
    secret_key=API_SECRET,
    api_passphrase=API_PASSPHRASE
)

# ---- BTC価格取得 ----
def get_btc_price():
    ticker = client.market.get_ticker(symbol=SYMBOL, product_type=PRODUCT_TYPE)
    logger.info(f"[get_btc_price] {ticker}")
    return float(ticker.data[0]["lastPr"])

# ---- 証拠金取得 ----
def get_margin_balance():
    res = client.account.get_account(
        symbol=SYMBOL,
        product_type=PRODUCT_TYPE,
        margin_coin="USDT"
    )
    logger.info(f"[get_margin_balance] {res}")
    return res.data

# ---- 発注処理（仮）----
def execute_order(volume):
    logger.info(f"[execute_order] Volume: {volume}")
    # 本番では client.trade.create_order(...) をここで実装可能
    return True

# ---- Webhookエンドポイント ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] Detected BUY signal")

            # VOL=xxx 抽出
            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw)
            volume = float(match.group(1)) if match else 0.01
            logger.info(f"[webhook] Extracted Volume: {volume}")

            # データ取得
            price = get_btc_price()
            margin = get_margin_balance()

            logger.info(f"[webhook] BTC Price: {price}, Margin: {margin}")
            execute_order(volume)
            return jsonify({"status": "success"}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---- Health check ----
@app.route("/")
def home():
    return "Bitget SDK Webhook Bot is running!"

# ---- 実行 ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


