import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP & TIMEZONE ---
st.set_page_config(page_title="Elite Sentinel Pro", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM IST (Currently CLOSED for Analysis)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=15000 if is_open else 60000, key="sentinel_final_audit")

# --- 2. PERSISTENCE LAYER ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        df_load = pd.read_csv(PORTFOLIO_FILE)
        for col in ['StopPrice', 'BuyPrice', 'Qty', 'Symbol', 'Ticker']:
            if col not in df_load.columns: df_load[col] = 0
        st.session_state.portfolio = df_load.to_dict('records')
    else: st.session_state.portfolio = []

if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HEADER & MARKET DASHBOARD ---
st.title("🏹 Elite Sentinel: Zero-Error Terminal")
indices = {"Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "IT Index": "^CNXIT"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df_i = yf.Ticker(ticker).history(period="2d")
        if not df_i.empty:
            c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
            idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
    except: pass
idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 4. SIDEBAR ALERTS ---
with st.sidebar:
    st.header("⚙️ Settings")
    view_mode = st.radio("Display Mode", ["Simple View", "Risk Analysis (Pro)"])
    st.divider()
    st.header("🔔 Live Entry Feed")
    if not st.session_state.alert_log:
        st.info("No confirmed breakouts yet.")
    else:
        sorted_log = sorted(st.session_state.alert_log.items(), key=lambda x: x[1], reverse=True)
        for stock, ts in sorted_log[:5]:
            m_ago = int((time.time() - ts) / 60)
            st.success(f"🚀 {stock}: Confirmed {m_ago}m ago")
    st.divider()
    risk_p = st.slider("Max Risk per Trade (%)", 0.5, 3.0, 1.5)

# --- 5. DATA ENGINE ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=30)
def fetch_market_data():
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)['Close']
    l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
    return h, l

# --- 6. CORE LOGIC EVALUATION ---
try:
    h_data, l_data = fetch_market_data()
    results = []
    
    for t in TICKERS_NS:
        try:
            hist = h_data[t].dropna()
            live = l_data[t].dropna()
            if hist.empty or live.empty: continue
            
            ltp = float(live.iloc[-1])
            prev_close = float(hist.iloc[-1])
            day_change = ((ltp - prev_close) / prev_close) * 100
            
            dma200 = hist.rolling(window=200).mean().iloc[-1]
            high_5d = hist.tail(5).max()
            trigger = round(high_5d * 1.002, 2)
            
            # Leader Check
            nifty_hist = h_data['^NSEI'].dropna()
            is_leader = (hist.iloc[-1] / hist.iloc[-63]) > (nifty_hist.iloc[-1] / nifty_hist.iloc[-63])
            
            # Status Logic
            status = "⏳ WAIT"
            if ltp >= trigger and ltp > dma200 and is_leader:
                if t not in st.session_state.triggers: st.session_state.triggers[t] = time.time()
                elapsed = (time.time() - st.session_state.triggers[t]) / 60
                if elapsed >= 15:
                    status = "🎯 CONFIRMED"
                    s_name = t.replace(".NS","")
                    if s_name not in st.session_state.alert_log:
                        st.toast(f"SIGNAL: {s_name}", icon="🚀")
                        st.audio("https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True)
                        st.session_state.alert_log[s_name] = time.time()
                else: status = f"👀 OBSERVE ({15-int(elapsed)}m)"

            # --- THE "USER-VERIFIED" RISK LOGIC ---
            gap_pct = ((ltp - trigger) / trigger) * 100
            if day_change < -1.5:
                risk_note = "🔴 WEAK (Dumping)"
            elif not is_leader:
                risk_note = "🟡 LAGGARD (No Strength)"
            elif ltp < dma200:
                risk_note = "🔴 DOWN TREND"
            elif gap_pct > 1.5:
                risk_note = "🟡 CHASING"
            elif gap_pct < -4.0:
                risk_note = "⚪ COLD"
            else:
                risk_note = "🟢 SAFE ZONE"

            res = {"Stock": t.replace(".NS",""), "Status": status, "LTP": round(ltp, 2), "Day %": f"{day_change:+.2f}%"}
            if view_mode == "Risk Analysis (Pro)":
                res.update({"Risk Info": risk_note, "Entry": trigger, "Gap %": f"{gap_pct:+.2f}%", "Leader": "✅" if is_leader else "❌"})
            results.append(res)
        except: continue

    st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Syncing Live Data...")
