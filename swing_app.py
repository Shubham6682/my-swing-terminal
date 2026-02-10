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
def display_market_header():
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    data = yf.download(list(indices.values()), period="2d", interval="1m", progress=False)
    cols = st.columns(len(indices) + 1)
    
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            curr_p = float(data['Close'][ticker].dropna().iloc[-1])
            prev_p = float(data['Close'][ticker].dropna().iloc[0])
            change = curr_p - prev_p
            pct = (change / prev_p) * 100
            cols[i].metric(name, f"{curr_p:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
        except:
            cols[i].metric(name, "Fetching...")

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    is_open = (9 <= now.hour < 16) and (now.weekday() < 5)
    if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
        is_open = False
