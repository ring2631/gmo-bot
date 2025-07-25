import os
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pybitget import Client  # pip install python-bitget

# ---- 環境変数ロード ----
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"

# ---- Flask & ロガー初期化 ----
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ---- Bitgetクライアント初期化 ----
client = Client(
    api_key=API_KEY,
    api_secret_key=API_SECRET,
    passphrase=API_PASSPHRASE
)

# ---- BTC価格取得 ----
def get_btc_price():
    ticker = client.mix_get_single_symbol_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] Ticker: {ticker}")
    return float(ticker["data"]["last"])

# ---- 証拠金取得 ----
def get_margin_balance():
    res = client.mix_get_account(symbol=SYMBOL, marginCoin=MARGIN_COIN)
    logger.info(f"[get_margin_balance] Account: {res}")
    return res["data"]

# ---- 注文処理（本番）----
def execute_order(volume):
    try:
        order = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin=MARGIN_COIN,
            side="open_long",           # ロングポジションを建てる
            orderType="market",         # 成行
            size=str(volume),           # 取引数量
            price="",                   # 成行のため空
            timeInForceValue="normal"
        )
        logger.info(f"[execute_order] Order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"[execute_order] Order failed: {e}")
        raise

# ---- Webhookハンドラー ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")

            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw)
            volume = float(match.group(1)) if match else 0.01
            logger.info(f"[webhook] Extracted volume: {volume}")

            price = get_btc_price()
            margin = get_margin_balance()
            logger.info(f"[webhook] Price={price}, Margin={margin}")

            result = execute_order(volume)
            return jsonify({"status": "success", "order": result}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget Webhook Bot is LIVE and Ready!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


