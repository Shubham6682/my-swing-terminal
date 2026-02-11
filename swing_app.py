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

# Market Hours: 9:15 AM - 3:30 PM
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

# Initialize Session States
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'watchlist' not in st.session_state: st.session_state.watchlist = []

# --- 2. INDEX HEADER (STAYS VISIBLE) ---
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

# --- 3. THE TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & Lookup"])

# --- TAB 1: MARKET SCANNER ---
with tab1:
    st.sidebar.header("🛡️ Strategy Control")
    cap = st.sidebar.number_input("Capital", value=50000)
    risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)
    
    NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

    @st.cache_data(ttl=30)
    def get_market_data():
        h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
        l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
        return h, l

    try:
        h_data, l_data = get_market_data()
        n_perf = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
        results = []

        for t in NIFTY_50:
            try:
                hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
                price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                vol_m = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
                rs_b = (hc.iloc[-1] / hc.iloc[-63]) - 1 > n_perf

                is_buy = (price > dma200 and 40 < rsi < 65)
                stop = float(h_data['Low'][t].tail(20).min()) * 0.985
                risk_ps = price - stop
                qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 0
                if qty == 0 and cap >= price: qty = 1
                
                results.append({
                    "Stock": t.replace(".NS", ""),
                    "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                    "Price": round(price, 2),
                    "StopLoss": round(stop, 2),
                    "Profit": round(qty * (risk_ps * 2), 2),
                    "RSI": round(rsi, 1),
                    "Vol": f"{vol_m:.1f}x",
                    "Leader": "Yes" if rs_b else "No"
                })
            except: continue

        df = pd.DataFrame(results)
        df['s'] = df['Action'].apply(lambda x: 0 if "BUY" in x else 1)
        df = df.sort_values('s').drop(columns=['s'])
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)
    except: st.info("Scanning Market...")

# --- TAB 2: VIRTUAL PORTFOLIO ---
with tab2:
    st.subheader("🚀 Virtual Portfolio Tracker")
    p_col1, p_col2, p_col3 = st.columns(3)
    with p_col1: vt = st.text_input("Stock Symbol:", key="vt").upper()
    with p_col2: vq = st.number_input("Qty:", min_value=1, value=1)
    with p_col3: vp = st.number_input("Buy Price (₹):", min_value=0.1, value=100.0)
    
    if st.button("🚀 Add Virtual Trade"):
        if vt:
            st.session_state.portfolio.append({"Ticker": f"{vt}.NS", "Symbol": vt, "Qty": vq, "BuyPrice": vp})
            st.rerun()

    if st.session_state.portfolio:
        p_res = []
        total_pnl = 0.0
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        curr_p_data = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        
        for i in st.session_state.portfolio:
            try:
                c_px = curr_p_data[i['Ticker']].dropna().iloc[-1] if len(p_list)>1 else curr_p_data.dropna().iloc[-1]
                pnl = (c_px - i['BuyPrice']) * i['Qty']
                total_pnl += pnl
                p_res.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "Current": round(c_px, 2), "P&L": round(pnl, 2)})
            except: continue
        
        st.table(pd.DataFrame(p_res))
        st.metric("Total P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
        if st.button("Reset Portfolio"): 
            st.session_state.portfolio = []
            st.rerun()

# --- TAB 3: WATCHLIST & LOOKUP ---
with tab3:
    st.subheader("🔍 Deep-Dive & Watchlist")
    lookup = st.text_input("Deep-Dive Stock (e.g. HAL, ITC):").upper()
    if lookup:
        # Simplified lookup logic
        try:
            d_px = yf.Ticker(f"{lookup}.NS").history(period="1d")['Close'].iloc[-1]
            st.write(f"**Current Price of {lookup}:** ₹{d_px:,.2f}")
            if st.button(f"Add {lookup} to Watchlist"):
                if lookup not in st.session_state.watchlist: st.session_state.watchlist.append(lookup)
        except: st.error("Ticker not found.")
    
    st.divider()
    st.write("**Your Watchlist:**")
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
    if st.button("Clear Watchlist"):
        st.session_state.watchlist = []
        st.rerun()
