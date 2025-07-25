import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from bitget import Client  # ← 正しいインポート

# 環境変数読み込み
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"

# Flask & ログ初期化
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Bitgetクライアント初期化
client = Client(
    api_key=API_KEY,
    api_secret=API_SECRET,
    passphrase=API_PASSPHRASE,
    use_server_time=True
)

# ---- BTC価格取得 ----
def get_btc_price():
    res = client.mix_get_accounts(productType="UMCBL")  # 証拠金取得に混在する API
    price_res = client.mix_get_market_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] price_response: {price_res}")
    return float(price_res["data"]["last"])

# ---- 証拠金取得 ----
def get_margin_balance():
    res = client.mix_get_accounts(productType="UMCBL")  # productType に注意
    logger.info(f"[get_margin_balance] account_response: {res}")
    return res["data"]

# ---- 仮注文関数 ----
def execute_order(volume):
    logger.info(f"[execute_order] Volume: {volume}")
    # 本番は client.mix_place_order(...) で注文出せるよ
    return True

# ---- Webhookエンドポイント ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw data: '{raw}'")
        if "BUY" in raw:
            logger.info("[webhook] Detected BUY signal")
            price = get_btc_price()
            margin = get_margin_balance()
            logger.info(f"[webhook] BTC Price: {price}, Margin: {margin}")
            execute_order(volume=0.01)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget SDK Webhook Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

