import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. SETTINGS & REFRESH ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Sync

# --- 2. TICKER LIST ---
NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

# --- 3. UI HEADER ---
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Status Logic
is_open = (9 <= now.hour < 16) and (now.weekday() < 5)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False
status_emoji = "🟢 OPEN" if is_open else "⚪ CLOSED"

st.title(f"🏹 Nifty 50 Profit Terminal {status_emoji}")
st.write(f"Last Sync: **{now.strftime('%H:%M:%S')} IST**")

# Sidebar
st.sidebar.header("🛡️ Risk & Capital")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 4. DATA ENGINE ---
@st.cache_data(ttl=60)
def fetch_all_data():
    # Fetching only essential columns to save memory and speed
    data = yf.download(NIFTY_50, period="2y", interval="1d", progress=False)
    return data['Close'], data['Low'], data['Volume'], data['Open']

try:
    with st.spinner("Downloading Market Data..."):
        close_data, low_data, vol_data, open_data = fetch_all_data()

    results = []
    total_profit = 0.0

    for t in NIFTY_50:
        try:
            # Technical Indicators
            prices = close_data[t].dropna()
            if len(prices) < 200: continue
            
            cmp = float(prices.iloc[-1])
            dma200 = float(prices.rolling(window=200).mean().iloc[-1])
            
            # RSI Calculation
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # Risk Logic
            stop_loss = float(low_data[t].tail(20).min()) * 0.985
            risk_amt = cmp - stop_loss
            
            # FII Proxy
            v_avg = vol_data[t].tail(20).mean()
            v_curr = vol_data[t].iloc[-1]
            fii = "🟢 Accumulating" if (v_curr > v_avg and cmp > open_data[t].iloc[-1]) else "⚪ Neutral"
            
            # Signal
            is_valid = (cmp > dma200 and 40 < rsi < 65)
            action = "✅ BUY" if is_valid else "⏳ WAIT"
            
            qty = 0
            profit = 0.0
            if is_valid and risk_amt > 0:
                qty = int((cap * (risk_p / 100)) // risk_amt)
                profit = round(qty * (risk_amt * 2), 2)
                total_profit += profit

            results.append({
