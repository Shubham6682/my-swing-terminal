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

# Refresh every 15s during market hours
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
        l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
        return h, l

    try:
        h_data, l_data = get_market_data()
        results = []

        for t in NIFTY_50:
            try:
                hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
                price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                is_buy = (price > dma200 and 40 < rsi < 65)
                stop = float(h_data['Low'][t].tail(20).min()) * 0.985
                risk_ps = price - stop
                qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 1
                
                res = {"Stock": t.replace(".NS", ""), "Action": "✅ BUY" if is_buy else "⏳ WAIT", "Price": round(price, 2), "StopLoss": round(stop, 2), "Profit": round(qty * (risk_ps * 2), 2), "RSI": round(rsi, 1)}
                
                if view_mode == "Pro (Deep-Dive)":
                    res["ADR%"] = round(((h_data['High'][t] - h_data['Low'][t]) / h_data['Low'][t]).tail(20).mean() * 100, 2)
                    res["Tight%"] = round(((hc.tail(5).max() - hc.tail(5).min()) / hc.tail(5).min()) * 100, 2)
                    res["Vol"] = f"{h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean():.1f}x"
                results.append(res)
            except: continue

        df = pd.DataFrame(results)
        df['s'] = df['Action'].apply(lambda x: 0 if "BUY" in x else 1)
        st.dataframe(df.sort_values('s').drop(columns=['s']), use_container_width=True, hide_index=True, height=500)
    except: st.info("Syncing Market Data...")

# --- TAB 2: PORTFOLIO ---
with tab2:
    st.subheader("🚀 Practice Trading Portfolio")
    p1, p2, p3 = st.columns(3)
    vt = p1.text_input("Stock Symbol (e.g. HAL):", key="p_vt").upper()
    vq = p2.number_input("Quantity:", min_value=1, value=1, key="p_vq")
    vp = p3.number_input("Entry Price (₹):", min_value=0.1, value=100.0, key="p_vp")
    
    if st.button("🚀 Add Virtual Trade"):
        if vt:
            st.session_state.portfolio.append({"Ticker": f"{vt}.NS", "Symbol": vt, "Qty": vq, "BuyPrice": vp})
            st.rerun()

    if st.session_state.portfolio:
        p_res = []
        total_pnl = 0.0
        p_list = list(set([i['Ticker'] for i in st.session_state.portfolio]))
        
        # Fresh Fetch for Portfolio
        c_data_raw = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        
        for i in st.session_state.portfolio:
            try:
                # Force float extraction to avoid series/metadata errors
                if len(p_list) > 1:
                    raw_val = c_data_raw[i['Ticker']].dropna().iloc[-1]
                else:
                    raw_val = c_data_raw.dropna().iloc[-1]
                
                c_px = float(raw_val)
                pnl = (c_px - i['BuyPrice']) * i['Qty']
                total_pnl += pnl
                p_res.append({
                    "Stock": i['Symbol'], 
                    "Qty": i['Qty'], 
                    "Entry": round(float(i['BuyPrice']), 2), 
                    "Current": round(c_px, 2), 
                    "P&L (₹)": round(float(pnl), 2)
                })
            except: continue
        
        if p_res:
            st.dataframe(pd.DataFrame(p_res), use_container_width=True, hide_index=True)
            st.metric("Total Unrealized P&L", f"₹{total_pnl:,.2f}", delta=round(float(total_pnl), 2))
        
        if st.button("Reset All Practice Trades"): 
            st.session_state.portfolio = []
            st.rerun()

# --- TAB 3: WATCHLIST & LOOKUP (FIXED SYNTAX) ---
with tab3:
    st.subheader("🔍 Stock Search & Watchlist")
    lu_ticker = st.text_input("Deep-Dive Stock (e.g. RELIANCE):", key="w_lu").upper()
    
    if lu_ticker:
        try:
            with st.spinner(f"Analyzing {lu_ticker}..."):
                stock_obj = yf.Ticker(f"{lu_ticker}.NS")
                hist = stock_obj.history(period="1d")
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    st.write(f"**Current Market Price of {lu_ticker}:** ₹{current_price:,.2f}")
                    
                    if st.button(f"➕ Add {lu_ticker} to Watchlist"):
                        if lu_ticker not in st.session_state.watchlist:
                            st.session_state.watchlist.append(lu_ticker)
                            st.toast(f"{lu_ticker} Added!")
                else:
                    st.error("No data found for this symbol.")
        except:
            st.error("Ticker lookup failed. Please use standard NSE names.")
    
    st.divider()
    st.write("**Your Active Watchlist:**")
    if st.session_state.watchlist:
        for s in st.session_state.watchlist:
            st.write(f"🔹 {s}")
        if st.button("Clear Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.write("Your watchlist is empty.")
