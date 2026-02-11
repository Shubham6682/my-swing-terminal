import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Elite Swing Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM IST
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

# Auto-refresh every 15s during market, 60s otherwise
st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

# Initialize Session States
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'watchlist' not in st.session_state: st.session_state.watchlist = []

# --- 2. INDEX HEADER ---
st.title("🏹 Elite Momentum Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        if not df_live.empty and not df_hist.empty:
            curr, prev = df_live['Close'].iloc[-1], df_hist['Close'].iloc[0]
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
    risk_p = st.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)

# --- 4. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & Lookup"])

# --- TAB 1: SCANNER ---
with tab1:
    NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

    @st.cache_data(ttl=30)
    def get_market_data():
        h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
        l_15m = yf.download(NIFTY_50, period="2d", interval="15m", progress=False)
        l_1m = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
        return h, l_15m, l_1m

    try:
        h_data, l_15m_data, l_1m_data = get_market_data()
        results = []
        for t in NIFTY_50:
            try:
                hc = h_data['Close'][t].dropna()
                lc_15m = l_15m_data['Close'][t].dropna()
                lc_1m = l_1m_data['Close'][t].dropna()
                
                price = float(lc_1m.iloc[-1])
                last_15m_close = float(lc_15m.iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                ema20 = hc.ewm(span=20, adjust=False).mean().iloc[-1]
                high_5d = hc.tail(5).max()
                trigger_price = round(high_5d + 1, 2)
                
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                is_uptrend = price > dma200
                is_breakout_mode = 40 <= rsi <= 60
                is_confirmed = (last_15m_close >= trigger_price) and is_uptrend and is_breakout_mode
                
                if is_confirmed:
                    status, strategy = "🎯 CONFIRMED BUY", "Breakout Verified"
                elif is_uptrend and is_breakout_mode and price >= trigger_price:
                    status, strategy = "⚡ TRIGGERED", "Wait for 15m Close"
                elif rsi > 60:
                    status, strategy = "⏳ WAIT", f"Pullback to ₹{ema20:.1f}"
                else:
                    status, strategy = "⏳ WAIT", f"Breakout @ ₹{trigger_price}"
                
                stop = float(h_data['Low'][t].tail(20).min()) * 0.985
                risk_ps = price - stop
                qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 1
                
                res = {"Stock": t.replace(".NS", ""), "Status": status, "Strategy": strategy, "Price": round(price, 2), "StopLoss": round(stop, 2), "Profit": round(qty * (risk_ps * 2), 2)}
                if view_mode == "Pro (Deep-Dive)":
                    res["RSI"] = round(rsi, 1)
                    res["Vol"] = f"{h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean():.1f}x"
                results.append(res)
            except: continue
        
        df = pd.DataFrame(results)
        df['sort'] = df['Status'].map({"🎯 CONFIRMED BUY": 0, "⚡ TRIGGERED": 1, "⏳ WAIT": 2})
        st.dataframe(df.sort_values('sort').drop(columns=['sort']), use_container_width=True, hide_index=True, height=500)
    except: st.info("Scanning...")

# --- TAB 2: PORTFOLIO ---
with tab2:
    st.subheader("🚀 Practice Portfolio")
    c1, c2, c3 = st.columns(3)
    p_vt = c1.text_input("Stock Symbol:", key="p_vt_main").upper()
    p_vq = c2.number_input("Qty:", min_value=1, value=1, key="p_vq_main")
    p_vp = c3.number_input("Price (₹):", min_value=0.1, value=100.0, key="p_vp_main")
    
    if st.button("🚀 Add Virtual Trade", key="add_v_btn"):
        if p_vt:
            st.session_state.portfolio.append({"Ticker": f"{p_vt}.NS", "Symbol": p_vt, "Qty": p_vq, "BuyPrice": p_vp})
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
                pnl = (c_px - i['BuyPrice']) * i['Qty']
                total_pnl += pnl
                p_res.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": round(float(i['BuyPrice']), 2), "Current": round(c_px, 2), "P&L": round(float(pnl), 2)})
            except: continue
        st.dataframe(pd.DataFrame(p_res), use_container_width=True, hide_index=True)
        st.metric("Total Unrealized P&L", f"₹{total_pnl:,.2f}", delta=round(float(total_pnl), 2))
        if st.button("Reset Portfolio", key="reset_v_btn"): st.session_state.portfolio = []; st.rerun()

# --- TAB 3: WATCHLIST ---
with tab3:
    st.subheader("🔍 Market Search")
    lu = st.text_input("Search Ticker:", key="lu_main").upper()
    if lu:
        try:
            px = float(yf.Ticker(f"{lu}.NS").history(period="1d")['Close'].iloc[-1])
            st.write(f"**Current Price:** ₹{px:,.2f}")
            if st.button(f"Add {lu} to Watchlist", key="add_w_btn"):
                if lu not in st.session_state.watchlist: st.session_state.watchlist.append(lu)
        except: st.error("Lookup failed.")
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
    if st.button("Clear Watchlist", key="clear_w_btn"): st.session_state.watchlist = []; st.rerun()
