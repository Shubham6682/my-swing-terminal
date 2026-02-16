import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Dual-Engine Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM IST (Refresh every 30s for heavy math)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=30000 if is_open else 60000, key="dual_engine_sync")

# --- 2. PERSISTENCE LAYER ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        st.session_state.portfolio = pd.read_csv(PORTFOLIO_FILE).to_dict('records')
    else: st.session_state.portfolio = []

if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 
if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HELPER MATH FUNCTIONS (Zero Dependency) ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_width(series, period=20):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    width = (upper - lower) / sma
    return width

# --- 4. HEADER ---
st.title("🏹 Elite Dual-Engine Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df_i = yf.Ticker(ticker).history(period="5d")
        if not df_i.empty:
            c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
            idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
    except: pass
idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 5. SIDEBAR (THE MODE SWITCH) ---
with st.sidebar:
    st.header("🧠 Strategy Engine")
    # THE NEW SWITCH
    strategy_mode = st.radio("Select Intelligence Mode:", 
                             ["🛡️ Pro Sentinel (Swing)", "🎯 Elite Sniper (Extreme)"],
                             captions=["Trend Following & Breakouts", "VCP Squeeze & Volume Surges"])
    
    st.divider()
    st.header("🔔 Live Entry Feed")
    if not st.session_state.alert_log: st.info("Scanning..." if is_open else "Market Closed")
    else:
        for s, ts in sorted(st.session_state.alert_log.items(), key=lambda x: x[1], reverse=True)[:5]:
            st.success(f"🚀 {s}: {int((time.time()-ts)/60)}m ago")
            
    st.divider()
    risk_p = st.slider("Max Risk per Trade (%)", 0.5, 3.0, 1.5)

# --- 6. DATA ENGINE ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def fetch_data():
    # Fetch 1y data to cover both 200DMA (Sentinel) and RSI/Bollinger (Sniper)
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)['Close']
    l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
    v = yf.download(TICKERS_NS, period="1mo", progress=False)['Volume'] # Volume for Sniper
    if l.empty or l.dropna(how='all').empty: l = h.tail(1)
    return h, l, v

# --- 7. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Hunter", "🚀 Virtual Portfolio", "🎯 Watchlist"])

with tab1:
    try:
        h_data, l_data, v_data = fetch_data()
        results = []
        
        # Pre-calculate Nifty Return for Relative Strength
        nifty_hist = h_data['^NSEI'].dropna()
        nifty_perf = nifty_hist.iloc[-1] / nifty_hist.iloc[-63]

        for t in TICKERS_NS:
            try:
                hist = h_data[t].dropna()
                ltp = float(l_data[t].dropna().iloc[-1])
                prev_close = float(hist.iloc[-2])
                day_change = ((ltp - prev_close) / prev_close) * 100
                dma200 = hist.rolling(200).mean().iloc[-1]
                
                # --- STRATEGY 1: PRO SENTINEL ---
                if strategy_mode == "🛡️ Pro Sentinel (Swing)":
                    high_5d = hist.tail(6).iloc[:-1].max()
                    trigger = round(high_5d * 1.002, 2)
                    is_leader = (hist.iloc[-1]/hist.iloc[-63]) > nifty_perf
                    
                    status = "🎯 CONFIRMED" if ltp >= trigger and ltp > dma200 and is_leader else "⏳ WAIT"
                    gap = ((ltp - trigger)/trigger)*100
                    
                    # Risk Logic
                    note = "🟢 SAFE ZONE"
                    if day_change < -1.5: note = "🔴 WEAK (Dumping)"
                    elif not is_leader: note = "🟡 LAGGARD"
                    elif ltp < dma200: note = "🔴 DOWN TREND"
                    elif gap > 1.8: note = "🟡 CHASING"
                    
                    results.append({
                        "Stock": t.replace(".NS",""), 
                        "Status": status, 
                        "LTP": round(ltp, 2), 
                        "Day %": f"{day_change:+.2f}%",
                        "Risk Info": note,
                        "Entry": trigger,
                        "Gap %": f"{gap:+.2f}%"
                    })

                # --- STRATEGY 2: ELITE SNIPER (EXTREME) ---
                else:
                    # Advanced Math
                    rsi = calculate_rsi(hist).iloc[-1]
                    bb_width = calculate_bollinger_width(hist).iloc[-1]
                    
                    # Volume Check
                    vol_now = v_data[t].iloc[-1]
                    vol_avg = v_data[t].rolling(20).mean().iloc[-1]
                    vol_spike = vol_now > (vol_avg * 1.5)
                    
                    # Status Logic
                    status = "😴 SLEEPING"
                    if bb_width < 0.10: status = "👀 COILING (Squeeze)" # VCP Pattern
                    elif vol_spike and day_change > 1.5 and rsi > 55: status = "🚀 BREAKOUT"
                    
                    # Only show interesting stocks in Sniper Mode
                    if status != "😴 SLEEPING":
                        results.append({
                            "Stock": t.replace(".NS",""),
                            "Status": status,
                            "LTP": round(ltp, 2),
                            "Day %": f"{day_change:+.2f}%",
                            "RSI": round(rsi, 1),
                            "Vol Spike": "🔥 YES" if vol_spike else "No",
                            "Squeeze": "✅ YES" if bb_width < 0.10 else "No"
                        })

            except: continue
        
        # Display Logic
        if results:
            df_res = pd.DataFrame(results).sort_values("Status")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            if strategy_mode == "🎯 Elite Sniper (Extreme)":
                st.info("No Sniper Setups Found. The market is noisy. This is normal for Extreme Mode.")
            else:
                st.info("Scanning...")

    except Exception as e: st.error(f"Data Engine Error: {e}")

with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        live_p = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        if live_p.empty: live_p = h_data[p_list].tail(1)
        disp_p = []
        for i in st.session_state.portfolio:
            try:
                cv = float(live_p[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(live_p.dropna().iloc[-1])
                disp_p.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "SL": i['StopPrice'], "Current": round(cv, 2), "P&L": round((cv - i['BuyPrice']) * i['Qty'], 2)})
            except: continue
        st.dataframe(pd.DataFrame(disp_p), use_container_width=True, hide_index=True)

    with st.expander("➕ Manual Entry"):
        c1, c2, c3 = st.columns(3)
        nt = c1.selectbox("Ticker", TICKERS_NS)
        nq = c2.number_input("Qty", min_value=1)
        np = c3.number_input("Price", min_value=1.0)
        if st.button("Add Trade"):
            st.session_state.portfolio.append({"Ticker": nt, "Symbol": nt.replace(".NS",""), "Qty": nq, "BuyPrice": np, "StopPrice": np * (1 - (risk_p/100))})
            pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
            st.rerun()

with tab3:
    st.subheader("🎯 Watchlist")
    lu = st.selectbox("Quick Add:", NIFTY_50)
    if st.button(f"Add {lu}"):
        if lu not in st.session_state.watchlist: st.session_state.watchlist.append(lu)
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
