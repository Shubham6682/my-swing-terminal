import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 High-Freq Terminal", layout="wide")

# Determine Market Status for Refresh Rate
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
market_open = False
if now.weekday() < 5:
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start <= now <= end:
        market_open = True

# DUAL REFRESH: 5 seconds for indices if open, 60 seconds for stock logic
refresh_rate = 5000 if market_open else 60000
st_autorefresh(interval=refresh_rate, key="datarefresh")

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

# --- 3. LIVE INDEX HEADER ---
def display_header(is_open, current_time):
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    # Smallest possible fetch for speed
    idx_data = yf.download(list(indices.values()), period="2d", interval="1m", progress=False)
    
    cols = st.columns(len(indices) + 1)
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            px = idx_data['Close'][ticker].dropna()
            if not px.empty:
                curr, prev = float(px.iloc[-1]), float(px.iloc[0])
                change = curr - prev
                pct = (change / prev) * 100
                cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            else:
                cols[i].metric(name, "N/A")
        except:
            cols[i].metric(name, "Syncing...")

    status_icon = "🟢 OPEN" if is_open else "⚪ CLOSED"
    cols[-1].markdown(f"**Status:** {status_icon}\n\n**Update:** Every {refresh_rate/1000}s")

display_header(market_open, now)
st.divider()

# --- 4. SIDEBAR ---
st.sidebar.header("🛡️ Risk Settings")
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 5. DATA ENGINE ---
@st.cache_data(ttl=55) # Cache slightly less than stock refresh to ensure fresh data
def get_stock_data():
    h = yf.download(NIFTY_50, period="2y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="5d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Updating Terminal..."):
        h_data, l_data = get_stock_data()

    results = []
    total_prof = 0.0

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            # Indicators
            dma200 = float(hc.rolling(200).mean().iloc[-1])
            delta = hc.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

            # Signal & Risk
            is_buy = (price > dma200 and 40 < rsi < 65)
            stop = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_amt = price - stop
            
            qty, profit = 0, 0.0
            if is_buy and risk_amt > 0:
                qty = int((cap * (risk_p / 100)) // risk_amt)
                profit = round(qty * (risk_amt * 2), 2)
                total_prof += profit

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Qty": qty,
                "Target": round(price + (risk_amt * 2), 2) if is_buy else 0.0,
                "Profit": profit,
                "RSI": round(rsi, 1)
            })
        except: continue

    if results:
        df = pd.DataFrame(results)
        df['sort'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
        df = df.sort_values('sort').drop(columns=['sort'])
        
        st.sidebar.markdown("---")
        st.sidebar.metric("💰 Potential Profit", f"₹{total_prof:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.info("Market connection active. Waiting for data stream...")
