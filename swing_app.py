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

# Comprehensive Ticker List for Dropdowns
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="final_sync")

# Initialize Session & Self-Healing Persistence
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        if 'StopPrice' not in df_load.columns: df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 2. HEADER & INDICES ---
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
    view_mode = st.radio("Mode", ["Simple", "Pro Deep-Dive"])
    if st.button("💾 Save All Data"):
        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
        st.success("Saved!")

# --- 4. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & Lookup"])

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
            high_5d = hc.tail(5).max()
            trigger = round(high_5d * 1.002, 2)
            
            # Leader Filter
            n_h = h_data['Close']['^NSEI'].dropna()
            is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])
            
            status, strategy = "⏳ WAIT", f"Breakout @ {trigger}"
            if price > dma200 and is_leader:
                if price >= trigger:
                    if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                    elapsed = (time.time() - st.session_state.triggers[t]) / 60
                    status = "🎯 CONFIRMED" if elapsed >= 15 else f"👀 OBSERVE ({15-int(elapsed)}m)"
                    strategy = "Momentum verified"
            
            res = {"Stock": t.replace(".NS",""), "Status": status, "Strategy": strategy, "Price": round(price, 2)}
            if view_mode == "Pro Deep-Dive": res["Leader"] = "✅" if is_leader else "❌"
            results.append(res)
        except: continue
    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

# --- TAB 2: PORTFOLIO ---
with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_pxs = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        display_p = []
        for i in st.session_state.portfolio:
            try:
                cv = float(c_pxs[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(c_pxs.dropna().iloc[-1])
                # Auto Trailing
                if cv > (i['BuyPrice'] * 1.03) and i['StopPrice'] < i['BuyPrice']:
                    i['StopPrice'] = i['BuyPrice']
                    st.toast(f"🛡️ {i['Symbol']} Risk-Free!")
                if cv <= i['StopPrice']:
                    st.toast(f"🚨 EXIT {i['Symbol']}!", icon="⚠️")
                    st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                display_p.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "SL": i['StopPrice'], "Current": round(cv, 2), "P&L": round((cv - i['BuyPrice']) * i['Qty'], 2)})
            except: continue
        st.dataframe(pd.DataFrame(display_p), use_container_width=True, hide_index=True)

    with st.expander("➕ Add Trade via Dropdown"):
        col1, col2, col3 = st.columns(3)
        nt = col1.selectbox("Ticker", NIFTY_50)
        nq = col2.number_input("Qty", min_value=1, value=1)
        np = col3.number_input("Price", min_value=1.0)
        if st.button("Add to Portfolio"):
            st.session_state.portfolio.append({"Ticker": f"{nt}.NS", "Symbol": nt, "Qty": nq, "BuyPrice": np, "StopPrice": np * 0.98})
            pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
            st.rerun()

# --- TAB 3: WATCHLIST ---
with tab3:
    st.subheader("🎯 Watchlist Manager")
    lu = st.selectbox("Quick Add Ticker:", NIFTY_50, key="w_lu")
    if st.button(f"Add {lu} to Watchlist"):
        if lu not in st.session_state.watchlist: st.session_state.watchlist.append(lu)
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
    if st.button("Clear Watchlist"): st.session_state.watchlist = []; st.rerun()
