from flask import Flask, request, jsonify
import logging
import os
from dotenv import load_dotenv
from bitget import Client

# ----- 初期化 -----
app = Flask(__name__)
load_dotenv()

# ----- ログ設定 -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ----- 環境変数 -----
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
LEVERAGE = 2
RISK_RATIO = 0.35

# ----- Bitget SDKクライアント -----
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
    return float(ticker['data']['last'])

# ----- 証拠金取得 -----
def get_margin_balance():
    result = client.mix_get_account(symbol=SYMBOL)
    logger.info(f"[get_margin_balance] Account: {result}")
    return float(result['data']['usdtEquity'])

# ----- 注文送信 -----
def execute_order(side, volatility):
    price = get_btc_price()
    equity = get_margin_balance()

    order_margin = equity * RISK_RATIO
    position_value = order_margin * LEVERAGE
    order_size = round(position_value / price, 3)
    logger.info(f"[execute_order] Calculated order size: {order_size} BTC")

    if order_size <= 0:
        logger.warning("[execute_order] Order size is 0. Skip.")
        return {"status": "skipped", "reason": "Insufficient equity"}

    trail_width = max(float(volatility) * 1.5, 15)
    callback_rate = round(trail_width / price, 4)
    stop_loss = round(price * 0.975, 1)

    try:
        res = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin=MARGIN_COIN,
            side="open_long" if side == "BUY" else "open_short",
            orderType="market",
            size=str(order_size),
            presetStopLossPrice=str(stop_loss),
            presetTrailingStopCallbackRate=str(callback_rate),
            timeInForceValue="normal"
        )
        logger.info(f"[execute_order] Order response: {res}")
        return res
    except Exception as e:
        logger.error(f"[execute_order] Order failed: {e}")
        raise

# ----- VOL=xxxx抽出 -----
def extract_volatility(payload):
    try:
        for token in payload.split():
            if token.startswith("VOL="):
                return float(token.replace("VOL=", ""))
        raise ValueError("VOL=xxxx not found")
    except Exception as e:
        logger.error(f"[extract_volatility] Error: {e}")
        raise

# ----- Webhook処理 -----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.get_data(as_text=True)
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")
            vol = extract_volatility(raw)
            return jsonify(execute_order("BUY", vol))
        elif "SELL" in raw:
            logger.info("[webhook] SELL signal detected")
            vol = extract_volatility(raw)
            return jsonify(execute_order("SELL", vol))
        else:
            logger.warning("[webhook] Invalid signal")
            return jsonify({"status": "ignored"}), 400
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def root():
    return "Webhook bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

