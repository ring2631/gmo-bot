from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_bot")

app = Flask(__name__)

def make_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}{body}"
    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def test_market_ticker():
    path = "/api/mix/v1/market/ticker"
    url = f"{BASE_URL}{path}?symbol=BTCUSDT_UMCBL"
    headers = make_headers("GET", path, "")
    response = requests.get(url, headers=headers)
    logger.info("[test_market_ticker] Response: %s", response.json())
    return response.json()

@app.route("/test", methods=["GET"])
def test():
    return jsonify(test_market_ticker())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)





