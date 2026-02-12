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

# Market Hours: 9:15 AM - 3:30 PM IST
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="elite_unified_sync")

# --- 2. DATA PERSISTENCE & ALERTS ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        if 'StopPrice' not in df_load.columns: df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'last_confirmed' not in st.session_state: st.session_state.last_confirmed = []
if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HEADER & INDICES ---
st.title("🏹 Elite Pro Alarm Terminal")
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
    cap = st.number_input("Total Capital (₹)", value=50000)
    risk_p = st.slider("Risk per Trade (%)", 0.5, 3.0, 1.0)
    st.divider()
    st.header("🔔 Recent Alerts")
    if not st.session_state.last_confirmed:
        st.write("No signals yet today.")
    else:
        for stock in reversed(st.session_state.last_confirmed[-5:]):
            st.success(f"🚀 {stock} CONFIRMED")

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
        current_confirmed_this_run = []

        for t in TICKERS_NS:
            try:
                hc = h_data['Close'][t].dropna()
                price = float(l_data[t].dropna().iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                high_5d = hc.tail(5).max()
                trigger = round(high_5d * 1.002, 2)
                
                # Leader Check
                n_h = h_data['Close']['^NSEI'].dropna()
                is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])
                
                status = "⏳ WAIT"
                if price > dma200 and is_leader:
                    if price >= trigger:
                        if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                        elapsed = (time.time() - st.session_state.triggers[t]) / 60
                        if elapsed >= 15:
                            status = "🎯 CONFIRMED"
                            current_confirmed_this_run.append(t.replace(".NS",""))
                        else: status = f"👀 OBSERVE ({15-int(elapsed)}m)"
                
                # Risk Analysis Columns
                gap_pct = ((price - trigger) / trigger) * 100
                
                res = {
                    "Stock": t.replace(".NS",""), 
                    "Status": status, 
                    "Entry Zone": trigger, 
                    "LTP": round(price, 2)
                }
                
                if view_mode == "Pro Deep-Dive (Risk Analysis)":
                    res["Gap %"] = f"{gap_pct:+.2f}%"
                    res["Leader"] = "✅" if is_leader else "❌"
                    res["StopLoss"] = round(price * (1 - (risk_p/100)), 2)
                    res["Risk Info"] = "🟢 SAFE" if gap_pct < 1.5 else "🔴 TOO FAR"
                
                results.append(res)
            except: continue

        # --- NOTIFICATION LOGIC ---
        for stock_sym in current_confirmed_this_run:
            if stock_sym not in st.session_state.last_confirmed:
                st.toast(f"🚀 BREAKOUT: {stock_sym} is now CONFIRMED!", icon="💰")
                st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                st.session_state.last_confirmed.append(stock_sym)

        st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)
    except: st.info("Loading Live Market Data...")

with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_pxs = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        display_p = []
        for i in st.session_state.portfolio:
            try:
                cv = float(c_pxs[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(c_pxs.dropna().iloc[-1])
                # Auto Trailing: If price > 3% from entry, SL moves to entry
                if cv > (i['BuyPrice'] * 1.03) and i['StopPrice'] < i['BuyPrice']:
                    i['StopPrice'] = i['BuyPrice']
                    st.toast(f"🛡️ {i['Symbol']} moved to Break-even (Risk Free)!")
                
                display_p.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "Trailing SL": i['StopPrice'], "Current": round(cv, 2), "P
