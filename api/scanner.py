import os
import json
import requests
import pandas as pd
import numpy as np
from http.server import BaseHTTPRequestHandler
import websocket

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_FROM_BOTFATHER")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7704749217")
DERIV_APP_ID = "59828"

VOLATILITY_SYMBOLS = {
    "R_10": "Volatility 10 Index",
    "1HZ10V": "Volatility 10 (1s) Index",
    "R_25": "Volatility 25 Index",
    "1HZ25V": "Volatility 25 (1s) Index",
    "R_50": "Volatility 50 Index",
    "1HZ50V": "Volatility 50 (1s) Index",
    "R_75": "Volatility 75 Index",
    "1HZ75V": "Volatility 75 (1s) Index",
    "R_100": "Volatility 100 Index",
    "1HZ100V": "Volatility 100 (1s) Index",
    "1HZ150V": "Volatility 150 (1s) Index",
    "1HZ250V": "Volatility 250 (1s) Index",
}

def send_telegram_signal(symbol_name, direction, strategy_name, current_price):
    action_text = "BUY (UP)" if direction == "UP" else "SELL (DOWN)"
    
    message = (
        f"🥇 **DERIV MULTIPLIER SIGNAL**\n"
        f"📊 **{symbol_name}**\n\n"
        f"📍 **Entry (Live):** `{current_price:.2f}`\n"
        f"📈 **Signal:** `{action_text}` via {strategy_name}\n\n"
        f"🎯 **Take Profit:** `+$5.00 (USD)`\n"
        f"🛑 **Stop Loss:** `-$0.75 (USD)`\n\n"
        f"⚙️ **Stake:** `$1.00` | **Multiplier:** `x50`\n"
        f"⚖️ **Risk Management:** Multiplier Loss capped at Stake."
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

def fetch_candles(symbol):
    url = f"https://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    payload = {
        "ticks_history": symbol,
        "adjust_start_time": 1,
        "count": 30,
        "end": "latest",
        "granularity": 60,
        "style": "candles"
    }
    try:
        ws = websocket.create_connection(url)
        ws.send(json.dumps(payload))
        resp = ws.recv()
        ws.close()
        data = json.loads(resp)
        return data.get("candles", [])
    except Exception as e:
        print(f"WebSocket error fetching {symbol}: {e}")
        return []

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        triggered_count = 0
        
        for symbol, name in VOLATILITY_SYMBOLS.items():
            try:
                candles = fetch_candles(symbol)
                if not candles or len(candles) < 20:
                    continue
                
                closes = [c["close"] for c in candles]
                s = pd.Series(closes)
                current_price = closes[-1]
                
                # 1. Moving Average Crossover
                ema_fast = s.ewm(span=5, adjust=False).mean()
                ema_slow = s.ewm(span=15, adjust=False).mean()
                if ema_fast.iloc[-2] <= ema_slow.iloc[-2] and ema_fast.iloc[-1] > ema_slow.iloc[-1]:
                    send_telegram_signal(name, "UP", "MA Crossover", current_price)
                    triggered_count += 1
                    continue
                elif ema_fast.iloc[-2] >= ema_slow.iloc[-2] and ema_fast.iloc[-1] < ema_slow.iloc[-1]:
                    send_telegram_signal(name, "DOWN", "MA Crossover", current_price)
                    triggered_count += 1
                    continue
                
                # 2. Price Breakout
                recent_high = max(closes[-15:-1])
                recent_low = min(closes[-15:-1])
                if closes[-1] > recent_high:
                    send_telegram_signal(name, "UP", "Price Breakout", current_price)
                    triggered_count += 1
                elif closes[-1] < recent_low:
                    send_telegram_signal(name, "DOWN", "Price Breakout", current_price)
                    triggered_count += 1
                    
            except Exception as e:
                print(f"Error checking {symbol}: {e}")

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(f"Scanner executed successfully. Signals sent: {triggered_count}".encode('utf-8'))
