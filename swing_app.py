import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Nifty 50 Real-Time Terminal", layout="wide")
# Set refresh to 1 minute for "Real-Time" feel, but keep logic on 15-min precision
st_autorefresh(interval=60000, key="datarefresh") 

# --- TICKER LIST ---
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

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI ---
st.title("🏹 Nifty 50 Real-Time Terminal")

# Sidebar
st.sidebar.header("🛡️ Risk Settings")
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# Real-Time Clock (IST)
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.datetime.now(ist)
st.markdown(f"### ⏱️ Last Real-Time Sync: `{now_ist.strftime('%H:%M:%S')}` IST")

with st.spinner("Streaming Live Data from NSE..."):
    # We download 2 days of 1-minute data for the 'Real-Time' Price
    # AND 2 years of daily data for the indicators
    hist_data = yf.download(NIFTY_50, period="2y", interval="1d", group_by='ticker', progress=False)
    live_data = yf.download(NIFTY_50, period="1d", interval="1m", group_by='ticker', progress=False)

results = []
for t in NIFTY_50:
    row = {"Stock": t.replace(".NS", ""), "Price": "N/A", "Action": "⏳ WAIT", "Reason": "Syncing..."}
    try:
        # Get Technicals from Historical Data
        df_h = hist_data[t].dropna()
        # Get Real-Time Price from Live Data
        df_l = live_data[t].dropna()
        
        if not df_h.empty and not df_l.empty:
            # TRUE REAL-TIME PRICE
            real_time_price = float(df_l['Close'].iloc[-1])
            
            # Indicators (Historical)
            dma_200 = float(df_h['Close'].rolling(window=200).mean().iloc[-1])
            rsi_val = float(calculate_rsi(df_h['Close']).iloc[-1])
            
            # Criteria
            is_bullish = real_time_price > dma_200
            is_rsi_safe = 40 < rsi_val < 65
            
            stop_loss = float(df_h['Low'].tail(20).min()) * 0.985
            risk_per_share = real_time_price - stop_loss
            
            if is_bullish and is_rsi_safe:
                qty = int((cap * (risk_p / 100)) // risk_per_share) if risk_per_share > 0 else 0
                row.update({
                    "Price": round(real_time_price, 2),
                    "RSI": round(rsi_val, 1),
                    "Action": "✅ BUY",
                    "Reason": f"Qty: {qty}"
                })
            else:
                row.update({
                    "Price": round(real_time_price, 2),
                    "RSI": round(rsi_val, 1),
                    "Action": "⏳ WAIT",
                    "Reason": "Trend/RSI Fail"
                })
    except: pass
    results.append(row)

if results:
    full_df = pd.DataFrame(results)
    
    # Sorting: Green at top
    full_df['Sort'] = full_df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    full_df = full_df.sort_values('Sort').drop('Sort', axis=1)

    # Style
    def style_fn(row):
        color = '#27ae60' if row['Action'] == "✅ BUY" else '#ff4d4d'
        return [f'background-color: {color}; color: white'] * len(row)

    st.dataframe(full_df.style.apply(style_fn, axis=1), use_container_width=True, hide_index=True)

st.info("💡 App auto-refreshes every 60 seconds to pull the latest 1-minute tick.")
