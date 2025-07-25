import os
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pybitget import Client  # ← pip install python-bitget

# 環境変数読み込み
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"
PRODUCT_TYPE = "UMCBL"  # Mix契約のUSDT建て

# Flask & ログ設定
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Bitgetクライアント初期化（引数名を正確に）
client = Client(
    api_key=API_KEY,
    api_secret_key=API_SECRET,  # ← 修正済み！
    passphrase=API_PASSPHRASE
)

# ---- BTC価格取得 ----
def get_btc_price():
    ticker = client.mix_get_market_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] {ticker}")
    return float(ticker["data"]["last"])

# ---- 証拠金情報取得 ----
def get_margin_balance():
    res = client.mix_get_account(symbol=SYMBOL, productType=PRODUCT_TYPE)
    logger.info(f"[get_margin_balance] {res}")
    return res["data"]

# ---- ダミー注文処理 ----
def execute_order(volume):
    logger.info(f"[execute_order] Volume: {volume}")
    # ここに client.mix_place_order(...) を追加予定
    return True

# ---- Webhookハンドラ ----
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

            price = get_btc_price()
            margin = get_margin_balance()

            logger.info(f"[webhook] BTC Price: {price}, Margin: {margin}")
            execute_order(volume)
            return jsonify({"status": "success"}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---- ヘルスチェック ----
@app.route("/")
def home():
    return "Bitget Webhook Bot is running!"

# ---- アプリ実行 ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


