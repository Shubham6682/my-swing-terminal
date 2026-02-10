import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Pro Swing Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Status
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="pro_sync")

# Initialize Watchlist in Session State
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. INDEX HEADER ---
st.title("🏹 Pro Swing Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        if not df_live.empty and not df_hist.empty:
            curr = df_live['Close'].iloc[-1]
            prev = df_hist['Close'].iloc[0]
            change = curr - prev
            pct = (change / prev) * 100
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
    except:
        idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 3. MANUAL STOCK DEEP-DIVE & WATCHLIST ---
st.subheader("🎯 Manual Stock Deep-Dive")
lookup_ticker = st.text_input("Enter NSE Stock Ticker (e.g., ZOMATO, HAL):", "").upper()

if lookup_ticker:
    full_t = f"{lookup_ticker}.NS"
    try:
        with st.spinner(f"Analyzing {lookup_ticker}..."):
            raw_data = yf.download([full_t, "^NSEI"], period="1y", interval="1d", progress=False)
            h = raw_data['Close'][full_t].dropna()
            nifty_h = raw_data['Close']['^NSEI'].dropna()
            
            cp = h.iloc[-1]
            dma200 = h.rolling(200).mean().iloc[-1]
            ema20 = h.ewm(span=20, adjust=False).mean().iloc[-1]
            recent_high = h.tail(20).max()
            
            # RSI
            delta = h.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # Relative Strength
            s_3m = (h.iloc[-1] / h.iloc[-63]) - 1
            n_3m = (nifty_h.iloc[-1] / nifty_h.iloc[-63]) - 1
            is_leader = s_3m > n_3m

            # UI Analysis
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Price", f"₹{cp:,.2f}")
            m2.metric("RSI", f"{rsi:.1f}")
            m3.metric("EMA (20)", f"₹{ema20:,.2f}")
            m4.metric("Market Leader", "YES" if is_leader else "NO")

            # Condition Check
            reasons = []
            if cp < dma200: reasons.append("Price below 200-DMA")
            if rsi > 65: reasons.append("RSI Overbought")
            if rsi < 40: reasons.append("Weak Momentum")
            if not is_leader: reasons.append("Lagging Nifty 50")

            if not reasons:
                st.success(f"🚀 {lookup_ticker} is a HIGH QUALITY BUY at ₹{cp:,.2f}")
            else:
                st.warning(f"⏳ Wait: {', '.join(reasons)}")
                
                # RECOMMENDED ENTRY POINT
                st.info(f"💡 **Professional Entry Recommendation:**")
                if rsi > 65:
                    st.write(f"Wait for a pullback to the **20-Day EMA (₹{ema20:,.2f})**. Buying now is risky.")
                elif cp < dma200:
                    st.write(f"Avoid until price closes above **200-DMA (₹{dma200:,.2f})** on high volume.")
                else:
                    st.write(f"Consider entry on a breakout above **Recent High (₹{recent_high:,.2f})**.")

            # Watchlist Button
            if st.button(f"➕ Add {lookup_ticker} to Watchlist"):
                if lookup_ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(lookup_ticker)
                    st.toast(f"{lookup_ticker} Added!")

    except Exception:
        st.error("Could not find ticker. Use NSE symbols like 'RELIANCE'.")

st.divider()

# --- 4. SIDEBAR (WATCHLIST & SETTINGS) ---
with st.sidebar:
    st.header("📋 My Watchlist")
    if st.session_state.watchlist:
        for stock in st.session_state.watchlist:
            st.write(f"🔹 **{stock}**")
        if st.button("Clear Watchlist"):
            st.session_state.watchlist = []
    else:
        st.write("Your watchlist is empty.")
    
    st.divider()
    st.header("🛡️ Strategy Control")
    mode = st.sidebar.radio("Rigidity", ["Normal", "Pro"])
    cap = st.sidebar.number_input("Capital", value=50000)
    risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 5. MAIN SCANNER ---
# (Main scanner logic for Nifty 50 stocks remains here as per previous versions)
