import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Pro-Swing Automation", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"

# Sector Mapping
SECTORS = {
    "BANK": ["AXISBANK.NS", "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "SBIN.NS", "INDUSINDBK.NS"],
    "IT": ["HCLTECH.NS", "INFY.NS", "LTIM.NS", "TCS.NS", "TECHM.NS", "WIPRO.NS"],
    "AUTO": ["BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "M&M.NS", "MARUTI.NS", "TATAMOTORS.NS"],
    "ENERGY": ["BPCL.NS", "COALINDIA.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS"]
}
ALL_TICKERS = [t for sub in SECTORS.values() for t in sub]

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="pro_sync_v2")

# Initialize Persistence with "Self-Healing" for StopPrice
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        # Fix for the KeyError: Ensure StopPrice exists in loaded data
        if 'StopPrice' not in df_load.columns:
            df_load['StopPrice'] = df_load['BuyPrice'] * 0.98
        st.session_state.portfolio = df_load.to_dict('records')
    else:
        st.session_state.portfolio = []

if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 2. INDEX HEADER ---
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df = yf.Ticker(ticker).history(period="2d")
        curr, prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
        cols[i].metric(name, f"{curr:,.2f}", f"{((curr-prev)/prev)*100:+.2f}%")
    except: pass
cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy")
    cap = st.number_input("Total Capital (₹)", value=50000)
    risk_p = st.slider("Risk per Trade (%)", 0.5, 3.0, 1.0)
    st.info(f"Max Loss per Trade: ₹{cap * (risk_p/100):.0f}")

# --- 4. TABS ---
tab1, tab2 = st.tabs(["🚀 Institutional Scanner", "📊 Automated Portfolio"])

# --- TAB 1: SCANNER ---
with tab1:
    @st.cache_data(ttl=30)
    def fetch_all():
        h = yf.download(ALL_TICKERS + ["^NSEI"], period="1y", progress=False)
        l = yf.download(ALL_TICKERS, period="1d", interval="1m", progress=False)['Close']
        return h, l

    h_data, l_data = fetch_all()
    results = []
    
    for t in ALL_TICKERS:
        try:
            hc = h_data['Close'][t].dropna()
            price = float(l_data[t].dropna().iloc[-1])
            
            dma200 = hc.rolling(200).mean().iloc[-1]
            high_5d = hc.tail(5).max()
            trigger = round(high_5d * 1.002, 2)
            
            # Relative Strength Filter
            n_h = h_data['Close']['^NSEI'].dropna()
            is_leader = (hc.iloc[-1]/hc.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])
            
            status, strategy = "⏳ WAIT", f"Breakout @ {trigger}"
            if price > dma200 and is_leader:
                if price >= trigger:
                    if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                    elap = (time.time() - st.session_state.triggers[t]) / 60
                    status = "🎯 CONFIRMED" if elap >= 15 else f"👀 OBSERVE ({15-int(elap)}m)"
                    strategy = "Leader Breakout"
            
            # Smart Qty Calculation for Sidebar Capital
            risk_amt = cap * (risk_p / 100)
            sl_est = price * 0.98
            suggest_qty = int(risk_amt / (price - sl_est)) if price > sl_est else 0

            results.append({
                "Stock": t.replace(".NS",""), "Status": status, "Strategy": strategy, 
                "Price": round(price, 2), "Leader": "✅" if is_leader else "❌",
                "Suggest Qty": suggest_qty
            })
        except: continue
    
    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

# --- TAB 2: PORTFOLIO & AUTO-TRAILING ---
with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_pxs = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        
        display_p = []
        for i in st.session_state.portfolio:
            try:
                curr_v = float(c_pxs[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(c_pxs.dropna().iloc[-1])
                
                # AUTO TRAIL: If price jumps 3%, move SL to Entry (Risk-Free)
                if curr_v > (i['BuyPrice'] * 1.03) and i['StopPrice'] < i['BuyPrice']:
                    i['StopPrice'] = i['BuyPrice']
                    st.toast(f"🛡️ {i['Symbol']} is now RISK-FREE! SL moved to Entry.")

                if curr_v <= i['StopPrice']:
                    st.toast(f"🚨 SELL {i['Symbol']} - SL HIT!", icon="⚠️")
                    st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                
                display_p.append({
                    "Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], 
                    "Active SL": i['StopPrice'], "Current": round(curr_v, 2), 
                    "P&L": f"₹{round((curr_v - i['BuyPrice']) * i['Qty'], 2)}"
                })
            except: continue
        st.dataframe(pd.DataFrame(display_p), use_container_width=True, hide_index=True)
        
    # Manual Add (with Ticker Dropdown)
    with st.expander("➕ Add New Trade Manually"):
        col_a, col_b, col_c = st.columns(3)
        new_t = col_a.selectbox("Stock", ALL_TICKERS)
        new_q = col_b.number_input("Qty", min_value=1, value=1)
        new_p = col_c.number_input("Entry Price", min_value=1.0)
        if st.button("Add to Portfolio"):
            st.session_state.portfolio.append({
                "Ticker": new_t, "Symbol": new_t.replace(".NS",""), 
                "Qty": new_q, "BuyPrice": new_p, "StopPrice": new_p * 0.98
            })
            pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
            st.rerun()
