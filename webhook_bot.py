from flask import Flask, request, jsonify
import logging
import os
from dotenv import load_dotenv
from python_bitget import Client

app = Flask(__name__)
load_dotenv()

# ----- ログ -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ----- 環境変数 -----
API_KEY = os.environ.get("BITGET_API_KEY")
API_SECRET = os.environ.get("BITGET_API_SECRET")
API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2

client = Client(
    api_key=API_KEY,
    api_secret_key=API_SECRET,
    passphrase=API_PASSPHRASE,
    use_server_time=True
)

# ----- 現在価格取得 -----
def get_btc_price():
    ticker = client.mix_get_market_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] Ticker: {ticker}")
    return float(ticker["data"]["last"])

# ----- 証拠金取得 -----
def get_margin_balance():
    account = client.mix_get_account(symbol=SYMBOL)
    logger.info(f"[get_margin_balance] Account: {account}")
    return float(account["data"]["available"])

# ----- 注文処理 -----
def execute_order(side, volatility):
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 3)

    trail_width = max(float(volatility) * 1.5, 15)
    callback_rate = round(trail_width / price, 4)
    stop_loss = round(price * 0.975, 1)

    logger.info(f"[execute_order] Price={price}, Size={size}, Callback={callback_rate}, SL={stop_loss}")

    try:
        res = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin="USDT",
            size=str(size),
            side=side.lower(),
            orderType="market",
            tradeSide=side.lower(),
            leverage=str(LEVERAGE),
            presetStopLossPrice=str(stop_loss),
            presetTrailingStopCallbackRate=str(callback_rate)
        )
        logger.info(f"[execute_order] Response: {res}")
        return res
    except Exception as e:
        logger.error(f"[execute_order] Order failed: {e}")
        raise

# ----- VOL抽出 -----
def extract_volatility(payload):
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx が見つかりません")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# ----- 動作確認 -----
@app.route("/", methods=["GET"])
def index():
    return "Webhook Bot is running"

# ----- Webhook -----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw: {raw_data}")

        if "BUY" in raw_data:
            logger.info("[webhook] BUY signal detected")
            vol = extract_volatility(raw_data)
            logger.info(f"[webhook] Extracted volatility: {vol}")
            result = execute_order("BUY", vol)
            return jsonify(result)
        elif "SELL" in raw_data:
            logger.info("[webhook] SELL signal detected")
            vol = extract_volatility(raw_data)
            logger.info(f"[webhook] Extracted volatility: {vol}")
            result = execute_order("SELL", vol)
            return jsonify(result)
        else:
            logger.warning("[webhook] Unknown signal")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


