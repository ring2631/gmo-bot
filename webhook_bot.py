import os
import logging
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pybitget import Client  # pip install python-bitget

# ---- 環境変数 ----
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

# ---- 設定 ----
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
RISK_RATIO = 0.35
LEVERAGE = 2

# ---- Flask & ロガー ----
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# ---- Bitgetクライアント ----
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

# ---- 注文処理（VOLで利確幅を計算）----
def execute_order(volatility):
    btc_price = get_btc_price()
    margin = get_margin_balance()
    usdt_equity = float(margin["usdtEquity"])

    # 証拠金 × RISK × LEVERAGE ÷ 現在価格 → 注文サイズ
    order_margin = usdt_equity * RISK_RATIO
    position_value = order_margin * LEVERAGE
    order_size = round(position_value / btc_price, 3)
    logger.info(f"[execute_order] Calculated order size: {order_size} BTC")

    if order_size <= 0:
        raise ValueError("Order size is zero or less. Skipping order.")

    # Stop Loss（現在価格の 2.5% 下）
    stop_loss_price = round(btc_price * 0.975, 1)

    # Take Profit（VOL × 1.5 上）
    take_profit_price = round(btc_price + volatility * 1.5, 1)

    # 実行
    try:
        order = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin=MARGIN_COIN,
            side="open_long",
            orderType="market",
            size=str(order_size),
            price="",  # 成行
            timeInForceValue="normal",
            presetStopLossPrice=str(stop_loss_price),
        )
        logger.info(f"[execute_order] Order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"[execute_order] Order failed: {e}")
        raise

# ---- Webhookエンドポイント ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw: {raw}")

        if "BUY" in raw:
            logger.info("[webhook] BUY signal detected")

            match = re.search(r"VOL\s*=\s*([0-9.]+)", raw)
            volatility = float(match.group(1)) if match else 100.0
            logger.info(f"[webhook] Extracted volatility: {volatility}")

            result = execute_order(volatility)
            return jsonify({"status": "success", "order": result}), 200

        return jsonify({"status": "ignored"}), 200

    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---- ホームエンドポイント ----
@app.route("/")
def home():
    return "Bitget Webhook Bot is Running!"

# ---- 起動 ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



