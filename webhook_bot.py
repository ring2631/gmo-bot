import os
import logging
import time
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
MARGIN_COIN_SHORT = "USDC"
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
def get_margin_balance(coin):
    res = client.mix_get_account(symbol=SYMBOL, marginCoin=coin)
    logger.info(f"[get_margin_balance] Account: {res}")
    return float(res["data"]["available"])

# ---- ATR取得 ----
def get_atr(symbol="BTCUSDT_UMCBL", interval="1H", length=14):
    now = int(time.time() * 1000)
    interval_ms = 60 * 60 * 1000
    start_time = now - (length + 1) * interval_ms
    end_time = now

    res = client.mix_get_candles(
        symbol=symbol,
        granularity=interval,
        startTime=start_time,
        endTime=end_time
    )

    candles = res
    if not candles or len(candles) < length + 1:
        raise ValueError("取得したローソク足データが不足しています")

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df[["high", "low", "close"]] = df[["high", "low", "close"]].astype(float)

    df["prior_close"] = df["close"].shift(1)
    df["tr"] = df[["high", "low", "prior_close"]].apply(
        lambda row: max(
            row["high"] - row["low"],
            abs(row["high"] - row["prior_close"]),
            abs(row["low"] - row["prior_close"])
        ), axis=1
    )

    atr = df["tr"].rolling(window=length).mean().iloc[-1]
    if pd.isna(atr):
        raise ValueError("ATRの計算に失敗しました")

    stop_width = round(atr * 1.5, 1)
    logger.info(f"[get_atr] Calculated ATR: {atr}, Stop width: {stop_width}")
    return stop_width

# ---- ロング注文 ----
def execute_order():
    btc_price = get_btc_price()
    atr = get_atr()
    margin = get_margin_balance(MARGIN_COIN)
    order_value = margin * RISK_RATIO * LEVERAGE
    size = round(order_value / btc_price, 4)
    logger.info(f"[execute_order] Calculated order size: {size} BTC")

    atr_stop = atr * 2.0
    fixed_stop = btc_price * 0.02
    stop_loss_distance = max(atr_stop, fixed_stop)
    stop_loss_price = round(btc_price - stop_loss_distance, 1)

    logger.info(f"[execute_order] Stop loss (ATR): {atr_stop:.1f}, Fixed: {fixed_stop:.1f}")
    logger.info(f"[execute_order] Selected Stop Loss Price: {stop_loss_price}")

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

# ---- ショート注文（USDC）----
def execute_short_order():
    btc_price = get_btc_price()
    atr = get_atr()
    margin = get_margin_balance(MARGIN_COIN_SHORT)
    order_value = margin * RISK_RATIO * LEVERAGE
    size = round(order_value / btc_price, 4)
    logger.info(f"[execute_short_order] Calculated order size: {size} BTC")

    atr_stop = atr * 2.0
    fixed_stop = btc_price * 0.02
    stop_loss_distance = max(atr_stop, fixed_stop)
    stop_loss_price = round(btc_price + stop_loss_distance, 1)

    logger.info(f"[execute_short_order] Stop loss (ATR): {atr_stop:.1f}, Fixed: {fixed_stop:.1f}")
    logger.info(f"[execute_short_order] Selected Stop Loss Price: {stop_loss_price}")

    order = client.mix_place_order(
        symbol=SYMBOL,
        marginCoin=MARGIN_COIN_SHORT,
        size=str(size),
        side="open_short",
        orderType="market",
        timeInForceValue="normal",
        presetStopLossPrice=str(stop_loss_price)
    )
    logger.info(f"[execute_short_order] Order placed: {order}")
    return order

# ---- ロングポジションをクローズ ----
def close_long_position():
    try:
        res = client.mix_get_single_position(symbol=SYMBOL, marginCoin=MARGIN_COIN)
        logger.info(f"[close_long_position] Raw position response: {res}")
        data = res.get('data', [])
        if not data or not isinstance(data, list):
            return {"msg": "No open position"}

        long_positions = [pos for pos in data if pos.get('holdSide') == 'long' and float(pos.get('total', 0)) > 0]
        if not long_positions:
            return {"msg": "No long position"}

        size = float(long_positions[0]['total'])
        order = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin=MARGIN_COIN,
            size=size,
            side="close_long",
            orderType="market"
        )
        logger.info(f"[close_long_position] Close response: {order}")
        return order
    except Exception as e:
        logger.error(f"[close_long_position] Error: {e}")
        return {"error": str(e)}

# ---- ショートポジションをクローズ ----
def close_short_position():
    try:
        res = client.mix_get_single_position(symbol=SYMBOL, marginCoin=MARGIN_COIN_SHORT)
        logger.info(f"[close_short_position] Raw position response: {res}")
        data = res.get('data', [])
        if not data or not isinstance(data, list):
            return {"msg": "No open position"}

        short_positions = [pos for pos in data if pos.get('holdSide') == 'short' and float(pos.get('total', 0)) > 0]
        if not short_positions:
            return {"msg": "No short position"}

        size = float(short_positions[0]['total'])
        order = client.mix_place_order(
            symbol=SYMBOL,
            marginCoin=MARGIN_COIN_SHORT,
            size=size,
            side="close_short",
            orderType="market"
        )
        logger.info(f"[close_short_position] Close response: {order}")
        return order
    except Exception as e:
        logger.error(f"[close_short_position] Error: {e}")
        return {"error": str(e)}

# ---- Webhook受信 ----
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.data.decode("utf-8")
    logger.info(f"[webhook] Raw: {raw}")

    if "BUY" in raw:
        logger.info("[webhook] BUY signal detected")
        result = execute_order()
        return jsonify({"status": "success", "order": result}), 200

    if "SELL" in raw:
        logger.info("[webhook] SELL signal detected")
        result = execute_short_order()
        return jsonify({"status": "success", "order": result}), 200

    if "LONG_TRAIL_STOP" in raw:
        logger.info("[webhook] LONG TRAIL STOP signal")
        result = close_long_position()
        return jsonify({"status": "closed", "response": result}), 200

    if "SHORT_TRAIL_STOP" in raw:
        logger.info("[webhook] SHORT TRAIL STOP signal")
        result = close_short_position()
        return jsonify({"status": "closed", "response": result}), 200

    return jsonify({"status": "ignored", "message": "No valid signal"}), 200

# ---- 起動 ----
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


