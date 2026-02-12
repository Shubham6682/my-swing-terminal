import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Pro Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="full_nifty_sync")

# --- 2. DATA PERSISTENCE ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        if 'StopPrice' not in df_load.columns: df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HEADER ---
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

# --- 4. FULL NIFTY 50 LIST ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Risk Control")
    cap = st.number_input("Total Capital (₹)", value=50000)
    risk_p = st.slider("Risk per Trade (%)", 0.5, 3.0, 1.0)
    st.divider()
    search_q = st.text_input("🔍 Quick Search Stock", "").upper()

# --- 6. TABS ---
tab1, tab2 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio"])

# --- TAB 1: SCANNER ---
with tab1:
    @st.cache_data(ttl=30)
    def fetch_market():
        h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)
        l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
        return h, l

    try:
        h_data, l_data = fetch_market()
        results = []
        
        for t in TICKERS_NS:
            stock_name = t.replace(".NS","")
            if search_q and search_q not in stock_name:
                continue
                
            try:
                hc = h_data['Close'][t].dropna()
                price = float(l_data[t].dropna().iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                ema20 = hc.ewm(span=20).mean().iloc[-1]
                high_5d = hc.tail(5).max()
                trigger = round(high_5d * 1.002, 2)
                
                # Leader Check (vs Nifty)
                n_h = h_data['Close']['^NSEI'].dropna()
                is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])
                
                status, entry_type = "⏳ WAIT", "Watch"
                
                if price > dma200 and is_leader:
                    if price >= trigger:
                        if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                        elapsed = (time.time() - st.session_state.triggers[t]) / 60
                        status = "🎯 CONFIRMED" if elapsed >= 15 else f"👀 OBSERVE ({15-int(elapsed)}m)"
                        entry_type = "BUY ABOVE"
                    elif price < ema20 * 1.01:
                        status = "📉 PULLBACK"
                        entry_type = "BUY NEAR"
                        trigger = round(ema20, 2)
                
                results.append({
                    "Stock": stock_name, 
                    "Status": status, 
                    "Type": entry_type, 
                    "Entry Zone": trigger, 
                    "LTP": round(price, 2),
                    "StopLoss": round(hc.tail(20).min() * 0.985, 2)
                })
            except: continue
        
        df_res = pd.DataFrame(results)
        if not df_res.empty:
            st.dataframe(df_res.sort_values("Status"), use_container_width=True, hide_index=True)
        else:
            st.warning("No stocks matching search.")
    except: st.info("Loading Nifty 50 Data...")

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
                    st.toast(f"🛡️ {i['Symbol']} moved to Break-even!")
                
                display_p.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "SL": i['StopPrice'], "Current": round(cv, 2), "P&L": round((cv - i['BuyPrice']) * i['Qty'], 2)})
            except: continue
        st.dataframe(pd.DataFrame(display_p), use_container_width=True, hide_index=True)

    with st.expander("➕ Add Trade"):
        col1, col2, col3 = st.columns(3)
        nt = col1.selectbox("Stock", TICKERS_NS)
        nq = col2.number_input("Qty", min_value=1, value=1)
        np = col3.number_input("Price", min_value=1.0)
        if st.button("Add to Portfolio"):
            st.session_state.portfolio.append({"Ticker": nt, "Symbol": nt.replace(".NS",""), "Qty": nq, "BuyPrice": np, "StopPrice": np * 0.98})
            pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
            st.rerun()
