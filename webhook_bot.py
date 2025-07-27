import os
import logging
import re
import pandas as pd
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
ATR_LENGTH = 14
ATR_MULTIPLIER = 1.5
KLINE_INTERVAL = "1H"

# ---- Flask & ログ ----
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
    return float(res["data"]["available"])

# ---- ATR取得 ----
def get_atr(symbol="BTCUSDT_UMCBL", interval=3600, length=14):
    now = int(time.time() * 1000)  # 現在時刻（ミリ秒）
    start_time = now - (length + 1) * interval * 1000
    end_time = now

    res = client.mix_get_candles(
        symbol=symbol,
        granularity=interval,
        startTime=start_time,
        endTime=end_time
    )

    candles = res['data']  # 最新が末尾
    candles.reverse()  # 時系列順に並べ替え

    highs = [float(c[3]) for c in candles]  # High
    lows = [float(c[4]) for c in candles]   # Low
    closes = [float(c[2]) for c in candles] # Close

    trs = []
    for i in range(1, len(highs)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    atr = sum(trs[-length:]) / length
    logger.info(f"[get_atr] ATR ({length} period): {atr:.2f}")
    return atr


# ---- ロング注文（ATRを用いた損切）----
def execute_order():
    btc_price = get_btc_price()
    atr = get_atr()
    margin = get_margin_balance()
    order_value = margin * RISK_RATIO * LEVERAGE
    size = round(order_value / btc_price, 4)
    logger.info(f"[execute_order] Calculated order size: {size} BTC")

    stop_loss_price = round(btc_price - atr * ATR_MULTIPLIER, 1)
    logger.info(f"[execute_order] Stop loss price (ATR-based): {stop_loss_price}")

    order = client.mix_place_order(
        symbol=SYMBOL,
        marginCoin=MARGIN_COIN,
        size=str(size),
        side="open_long",
        orderType="market",
        timeInForceValue="normal",
        presetStopLossPrice=str(stop_loss_price)
    )
    logger.info(f"[execute_order] Order placed: {order}")
    return order

# ---- ポジションをクローズ（成行） ----
def close_long_position():
    res = client.mix_close_positions(
        symbol=SYMBOL,
        marginCoin=MARGIN_COIN,
        side="close_long",
        posMode="single"
    )
    logger.info(f"[close_long_position] Close response: {res}")
    return res

# ---- Webhook受信 ----
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.data.decode("utf-8")
    logger.info(f"[webhook] Raw: {raw}")

    if "BUY" in raw:
        logger.info("[webhook] BUY signal detected")
        result = execute_order()
        return jsonify({"status": "success", "order": result}), 200

    if "LONG_TRAIL_STOP" in raw:
        logger.info("[webhook] TRAIL STOP signal detected")
        result = close_long_position()
        return jsonify({"status": "closed", "response": result}), 200

    return jsonify({"status": "ignored", "message": "No valid signal"}), 200

# ---- 起動 ----
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)





