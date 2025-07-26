import time, hmac, hashlib, requests, json
from urllib.parse import urlencode
import os
from dotenv import load_dotenv

# .env読み込み
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

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
    response = requests.get(f"{base_url}{path}?{query_string}", headers=headers)

    print("=== Bitget Signature Test ===")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_signature()

