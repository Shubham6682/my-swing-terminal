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
if 'triggers' not in st.session_state: st.session_state.triggers = {} # Store trigger timestamps

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
                hc, lc_15m, lc_1m = h_data['Close'][t].dropna(), l_15m_data['Close'][t].dropna(), l_1m_data['Close'][t].dropna()
                price, last_15m_close = float(lc_1m.iloc[-1]), float(lc_15m.iloc[-1])
                dma200 = hc.rolling(200).mean().iloc[-1]
                ema20 = hc.ewm(span=20, adjust=False).mean().iloc[-1]
                high_5d = hc.tail(5).max()
                trigger_price = round(high_5d + 1, 2)
                buffer_price = trigger_price * 0.998
                
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                # --- AUTOMATED OBSERVATION LOGIC ---
                is_uptrend = price > dma200
                is_breakout_mode = 40 <= rsi <= 60
                stock_key = t.replace(".NS", "")
                
                status, strategy = "⏳ WAIT", f"Breakout @ ₹{trigger_price}"
                
                if is_uptrend and is_breakout_mode and price >= trigger_price:
                    # Mark initial trigger time if not already stored
                    if stock_key not in st.session_state.triggers:
                        st.session_state.triggers[stock_key] = time.time()
                    
                    elapsed = (time.time() - st.session_state.triggers[stock_key]) / 60
                    
                    if elapsed >= 15:
                        if last_15m_close >= trigger_price and price >= buffer_price:
                            status, strategy = "🎯 CONFIRMED BUY", "Verified Breakout"
                        else:
                            status, strategy = "❌ FAILED BREAKOUT", "15m Close was weak"
                            # Clean up failed trigger to allow re-triggering later
                            del st.session_state.triggers[stock_key]
                    else:
                        status, strategy = "👀 OBSERVING", f"Locked: {15 - int(elapsed)}m left"
                elif rsi > 60:
                    status, strategy = "⏳ WAIT", f"Pullback to ₹{ema20:.1f}"
                
                stop = float(h_data['Low'][t].tail(20).min()) * 0.985
                risk_ps = price - stop
                qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 1
                
                res = {"Stock": stock_key, "Status": status, "Strategy": strategy, "Price": round(price, 2), "StopLoss": round(stop, 2), "Profit": round(qty * (risk_ps * 2), 2)}
                if view_mode == "Pro (Deep-Dive)":
                    res["RSI"], res["Vol"] = round(rsi, 1), f"{h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean():.1f}x"
                results.append(res)
            except: continue
        
        df = pd.DataFrame(results)
        df['sort'] = df['Status'].map({"🎯 CONFIRMED BUY": 0, "👀 OBSERVING": 1, "⏳ WAIT": 2, "❌ FAILED BREAKOUT": 3})
        st.dataframe(df.sort_values('sort').drop(columns=['sort']), use_container_width=True, hide_index=True, height=500)
    except: st.info("Initializing observation engine...")

# --- TABS 2 & 3 REMAIN THE SAME AS STABLE VERSION ---
