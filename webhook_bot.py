import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from bitpy import BitgetAPI  # ← 正しい SDK インポート

# Load env
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"
PRODUCT_TYPE = "USDT-FUTURES"  # bitget-python に合わせた形式

# Init Flask and logger
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Init BitgetAPI client
client = BitgetAPI(
    api_key=API_KEY,
    secret_key=API_SECRET,
    api_passphrase=API_PASSPHRASE
)

def get_btc_price():
    ticker = client.market.get_ticker(
        symbol="BTCUSDT",
        product_type=PRODUCT_TYPE
    )
    logger.info(f"[get_btc_price] {ticker}")
    return float(ticker["data"]["last"] if "data" in ticker else ticker.get("last", 0))

def get_margin_balance():
    res = client.account.get_account(
        symbol="BTCUSDT",
        product_type=PRODUCT_TYPE,
        margin_coin="USDT"
    )
    logger.info(f"[get_margin_balance] {res}")
    return res.get("data", res)

def execute_order(volume):
    logger.info(f"[execute_order] volume={volume}")
    # 将来 client.trade.create_order(...) を使って注文
    return True

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True).strip()
        logger.info(f"[webhook] Raw: {raw}")
        if "BUY" in raw:
            price = get_btc_price()
            margin = get_margin_balance()
            logger.info(f"[webhook] Price={price}, Margin={margin}")
            execute_order(volume=0.01)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Bitget‑Python Bot running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


