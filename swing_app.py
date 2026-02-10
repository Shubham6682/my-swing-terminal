import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Nifty 50 Profit Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Real-Time Sync

# --- TICKERS ---
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

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI ---
st.title("🏹 Nifty 50 Precision Profit Terminal")

# Sidebar - User Inputs
st.sidebar.header("🛡️ Risk & Capital")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000, step=5000)
risk_p = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, 0.5)

# Clock Logic
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.datetime.now(ist)
st.markdown(f"**Live Sync:** `{now_ist.strftime('%H:%M:%S')}` IST")

with st.spinner("Calculating real-time profits..."):
    # Bulk fetching
    hist_data = yf.download(NIFTY_50, period="2y", interval="1d", group_by='ticker', progress=False)
    live_data = yf.download(NIFTY_50, period="1d", interval="1m", group_by='ticker', progress=False)

results = []
total_profit_pool = 0.0

for t in NIFTY_50:
    # Default state for every stock
    row = {"Stock": t.replace(".NS", ""), "Price": 0.0, "Action": "⏳ WAIT", "Qty": 0, "Profit Potential": 0.0, "RSI": 0.0}
    
    try:
        if t in hist_data.columns.levels[0] and t in live_data.columns.levels[0]:
