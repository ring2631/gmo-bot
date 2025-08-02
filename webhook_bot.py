import os
import hmac
import time
import json
import hashlib
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from bitget.openapi.mix_api import MixMarketApi, MixOrderApi, MixAccountApi, MixPositionApi

# === 設定 ===
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
SYMBOL_SHORT = "BTCUSDC_UMCBL"
MARGIN_COIN_SHORT = "USDC"
LEVERAGE = 2
RISK_RATIO = 0.35
KLINE_INTERVAL = "1H"
ATR_LENGTH = 14

# === 初期化 ===
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

client = type("Client", (), {})()
client.mix_market_api = MixMarketApi(api_key=os.getenv("ACCESS_KEY"), secret_key=os.getenv("SECRET_KEY"),
                                     passphrase=os.getenv("PASSPHRASE"), use_server_time=True)
client.mix_order_api = MixOrderApi(api_key=os.getenv("ACCESS_KEY"), secret_key=os.getenv("SECRET_KEY"),
                                   passphrase=os.getenv("PASSPHRASE"), use_server_time=True)
client.mix_account_api = MixAccountApi(api_key=os.getenv("ACCESS_KEY"), secret_key=os.getenv("SECRET_KEY"),
                                       passphrase=os.getenv("PASSPHRASE"), use_server_time=True)
client.mix_position_api = MixPositionApi(api_key=os.getenv("ACCESS_KEY"), secret_key=os.getenv("SECRET_KEY"),
                                         passphrase=os.getenv("PASSPHRASE"), use_server_time=True)

# === 共通関数 ===
def get_unix_time():
    return int(time.time() * 1000)

def get_atr(symbol, interval, length):
    res = client.mix_market_api.get_candles(symbol=symbol, granularity=interval)
    candles = res["data"][-(length + 1):]
    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(1, len(closes))]
    return sum(trs) / length

# === ロング用 ===
def get_btc_price():
    res = client.mix_market_api.get_ticker(symbol=SYMBOL)
    return float(res["data"]["last"])

def get_margin_balance():
    res = client.mix_account_api.get_account(symbol=SYMBOL, marginCoin=MARGIN_COIN)
    return float(res["data"]["available"])

def execute_order():
    price = get_btc_price()
    atr = get_atr(SYMBOL, KLINE_INTERVAL, ATR_LENGTH)
    margin = get_margin_balance()
    order_value = margin * RISK_RATIO * LEVERAGE
    size = round(order_value / price, 4)
    sl_price = round(price - max(atr * 2.0, price * 0.02), 1)
    order = client.mix_order_api.place_order(
        symbol=SYMBOL,
        marginCoin=MARGIN_COIN,
        size=str(size),
        side="open_long",
        orderType="market",
        timeInForceValue="normal",
        presetStopLossPrice=str(sl_price)
    )
    logger.info(f"[execute_order] order: {order}")
    return order

def close_long_position():
    pos = client.mix_position_api.get_single_position(symbol=SYMBOL, marginCoin=MARGIN_COIN)
    data = pos.get("data", [])
    long_pos = [p for p in data if p["holdSide"] == "long" and float(p["total"]) > 0]
    if not long_pos:
        return {"msg": "No long position"}
    size = float(long_pos[0]["total"])
    order = client.mix_order_api.place_order(
        symbol=SYMBOL,
        marginCoin=MARGIN_COIN,
        size=size,
        side="close_long",
        orderType="market"
    )
    return order

# === ショート用（USDC）===
def get_btc_price_usdc():
    res = client.mix_market_api.get_ticker(symbol=SYMBOL_SHORT)
    return float(res["data"]["last"])

def get_margin_balance_usdc():
    res = client.mix_account_api.get_account(symbol=SYMBOL_SHORT, marginCoin=MARGIN_COIN_SHORT)
    return float(res["data"]["available"])

def execute_short_order():
    price = get_btc_price_usdc()
    atr = get_atr(SYMBOL_SHORT, KLINE_INTERVAL, ATR_LENGTH)
    margin = get_margin_balance_usdc()
    order_value = margin * RISK_RATIO * LEVERAGE
    size = round(order_value / price, 4)
    sl_price = round(price + max(atr * 2.0, price * 0.02), 1)
    order = client.mix_order_api.place_order(
        symbol=SYMBOL_SHORT,
        marginCoin=MARGIN_COIN_SHORT,
        size=str(size),
        side="open_short",
        orderType="market",
        timeInForceValue="normal",
        presetStopLossPrice=str(sl_price)
    )
    logger.info(f"[execute_short_order] order: {order}")
    return order

def close_short_position():
    pos = client.mix_position_api.get_single_position(symbol=SYMBOL_SHORT, marginCoin=MARGIN_COIN_SHORT)
    data = pos.get("data", [])
    short_pos = [p for p in data if p["holdSide"] == "short" and float(p["total"]) > 0]
    if not short_pos:
        return {"msg": "No short position"}
    size = float(short_pos[0]["total"])
    order = client.mix_order_api.place_order(
        symbol=SYMBOL_SHORT,
        marginCoin=MARGIN_COIN_SHORT,
        size=size,
        side="close_short",
        orderType="market"
    )
    return order

# === Webhook受信部 ===
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

# === Flask起動 ===
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)



