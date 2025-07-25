from flask import Flask, request, jsonify
import logging
import os
from dotenv import load_dotenv
from pybitget import Client

# --- 初期化 ---
app = Flask(__name__)
load_dotenv()

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# --- 環境変数読み込み ---
API_KEY = os.environ.get("BITGET_API_KEY")
API_SECRET = os.environ.get("BITGET_API_SECRET")
API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"
LEVERAGE = 2

client = Client(api_key=API_KEY, api_secret_key=API_SECRET, passphrase=API_PASSPHRASE)

# --- 現在価格取得 ---
def get_btc_price():
    ticker = client.mix_get_market_ticker(symbol=SYMBOL)
    price = float(ticker['data']['last'])
    logger.info(f"[get_btc_price] Ticker: {ticker}")
    return price

# --- 証拠金取得 ---
def get_margin_balance():
    account = client.mix_get_account(symbol=SYMBOL)
    logger.info(f"[get_margin_balance] Account: {account}")
    return float(account['data']['available'])

# --- 注文実行 ---
def execute_order(side, volatility):
    price = get_btc_price()
    margin = get_margin_balance()

    order_margin = margin * 0.35
    position_value = order_margin * LEVERAGE
    size = round(position_value / price, 3)

    trail_width = max(float(volatility) * 1.5, 15)
    stop_loss = round(price * 0.975, 1)

    logger.info(f"[execute_order] Calculated order size: {size} BTC")

    res = client.mix_place_order(
        symbol=SYMBOL,
        marginCoin="USDT",
        size=str(size),
        side=side.lower(),
        orderType="market",
        tradeSide=side.lower(),
        leverage=str(LEVERAGE),
        presetStopLossPrice=str(stop_loss),
        presetTrailingStopCallbackRate=str(round(trail_width / price, 4))
    )
    logger.info(f"[execute_order] Response: {res}")
    return res

# --- VOL抽出 ---
def extract_volatility(payload):
    for token in payload.split():
        if token.startswith("VOL="):
            return float(token.replace("VOL=", ""))
    raise ValueError("VOL=xxxx が見つかりません")

# --- エンドポイント ---
@app.route('/', methods=['GET'])
def index():
    return "Bitget Webhook Bot is running"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw = request.get_data(as_text=True).strip()
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
            return jsonify({"status": "ignored", "message": "Unknown signal"}), 400

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)


