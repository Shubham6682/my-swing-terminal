import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Sync

# --- 2. MASTER TICKER LIST ---
NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

# --- 3. MARKET HEADER & STATUS ---
def display_header():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    
    # Precise Market Hours Check (9:15 AM - 3:30 PM)
    market_open = False
    if now.weekday() < 5: # Mon-Fri
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if start <= now <= end:
            market_open = True
    
    # Indices Bar
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    idx_data = yf.download(list(indices.values()), period="2d", interval="1m", progress=False)
    
    cols = st.columns(len(indices) + 1)
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            # Fixed Bracket Syntax here
            prices = idx_data['Close'][ticker].dropna()
            if not prices.empty:
                curr = float(prices.iloc[-1])
                prev = float(prices.iloc[0])
                change = curr - prev
                pct = (change / prev) * 100
                cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            else:
                cols[i].metric(name, "N/A", "Market Closed")
        except Exception:
            cols[i].metric(name, "N/A")

    status_icon = "🟢 OPEN" if market_open else "⚪ CLOSED"
    cols[-1].markdown(f"**Status:** {status_icon}\n\n**Time:** {now.strftime('%H:%M:%S')}")

# Run Header UI
display_header()
st.divider()

# --- 4. SIDEBAR SETTINGS ---
st.sidebar.header("🛡️ Strategy Settings")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, 0.5)

# --- 5. DATA ENGINE ---
@st.cache_data(ttl=60)
def get_market_data():
    """Syncs historical and live data streams."""
    h = yf.download(NIFTY_50, period="2y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="5d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Syncing Terminal..."):
        h_data, l_data = get_market_data()

    results = []
    total_prof_pool = 0.0

    for t in NIFTY_50:
        try:
            h_close = h_data['Close'][t].dropna()
            l_close = l_data['Close'][t].dropna()
            
            # Use 1m price if available, otherwise fallback to last Daily Close
            price = float(l_close.iloc[-1]) if not l_close.empty else float(h_close.iloc[-1])

            # Indicator Math
            dma200 = float(h_close.rolling(window=200).mean().iloc[-1])
            delta = h_close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

            # Strategy Parameters
            is_buy = (price > dma200 and 40 < rsi < 65)
            
            # Risk Logic: 20-day low stop loss
            low_20 = float(h_data['Low'][t].tail(20).min())
            stop_loss = low_20 * 0.985
            risk_amt = price - stop_loss
            
            qty = 0
            profit = 0.0
            if is_buy and risk_amt > 0:
                qty = int((cap * (risk_p / 100)) // risk_amt)
                profit = round(qty * (risk_amt * 2), 2)
                total_prof_pool += profit

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Qty": qty,
                "Target": round(price + (risk_amt * 2), 2) if is_buy else 0,
                "Profit": profit,
                "RSI": round(rsi, 1)
            })
        except Exception:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="Action")
        st.sidebar.markdown("---")
        st.sidebar.metric("💰 Potential Profit", f"₹{total_prof_pool:,.2f}")
        st.sidebar.write(f"Risk per trade: ₹{cap*(risk_p/100):.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Waiting for Data... ({e})")
