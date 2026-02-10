import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. SETTINGS ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Sync

# --- 2. TICKERS ---
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

# --- 3. UI ---
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
is_open = (9 <= now.hour < 16) and (now.weekday() < 5)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st.title(f"🏹 Nifty 50 Precision Terminal {'🟢' if is_open else '⚪'}")
st.write(f"IST Time: **{now.strftime('%H:%M:%S')}** | Refresh: 1 Min")

st.sidebar.header("🛡️ Strategy Settings")
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 4. DATA ENGINE ---
@st.cache_data(ttl=60)
def get_live_data():
    # Fetching 2 years for DMA/RSI and 1 day for Real
