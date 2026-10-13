from flask import Flask, request
import os, json, requests
import websocket

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN")
DERIV_WS = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

VOLATILITIES = {
    "R_10": "Volatility 10",
    "R_25": "Volatility 25",
    "R_50": "Volatility 50",
    "R_75": "Volatility 75",
    "R_100": "Volatility 100",
    "1HZ10V": "Vol 10 (1s)",
    "1HZ25V": "Vol 25 (1s)",
    "1HZ100V": "Vol 100 (1s)"
}

def send(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)

def get_deriv_candles(symbol):
    try:
        ws = websocket.create_connection(DERIV_WS, timeout=8)
        req = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": 60,
            "count": 50,
            "end": "latest"
        }
        ws.send(json.dumps(req))
        for _ in range(3):
            res = json.loads(ws.recv())
            if "candles" in res:
                ws.close()
                return res["candles"]
            if "error" in res:
                ws.close()
                return None
        ws.close()
    except Exception as e:
        return None
    return None

def analyze_symbol(symbol, name):
    candles = get_deriv_candles(symbol)
    if not candles or len(candles) < 20:
        return f"⚪ {name} ({symbol}): No data"

    last = candles[-1]["close"]
    prev = candles[-2]["close"]
    change = ((last - prev) / prev) * 100 if prev else 0

    recent = candles[-20:]
    ma20 = sum(c["close"] for c in recent) / 20
    high = max(c["high"] for c in candles[-10:])
    low = min(c["low"] for c in candles[-10:])
    vol_pct = ((high - low) / low * 100) if low else 0

    signal = "BUY 📈" if last > ma20 else "SELL 📉"
    if change > 0.3: signal = "STRONG BUY 🚀"
    if change < -0.3: signal = "STRONG SELL 🔻"

    spike = " 🔥SPIKE!" if vol_pct > 0.8 else ""
    return f"{'🟢' if last>ma20 else '🔴'} *{name}*: {last:.2f} {signal}{spike}\n Change: {change:+.2f}% | Vol: {vol_pct:.2f}%"

@app.route('/', methods=['GET','POST'])
@app.route('/api', methods=['GET','POST'])
def main():
    if request.method == 'GET':
        return "🔥 DERIV VOLATILITY SCANNER LIVE!"

    data = request.get_json(force=True, silent=True) or {}
    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text","").upper()

    if "/START" in text:
        send(chat_id, "🔥 *DERIV VOLATILITY SCANNER* 🔥\n\n*/scan* - Scan ALL volatilities\n*/v10* - Vol 10\n*/v25* - Vol 25\n*/v50* - Vol 50\n*/v75* - Vol 75\n*/v100* - Vol 100\n*/v1s* - Vol 1s markets\n\nReal Deriv API live! 📊")
        return "ok"

    if "/SCAN" in text or "/VOL" in text:
        send(chat_id, "⏳ Scanning 8 volatility markets... 5 sec")
        results = []
        for sym, name in VOLATILITIES.items():
            results.append(analyze_symbol(sym, name))
        msg = "🔥 *VOLATILITY SCAN - LIVE* 🔥\n" + time_now() + "\n\n" + "\n\n".join(results) + "\n\n_Best: High Vol + Strong Signal_"
        send(chat_id, msg)
        return "ok"

    for key in ["V10", "V25", "V50", "V75", "V100"]:
        if key in text:
            sym = "R_" + key[1:]
            if "1S" in text: sym = "1HZ" + key[1:] + "V"
            name = VOLATILITIES.get(sym, sym)
            res = analyze_symbol(sym, name)
            send(chat_id, f"📊 *{name} DETAIL*\n\n{res}\n\nUse /scan for all")
            return "ok"

    if "V1S" in text or "1S" in text:
        results = []
        for sym in ["1HZ10V","1HZ25V","1HZ100V"]:
            results.append(analyze_symbol(sym, VOLATILITIES[sym]))
        send(chat_id, "⚡ *VOLATILITY 1s MARKETS*\n\n" + "\n\n".join(results))
        return "ok"

    send(chat_id, "Use /scan to start scanning 🚀")
    return "ok"

def time_now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S UTC")
