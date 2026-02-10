import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. SETTINGS ---
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

# --- 3. MARKET STATUS LOGIC ---
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Simplified Market Status logic to prevent SyntaxErrors in f-strings
market_is_open = False
if now.weekday() < 5: # Monday to Friday
    # 9:15 AM to 3:30 PM
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now <= end_time:
        market_is_open = True

status_icon = "🟢 OPEN" if market_is_open else "⚪ CLOSED"

# --- 4. UI START ---
st.title(f"🏹 Nifty 50 Precision Terminal {status_icon}")
st.write(f"IST Time: **{now.strftime('%H:%M:%S')}** | Auto-Refresh: 1 Min")
