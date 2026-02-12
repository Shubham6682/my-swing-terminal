import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Alarms Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="alarm_sync")

# --- 2. SESSION STATE FOR ALERTS ---
if 'last_confirmed' not in st.session_state: st.session_state.last_confirmed = []
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        st.session_state.portfolio = pd.read_csv(PORTFOLIO_FILE).to_dict('records')
    else: st.session_state.portfolio = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HEADER ---
st.title("🔔 Elite Alarm Terminal")
st.write(f"**Market Status:** {'🟢 OPEN' if is_open else '⚪ CLOSED'} | **Last Sync:** {now.strftime('%H:%M:%S')}")
st.divider()

# --- 4. DATA FETCH ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=30)
def fetch_market():
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)
    l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
    return h, l

try:
    h_data, l_data = fetch_market()
    results = []
    current_confirmed = []

    for t in TICKERS_NS:
        try:
            hc = h_data['Close'][t].dropna()
            price = float(l_data[t].dropna().iloc[-1])
            dma200, high_5d = hc.rolling(200).mean().iloc[-1], hc.tail(5).max()
            trigger = round(high_5d * 1.002, 2)
            
            # Trend Check
            is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (h_data['Close']['^NSEI'].iloc[-1]/h_data['Close']['^NSEI'].iloc[-63])
            
            status = "⏳ WAIT"
            if price > dma200 and is_leader:
                if price >= trigger:
                    if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                    elapsed = (time.time() - st.session_state.triggers[t]) / 60
                    if elapsed >= 15:
                        status = "🎯 CONFIRMED"
                        current_confirmed.append(t)
                    else: status = f"👀 OBSERVE ({15-int(elapsed)}m)"
            
            results.append({"Stock": t.replace(".NS",""), "Status": status, "Price": round(price, 2), "Entry": trigger})
        except: continue

    # --- ALERT TRIGGER LOGIC ---
    for stock in current_confirmed:
        if stock not in st.session_state.last_confirmed:
            st.toast(f"🚀 SIGNAL: {stock} is now CONFIRMED!", icon="💰")
            st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
            st.session_state.last_confirmed.append(stock)

    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

except: st.info("Scanning for opportunities...")
