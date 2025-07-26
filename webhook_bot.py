from flask import Flask, request, jsonify
import os
import time
import hmac
import hashlib
import requests
import logging

app = Flask(__name__)

# 環境変数から読み込み（Render用、.env不要）
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sig_test")

def make_headers(method, path, query="", body=""):
    timestamp = str(int(time.time() * 1000))
    full_path = f"{path}{query}"
    prehash = f"{timestamp}{method.upper()}{full_path}{body}"
    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
    }
    if method.upper() != "GET":
        headers["Content-Type"] = "application/json"
    return headers

def verify_signature():
    path = "/api/mix/v1/account/account"
    query = "?symbol=BTCUSDT_UMCBL"
    url = BASE_URL + path + query
    headers = make_headers("GET", path, query=query)
    response = requests.get(url, headers=headers)
    logger.info("[verify_signature] Response: %s", response.json())
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.data.decode("utf-8")
    logger.info("[webhook] Raw: %s", raw)

    if raw.startswith("BUY VOL="):
        result = verify_signature()
        if result["code"] == "00000":
            return jsonify({"status": "OK"})
        else:
            return jsonify({"status": "署名エラー", "message": result.get("msg", "")}), 500

    return jsonify({"status": "ignored"})

if __name__ == "__main__":
    app.run(port=5000)





