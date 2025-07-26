import time
import hmac
import hashlib
import requests
import json
import os
from dotenv import load_dotenv

# 環境変数読み込み（.envファイルにAPIキー等を保存）
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

# シンボル設定（必要に応じて変更）
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"

# --- 署名付きヘッダー生成 ---
def make_headers(api_key, api_secret, api_passphrase, method, path, body):
    timestamp = str(int(time.time() * 1000))
    pre_hash = timestamp + method + path + body
    sign = hmac.new(api_secret.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()
    return {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': api_passphrase,
        'Content-Type': 'application/json'
    }

# --- 注文実行 ---
def send_trailing_order(
    api_key,
    api_secret,
    api_passphrase,
    symbol,
    margin_coin,
    size,
    callback_rate,
    stop_loss_price
):
    base_url = "https://api.bitget.com"
    path = "/api/mix/v1/order/placeOrder"
    url = base_url + path

    body_dict = {
        "symbol": symbol,
        "marginCoin": margin_coin,
        "side": "open_long",              # BUYのみ（売りは open_short）
        "orderType": "market",
        "size": str(size),
        "timeInForceValue": "normal",
        "presetStopLossPrice": str(stop_loss_price),
        "presetTrailingStopCallbackRate": str(callback_rate)
    }

    body = json.dumps(body_dict)
    headers = make_headers(api_key, api_secret, api_passphrase, "POST", path, body)
    response = requests.post(url, headers=headers, data=body)
    return response.json()

# --- 実行例 ---
if __name__ == "__main__":
    # テスト用：仮に現在価格 116000、VOL 104296 を使って動的に計算
    current_price = 116000
    volatility = 104296

    # 損切り：現在価格の2.5%下
    stop_loss_price = round(current_price * 0.975, 1)

    # トレイリング幅：VOL×1.5 or 15のうち大きい方を％に換算
    trail_width = max(volatility * 1.5, 15)
    callback_rate = round(trail_width / current_price, 4)  # 小数で渡す（例: 0.015）

    # 注文サイズ（固定 or 自動）
    size = 0.001

    # 注文送信
    result = send_trailing_order(
        api_key=API_KEY,
        api_secret=API_SECRET,
        api_passphrase=API_PASSPHRASE,
        symbol=SYMBOL,
        margin_coin=MARGIN_COIN,
        size=size,
        callback_rate=callback_rate,
        stop_loss_price=stop_loss_price
    )

    print("=== Order Response ===")
    print(json.dumps(result, indent=2))

