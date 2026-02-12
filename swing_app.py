import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Elite Swing Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"

# Nifty 50 List for the Search Dropdown
NIFTY_50_TICKERS = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

# Initialize Session States
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        st.session_state.portfolio = pd.read_csv(PORTFOLIO_FILE).to_dict('records')
    else:
        st.session_state.portfolio = []

if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 2. INDEX HEADER ---
st.title("🏹 Elite Momentum Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_hist = t_obj.history(period="2d")
        if len(df_hist) >= 2:
            curr, prev = df_hist['Close'].iloc[-1], df_hist['Close'].iloc[-2]
            change = curr - prev
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({(change/prev)*100:+.2f}%)")
    except: idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ View Settings")
    view_mode = st.radio("Display Mode", ["Simple (Focus)", "Pro (Deep-Dive)"])
    st.divider()
    st.header("🛡️ Strategy Control")
    cap = st.number_input("Total Capital (₹)", value=50000)
    risk_p = st.slider("Risk (%)", 0.5, 5.0, 1.0)
    if st.button("💾 Save Portfolio"):
        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
        st.success("Saved!")

# --- 4. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & Lookup"])

# --- TAB 1: SCANNER ---
with tab1:
    NIFTY_50_FULL = [f"{t}.NS" for t in NIFTY_50_TICKERS]
    @st.cache_data(ttl=30)
    def get_market_data():
        h = yf.download(NIFTY_50_FULL + ["^NSEI"], period="1y", interval="1d", progress=False)
        l_15m = yf.download(NIFTY_50_FULL, period="2d", interval="15m", progress=False)
        l_1m = yf.download(NIFTY_50_FULL, period="1d", interval="1m", progress=False)
        return h, l_15m, l_1m

    try:
        h_data, l_15m_data, l_1m_data = get_market_data()
        results = []
        for t in NIFTY_50_FULL:
            try:
                hc, lc_15m, lc_1m = h_data['Close'][t].dropna(), l_15m_data['Close'][t].dropna(), l_1m_data['Close'][t].dropna()
                price, last_15m_close = float(lc_1m.iloc[-1]), float(lc_15m.iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                ema20 = hc.ewm(span=20, adjust=False).mean().iloc[-1]
                high_5d = hc.tail(5).max()
                trigger_price = round(high_5d + 1, 2)
                buffer_price = trigger_price * 0.998
                
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                is_uptrend, is_breakout_mode = price > dma200, 40 <= rsi <= 60
                stock_key = t.replace(".NS", "")
                
                status, strategy = "⏳ WAIT", f"Breakout @ ₹{trigger_price}"
                
                if is_uptrend and is_breakout_mode and price >= trigger_price:
                    if stock_key not in st.session_state.triggers:
                        st.session_state.triggers[stock_key] = time.time()
                    elapsed = (time.time() - st.session_state.triggers[stock_key]) / 60
                    if elapsed >= 15:
                        if last_15m_close >= trigger_price and price >= buffer_price:
                            status, strategy = "🎯 CONFIRMED BUY", "Verified Breakout"
                        else:
                            status, strategy = "❌ FAILED BREAKOUT", "15m Close was weak"
                            del st.session_state.triggers[stock_key]
                    else:
                        status, strategy = "👀 OBSERVING", f"Wait {15 - int(elapsed)}m"
                elif rsi > 60:
                    status, strategy = "⏳ WAIT", f"Pullback to ₹{ema20:.1f}"
                
                res = {"Stock": stock_key, "Status": status, "Strategy": strategy, "Price": round(price, 2), "StopLoss": round(float(hc.tail(20).min() * 0.985), 2)}
                results.append(res)
            except: continue
        df = pd.DataFrame(results)
        df['sort'] = df['Status'].map({"🎯 CONFIRMED BUY": 0, "👀 OBSERVING": 1, "⏳ WAIT": 2, "❌ FAILED BREAKOUT": 3})
        st.dataframe(df.sort_values('sort').drop(columns=['sort']), use_container_width=True, hide_index=True, height=500)
    except: st.info("Scanning...")

# --- TAB 2: PORTFOLIO (WITH SMART DROPDOWN) ---
with tab2:
    st.subheader("🚀 Virtual Portfolio")
    c1, c2, c3, c4 = st.columns(4)
    
    # NEW: Dropdown Search Menu
    p_vt = c1.selectbox("Search Stock Name:", options=NIFTY_50_TICKERS, help="Select a stock from the Nifty 50 list.")
    p_vq = c2.number_input("Qty:", min_value=1, value=1)
    p_vp = c3.number_input("Entry Price (₹):", min_value=0.1, value=100.0)
    p_sl = c4.number_input("Stop Loss (₹):", min_value=0.1, value=90.0)
    
    if st.button("🚀 Execute & Save Trade"):
        st.session_state.portfolio.append({
            "Ticker": f"{p_vt}.NS", "Symbol": p_vt, 
            "Qty": p_vq, "BuyPrice": p_vp, "StopPrice": p_sl
        })
        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
        st.rerun()

    if st.session_state.portfolio:
        p_res = []
        total_pnl = 0.0
        p_list = list(set([i['Ticker'] for i in st.session_state.portfolio]))
        c_raw = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        
        for i in st.session_state.portfolio:
            try:
                raw_v = c_raw[i['Ticker']].dropna().iloc[-1] if len(p_list) > 1 else c_raw.dropna().iloc[-1]
                c_px = float(raw_v)
                
                # Alert Logic
                if c_px <= i['StopPrice']:
                    st.toast(f"🚨 ALERT: {i['Symbol']} hit Stop Loss at ₹{c_px}", icon="⚠️")
                    st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                
                pnl = (c_px - i['BuyPrice']) * i['Qty']
                total_pnl += pnl
                p_res.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "Stop": i['StopPrice'], "Current": round(c_px, 2), "P&L": round(float(pnl), 2)})
            except: continue
        st.dataframe(pd.DataFrame(p_res), use_container_width=True, hide_index=True)
        st.metric("Total P&L", f"₹{total_pnl:,.2f}", delta=round(float(total_pnl), 2))
        if st.button("Reset Portfolio"):
            if os.path.exists(PORTFOLIO_FILE): os.remove(PORTFOLIO_FILE)
            st.session_state.portfolio = []
            st.rerun()

# --- TAB 3: WATCHLIST ---
with tab3:
    st.subheader("🔍 Stock Watchlist")
    lu = st.selectbox("Quick Add (Nifty 50):", options=NIFTY_50_TICKERS, key="lu_w")
    if st.button(f"Add {lu} to Watchlist"):
        if lu not in st.session_state.watchlist: 
            st.session_state.watchlist.append(lu)
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
