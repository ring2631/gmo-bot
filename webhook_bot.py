import os
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pybitget import Client

# 環境変数読み込み
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT"
PRODUCT_TYPE = "UMCBL"  # Mix契約用

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

client = Client(api_key=API_KEY, api_secret_key=API_SECRET, passphrase=API_PASSPHRASE)

# ティッカーを取得して最新価格を返す
def get_btc_price():
    ticker = client.mix_get_single_symbol_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] Ticker: {ticker}")
    return float(ticker["data"]["last"])

# 証拠金（アカウント情報）を取得
def get_margin_balance():
    res = client.mix_get_account(symbol=SYMBOL, productType=PRODUCT_TYPE)
    logger.info(f"[get_margin_balance] Account: {res}")
    return res["data"]

# 仮注文関数（本番で mix_place_order を使う予定）
def execute_order(volume):
    logger.info(f"[execute_order] Volume: {volume}")
    # 今後 client.mix_place_order(...) を使って本番処理をここに追加
    return True

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf‑8").strip()
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")
            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw)
            volume = float(match.group(1)) if match else 0.01
            logger.info(f"[webhook] Extracted volume: {volume}")

            price = get_btc_price()
            margin = get_margin_balance()
            logger.info(f"[webhook] Price={price}, Margin={margin}")

            execute_order(volume)
            return jsonify({"status": "success"}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget SDK Webhook Bot running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


