import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Nifty 50 Precision Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Real-Time Sync

# --- MASTER TICKER LIST ---
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

# --- MARKET HEADER ---
def get_market_indices():
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    # Fetching 2 days of data to calculate day change
    data = yf.download(list(indices.values()), period="2d", interval="1m", progress=False)
    
    cols = st.columns(len(indices) + 1)
    
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            # Safely extract close prices
            current_p = float(data['Close'][ticker].dropna().iloc[-1])
            # Price at the end of the previous trading day
            prev_close = float(data['Close'][ticker].dropna().iloc[0]) 
            change = current_p - prev_close
            pct = (change / prev_close) * 100
            cols[i].metric(name, f"{current_p:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
        except:
            cols[i].metric(name, "Fetching...")

    # Market Status Indicator (Top Right)
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    # Market Hours: 9:15 AM to 3:30 PM
    is_open = (9 <= now.hour < 16) and (now.weekday() < 5)
    if now.hour == 9 and now.minute < 15: is_open = False
    if now.hour == 15 and now.minute > 30: is_open = False
    
    status = "🟢 OPEN" if is_open else "⚪ CLOSED"
    cols[-1].markdown(f"**Market Status:** {status}\n\n**IST Time:** {now.strftime('%H:%M')}")

# --- UI START ---
get_market_indices()
st.divider()
st.title("🏹 Nifty 50 Precision Profit Terminal")

st.sidebar.header("🛡️ Risk & Capital")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000, step=5000)
risk_p = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, 0.5)

with st.spinner("Streaming Live Market Data..."):
    hist_data = yf.download(NIFTY_50, period="2y", interval="1d", group_by='ticker', progress=False)
    live_data = yf.download(NIFTY_50, period="1d", interval="1m", group_by='ticker', progress=False)

results = []
total_profit_pool = 0.0

for t in NIFTY_50:
    row = {"Stock": t.replace(".NS", ""), "Price": 0.0, "Action": "⏳ WAIT", "Qty": 0, "Profit Potential": 0.0}
    try:
        if t in hist_data.columns.levels[0] and t in live_data.columns.levels[0]:
            df_h = hist_data[t].dropna()
            df_l = live_data[t].dropna()
            
            if not df_h.empty and not df_l.empty:
                price = float(df_l['Close'].iloc[-1])
                dma_200 = float(df_h['Close'].rolling(window=200).mean().iloc[-1])
                rsi_val = float(calculate_rsi(df_h['Close']).iloc[-1])
                
                # Stop Loss: 20-day low with 1.5% buffer
                recent_low = float(df_h['Low'].tail(20).min())
