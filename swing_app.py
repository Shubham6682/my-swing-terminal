import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Sync

# --- 2. MASTER TICKER LIST ---
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

# --- 3. MARKET HEADER & STATUS ---
def display_header():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    
    # Precise Market Hours Check
    market_open = False
    if now.weekday() < 5: # Monday to Friday
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if start <= now <= end:
            market_open = True
    
    # Indices Bar
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    idx_data = yf.download(list(indices.values()), period="2d", interval="1m", progress=False)
    
    cols = st.columns(len(indices) + 1)
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            prices = idx_data['Close'][ticker].dropna()
            if not prices.empty:
                curr = float(prices.iloc[-1])
                prev = float(prices.iloc[0])
                change = curr - prev
                pct = (change / prev) * 100
                cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            else:
                cols[i].metric(name, "N/A", "Market Closed")
        except:
            cols[i].metric(name, "N/A")

    status_icon = "🟢 OPEN" if market_open else "⚪ CLOSED"
    cols[-1].markdown(f"**Status:** {status_icon}\n\n**Time:** {now.strftime('%H:%M:%S')}")

# Run the Header UI
display_header()
st.divider()

# --- 4. SIDEBAR SETTINGS ---
st.sidebar.header("
