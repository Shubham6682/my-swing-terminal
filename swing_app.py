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

# Sector Mapping to filter for 'Sector Strength'
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
st_autorefresh(interval=15000 if is_open else 60000, key="pro_sync")

# Initialize Persistence
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.read_csv(PORTFOLIO_FILE).to_dict('records') if os.path.exists(PORTFOLIO_FILE) else []
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

# --- 3. TABS ---
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
            
            # Trend Filters
            dma200 = hc.rolling(200).mean().iloc[-1]
            ema20 = hc.ewm(span=20).mean().iloc[-1]
            high_5d = hc.tail(5).max()
            trigger = round(high_5d * 1.002, 2) # 0.2% above high
            
            # RS (Relative Strength) against Nifty
            nifty_h = h_data['Close']['^NSEI'].dropna()
            stock_perf = (hc.iloc[-1] / hc.iloc[-63]) - 1
            nifty_perf = (nifty_h.iloc[-1] / nifty_h.iloc[-63]) - 1
            is_leader = stock_perf > nifty_perf
            
            status, strategy = "⏳ WAIT", f"Breakout @ {trigger}"
            if price > dma200 and is_leader:
                if price >= trigger:
                    if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                    elapsed = (time.time() - st.session_state.triggers[t]) / 60
                    status = "🎯 CONFIRMED" if elapsed >= 15 else f"👀 OBSERVE ({15-int(elapsed)}m)"
                    strategy = "Institutional Breakout"
            
            results.append({"Stock": t.replace(".NS",""), "Status": status, "Strategy": strategy, "Price": round(price, 2), "Leader": "✅ Yes" if is_leader else "❌ No"})
        except: continue
    
    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

# --- TAB 2: PORTFOLIO & TRAILING STOP ---
with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_pxs = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        
        updated_p = []
        for i in st.session_state.portfolio:
            curr_v = float(c_pxs[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(c_pxs.dropna().iloc[-1])
            
            # AUTO TRAILING STOP: Move SL up if price moves 2% in favor
            if curr_v > (i['BuyPrice'] * 1.02):
                new_sl = round(curr_v * 0.98, 2) # Keep SL 2% below current price
                if new_sl > i['StopPrice']:
                    i['StopPrice'] = new_sl
                    st.toast(f"📈 Trailing SL moved up for {i['Symbol']} to ₹{new_sl}")

            if curr_v <= i['StopPrice']:
                st.toast(f"🚨 EXIT TRIGGERED for {i['Symbol']}!", icon="⚠️")
                st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
            
            updated_p.append({
                "Stock": i['Symbol'], "Entry": i['BuyPrice'], 
                "Trailing SL": i['StopPrice'], "Current": round(curr_v, 2), 
                "P&L": round((curr_v - i['BuyPrice']) * i['Qty'], 2)
            })
        st.dataframe(pd.DataFrame(updated_p), use_container_width=True, hide_index=True)
        # Persistent Save
        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
