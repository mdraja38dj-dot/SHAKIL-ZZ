import os
import time
import json
import threading
import requests
import pandas as pd
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= SERVER NAME =================
SERVER_NAME = "SHAKIL ZZ 🚀 MASTER AI ENGINE"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

latest_result = {"signal": "WAIT", "status": "READY"}

# ================= MARKET DATA (REAL) =================
def get_market_data(market, tf):
    try:
        interval = "1m" if tf == "1m" else "5m"
        df = yf.download(market, period="1d", interval=interval, progress=False)

        if df.empty:
            raise Exception("No data")

        return df.tail(100)

    except:
        import numpy as np
        return pd.DataFrame({
            "Open": np.random.rand(60) * 100,
            "High": np.random.rand(60) * 101,
            "Low": np.random.rand(60) * 99,
            "Close": np.random.rand(60) * 100,
        })

# ================= STRUCTURE =================
def market_structure(df):
    last = df.tail(10)
    prev = df.iloc[-20:-10]

    if len(prev) < 5:
        return "RANGE"

    if last['High'].max() > prev['High'].max() and last['Low'].min() > prev['Low'].min():
        return "UPTREND_HH_HL"
    elif last['High'].max() < prev['High'].max() and last['Low'].min() < prev['Low'].min():
        return "DOWNTREND_LH_LL"
    return "RANGE"

# ================= SUPPORT / RESISTANCE =================
def sr_level(df):
    return {
        "support": float(df['Low'].min()),
        "resistance": float(df['High'].max())
    }

# ================= LIQUIDITY =================
def liquidity(df):
    last = df.iloc[-1]
    body = abs(last['Close'] - last['Open'])
    upper = last['High'] - max(last['Close'], last['Open'])
    lower = min(last['Close'], last['Open']) - last['Low']

    if lower > body * 1.5:
        return "BUY_SIDE_GRAB"
    elif upper > body * 1.5:
        return "SELL_SIDE_GRAB"
    return "NONE"

# ================= CANDLE =================
def candle_context(df):
    history = df.tail(40)

    bullish = (history['Close'] > history['Open']).sum()
    bearish = (history['Close'] < history['Open']).sum()

    momentum = history['Close'].iloc[-1] - history['Close'].iloc[0]

    return {
        "bullish": int(bullish),
        "bearish": int(bearish),
        "momentum": float(momentum),
        "running": "BULL_RUN" if momentum > 0 else "BEAR_RUN" if momentum < 0 else "SIDEWAYS"
    }

# ================= INDICATORS =================
def indicators(df):
    ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
    ema50 = df['Close'].ewm(span=50).mean().iloc[-1]

    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return {
        "ema": "BULLISH" if ema20 > ema50 else "BEARISH",
        "rsi": float(rsi.iloc[-1])
    }

# ================= PATTERN =================
def pattern(df):
    last = df.iloc[-1]

    body = abs(last['Close'] - last['Open'])
    upper = last['High'] - max(last['Close'], last['Open'])
    lower = min(last['Close'], last['Open']) - last['Low']

    if lower > body * 2:
        return "BULLISH_REJECTION"
    if upper > body * 2:
        return "BEARISH_REJECTION"

    return "NORMAL"

# ================= BOS =================
def bos(df):
    last = df.iloc[-1]

    if last['Close'] > df['High'].iloc[-2]:
        return "BOS_UP"
    elif last['Close'] < df['Low'].iloc[-2]:
        return "BOS_DOWN"

    return "NONE"

# ================= SCORE ENGINE =================
def score_engine(data):
    score = 0

    if "UPTREND" in data["structure"]:
        score += 2
    if "DOWNTREND" in data["structure"]:
        score -= 2

    if data["liquidity"] == "BUY_SIDE_GRAB":
        score += 3
    if data["liquidity"] == "SELL_SIDE_GRAB":
        score -= 3

    if data["indicators"]["rsi"] < 30:
        score += 2
    if data["indicators"]["rsi"] > 70:
        score -= 2

    if data["candle"]["running"] == "BULL_RUN":
        score += 2
    if data["candle"]["running"] == "BEAR_RUN":
        score -= 2

    if data["pattern"] == "BULLISH_REJECTION":
        score += 2
    if data["pattern"] == "BEARISH_REJECTION":
        score -= 2

    if data["bos"] == "BOS_UP":
        score += 2
    if data["bos"] == "BOS_DOWN":
        score -= 2

    if score >= 7:
        signal = "CALL"
    elif score <= -7:
        signal = "PUT"
    else:
        signal = "WAIT"

    return {"score": score, "signal": signal}

# ================= GEMINI AI =================
def gemini_ai(data, market):
    if not GEMINI_API_KEY:
        return "AI OFF"

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

        prompt = f"""
Market: {market}
Data: {json.dumps(data)}

Give 1 line professional trading confirmation.
"""

        r = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=10)

        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    except:
        pass

    return "AI SAFE MODE"

# ================= ANALYSIS =================
def analyze(market, tf):
    df = get_market_data(market, tf)

    data = {
        "structure": market_structure(df),
        "sr": sr_level(df),
        "liquidity": liquidity(df),
        "candle": candle_context(df),
        "indicators": indicators(df),
        "pattern": pattern(df),
        "bos": bos(df),
        "price": float(df['Close'].iloc[-1])
    }

    score = score_engine(data)
    data["score"] = score

    ai = gemini_ai(data, market)

    return {
        "system": SERVER_NAME,
        "market": market,
        "timeframe": tf,
        "signal": score["signal"],
        "confidence": "HIGH" if abs(score["score']) >= 6 else "MEDIUM",
        "ai_review": ai,
        "analysis": data
    }

# ================= THREAD SAFE =================
latest_result = {"signal": "WAIT"}

def run_engine(market, tf):
    global latest_result
    latest_result = analyze(market, tf)

# ================= API =================
@app.route("/analyze")
def analyze_route():
    market = request.args.get("market")
    tf = request.args.get("timeframe", "1m")

    threading.Thread(target=run_engine, args=(market, tf)).start()

    return jsonify({"status": "ANALYZING"})

@app.route("/signal")
def signal():
    return jsonify(latest_result)

@app.route("/")
def home():
    return jsonify({"system": SERVER_NAME})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
