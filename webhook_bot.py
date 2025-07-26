import time
import hmac
import hashlib
import requests
import json
import os
from urllib.parse import urlencode
from flask import Flask

# Flaskアプリ
app = Flask(__name__)

@app.route("/")
def home():
    return "Bitget Bot is running!"

# --- 環境変数からAPIキー類を取得（Render用に .env は使わない） ---
API_KEY = os.environ["BITGET_API_KEY"]
API_SECRET = os.environ["BITGET_API_SECRET"]
API_PASSPHRASE = os.environ["BITGET_API_PASSPHRASE"]

# --- Bitget用の署名付きヘッダー生成 ---
def make_headers(api_key, api_secret, api_passphrase, method, path, query_string="", body=""):
    timestamp = str(int(time.time() * 1000))
    full_path = path
    if method == "GET" and query_string:
        full_path += "?" + query_string
    prehash = timestamp + method + full_path + body
    sign = hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": api_passphrase,
        "Content-Type": "application/json"
    }

# --- 起動時に1回だけ署名テスト ---
def test_signature():
    base_url = "https://api.bitget.com"
    path = "/api/mix/v1/account/account"
    method = "GET"
    query_params = {
        "symbol": "BTCUSDT_UMCBL",
        "marginCoin": "USDT"
    }
    query_string = urlencode(query_params)

    headers = make_headers(API_KEY, API_SECRET, API_PASSPHRASE, method, path, query_string)
    url = f"{base_url}{path}?{query_string}"
    response = requests.get(url, headers=headers)

    print("=== Bitget Signature Test ===")
    print(json.dumps(response.json(), indent=2))

# --- エントリーポイント ---
if __name__ == "__main__":
    # 環境変数で署名テストONなら実行（Renderの Environment に指定）
    if os.environ.get("RUN_SIGNATURE_TEST") == "true":
        test_signature()

    # Flaskを常駐させる
    app.run(host="0.0.0.0", port=5000)

