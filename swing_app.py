import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Sentinel Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="sentinel_unified_sync")

# --- 2. DATA PERSISTENCE & ALERTS ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        if 'StopPrice' not in df_load.columns: df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'alert_log' not in st.session_state: st.session_state.alert_log = {} # Stock: Timestamp
if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HEADER & INDICES ---
st.title("🏹 Elite Sentinel Pro Terminal")
indices = {"Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Sensex": "^BSESN"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df_i = yf.Ticker(ticker).history(period="2d")
        c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
        idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
    except: pass
idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Terminal Settings")
    view_mode = st.radio("Display Mode", ["Simple View", "Pro Deep-Dive (Risk Analysis)"])
    st.divider()
    st.header("🛡️ Risk Control")
    risk_p = st.slider("Max Risk per Trade (%)", 0.5, 3.0, 1.0)
    st.divider()
    st.header("🔔 Live Entry Feed")
    if not st.session_state.alert_log:
        st.info("No active signals.")
    else:
        # Show newest 5 signals with timestamps
        sorted_history = sorted(st.session_state.alert_log.items(), key=lambda x: x[1], reverse=True)
        for stock, ts in sorted_history[:5]:
            time_ago = int((time.time() - ts) / 60)
            st.success(f"🚀 {stock}: Confirmed {time_ago}m ago")

# --- 5. DATA FETCH ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=30)
def fetch_market():
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)
    l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
    return h, l

# --- 6. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & GTT"])

with tab1:
    try:
        h_data, l_data = fetch_market()
        results = []
        for t in TICKERS_NS:
            try:
                hc = h_data['Close'][t].dropna()
                price = float(l_data[t].dropna().iloc[-1])
                dma200, high_5d = hc.rolling(200).mean().iloc[-1], hc.tail(5).max()
                trigger = round(high_5d * 1.002, 2)
                
                # Leader Check
                is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (h_data['Close']['^NSEI'].iloc[-1]/h_data['Close']['^NSEI'].iloc[-63])
                
                status = "⏳ WAIT"
                if price > dma200 and is_leader:
                    if price >= trigger:
                        if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                        elapsed = (time.time() - st.session_state.triggers[t]) / 60
                        if elapsed >= 15:
                            status = "🎯 CONFIRMED"
                            stock_sym = t.replace(".NS","")
                            if stock_sym not in st.session_state.alert_log:
                                st.toast(f"🚀 SIGNAL: {stock_sym} IS READY!", icon="💰")
                                st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                                st.session_state.alert_log[stock_sym] = time.time()
                        else: status = f"👀 OBSERVE ({15-int(elapsed)}m)"
                
                gap_pct = ((price - trigger) / trigger) * 100
                res = {"Stock": t.replace(".NS",""), "Status": status, "Entry Zone": trigger, "LTP": round(price, 2)}
                if view_mode == "Pro Deep-Dive (Risk Analysis)":
                    res["Gap %"] = f"{gap_pct:+.2f}%"
                    res["Risk Info"] = "🟢 SAFE" if gap_pct < 1.5 else "🔴 TOO FAR"
                    res["Leader"] = "✅" if is_leader else "❌"
                    res["StopLoss"] = round(price * (1 - (risk_p/100)), 2)
                results.append(res)
            except: continue
        st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)
    except: st.info("Scanning...")

with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_pxs
