import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Elite Pro Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"

NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="entry_sync")

# Initialize Session & Persistence
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        if 'StopPrice' not in df_load.columns: df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 2. HEADER ---
st.title("🏹 Elite Pro Momentum Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df_i = yf.Ticker(ticker).history(period="2d")
        c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
        idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
    except: pass
idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Control")
    cap = st.number_input("Capital (₹)", value=50000)
    risk_p = st.slider("Risk (%)", 0.5, 3.0, 1.0)
    if st.button("💾 Save All Data"):
        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
        st.success("Saved!")

# --- 4. TABS ---
tab1, tab2 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio"])

# --- TAB 1: SCANNER ---
with tab1:
    @st.cache_data(ttl=30)
    def get_data():
        h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)
        l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
        return h, l

    h_data, l_data = get_data()
    results = []
    for t in TICKERS_NS:
        try:
            hc = h_data['Close'][t].dropna()
            price = float(l_data[t].dropna().iloc[-1])
            dma200 = hc.rolling(200).mean().iloc[-1]
            ema20 = hc.ewm(span=20).mean().iloc[-1]
            high_5d = hc.tail(5).max()
            trigger = round(high_5d * 1.002, 2)
            
            # Leader Filter
            n_h = h_data['Close']['^NSEI'].dropna()
            is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])
            
            status, entry_type = "⏳ WAIT", "Watch Level"
            entry_price = trigger # Default to breakout trigger
            
            if price > dma200 and is_leader:
                if price >= trigger:
                    if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                    elapsed = (time.time() - st.session_state.triggers[t]) / 60
                    status = "🎯 CONFIRMED" if elapsed >= 15 else f"👀 OBSERVE ({15-int(elapsed)}m)"
                    entry_type = "Buy Above"
                    entry_price = trigger
                elif price < ema20 * 1.01: # Pullback logic
                    status = "📉 PULLBACK"
                    entry_type = "Buy Near"
                    entry_price = round(ema20, 2)
            
            res = {
                "Stock": t.replace(".NS",""), 
                "Status": status, 
                "Strategy": entry_type, 
                "Entry Price": entry_price, # NEW COLUMN
                "LTP": round(price, 2),
                "StopLoss": round(hc.tail(20).min() * 0.985, 2)
            }
            results.append(res)
        except: continue
    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

# --- TAB 2 (PORTFOLIO) UNCHANGED ---
