import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from bitget.rest.bitget_rest import Bitget

# 環境変数読み込み
load_dotenv()

# Bitget APIキー類
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = "BTCUSDT_UMCBL"

# Flask & ログ初期化
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

# Bitgetクライアント初期化（自動で署名・サーバー時刻対応）
client = Bitget(
    api_key=API_KEY,
    api_secret_key=API_SECRET,
    passphrase=API_PASSPHRASE,
    use_server_time=True
)

# ---- 現在価格取得 ----
def get_btc_price():
    res = client.mix_get_market_ticker(symbol=SYMBOL)
    logger.info(f"[get_btc_price] Response: {res}")
    return float(res["data"]["last"])

# ---- 証拠金取得 ----
def get_margin_balance():
    res = client.mix_get_account(symbol=SYMBOL)
    logger.info(f"[get_margin_balance] Response: {res}")
    return res["data"]

# ---- 発注処理（ダミー）----
def execute_order(volume):
    logger.info(f"[execute_order] Volume: {volume}")
    # 本番では client.mix_place_order(...) をここで使う
    return True

# ---- Webhookエンドポイント ----
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8").strip()
        logger.info(f"[webhook] Raw data: '{raw}'")
        if "BUY" in raw:
            logger.info("[webhook] Detected BUY signal")
            price = get_btc_price()
            margin = get_margin_balance()
            logger.info(f"[webhook] BTC Price: {price}, Margin: {margin}")
            execute_order(volume=0.01)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        logger.error(f"[webhook] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---- 簡易ヘルスチェック ----
@app.route("/")
def home():
    return "Bitget SDK Webhook Bot is running!"

# ---- 実行 ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
