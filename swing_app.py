import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Precision Swing Scanner", layout="wide")

# 15 Minute Refresh (900,000 ms)
st_autorefresh(interval=900000, key="datarefresh") 

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=900) # Cache matches the 15-min window
def get_nifty50_list():
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return [s + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'HINDALCO.NS']

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock_precision(ticker, capital, risk_pct):
    try:
        # Fetching full 1y data to ensure accurate 200 DMA calculation
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200: return None
        
        # Latest Close and Indicators
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # Risk Management (Precision based on 20-day volatility)
        recent_low = float(df['Low'].tail(20).min())
        stop_loss = round(recent_low * 0.98, 2) # 2% buffer below recent swing low
        
        risk_per_share = cmp - stop_loss
        if risk_per_share <= 0: return None
        
        # Position Sizing
        max_loss_allowed = capital * (risk_pct / 100)
        qty = int(max_loss_allowed // risk_per_share)
        target = round(cmp + (risk_per_share * 2), 2)
        
        # Logic Verdict
        is_above_200dma = cmp > dma_200
        is_rsi_safe = 40 < rsi < 65 # Avoiding overbought/oversold extremes
        
        action = "✅ BUY" if (is_above_200dma and is_rsi_safe) else "⏳ WAIT"
        
        return {
            "Stock": ticker.replace(".NS", ""),
            "Price": round(cmp, 2),
            "200 DMA": round(dma_200, 2),
            "RSI": round(rsi, 1),
            "Stop Loss": stop_loss,
            "Target (1:2)": target,
            "Qty": qty,
            "Action": action
        }
    except:
        return None

# --- UI INTERFACE ---
st.title("🏹 Nifty 50 Precision Scanner")
st.write(f"Refreshes every **15 minutes**. Current Time: {datetime.datetime.now().strftime('%H:%M:%S')}")

st.sidebar.header("🛡️ Risk Parameters")
user_cap = st.sidebar.number_input("Capital (₹)", 100000, step=10000)
user_risk = st.sidebar.slider("Risk per trade (%)", 0.5, 2.0, 1.0, 0.5)

with st.spinner("Calculating precision metrics for Nifty 50..."):
    tickers = get_nifty50_list()
    results = []
    # Sequential processing for maximum precision and error logging
    for t in tickers:
        res = analyze_stock_precision(t, user_cap, user_risk)
        if res: results.append(res)

if results:
    df = pd.DataFrame(results)
    
    only_buy = st.checkbox("Show only high-conviction BUY signals", value=True)
    if only_buy:
        df = df[df['Action'] == "✅ BUY"]

    # Simple, unbreakable table
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.error("Data synchronization failed. Please wait for the next 15-min window.")

st.info("💡 **Precision Tip:** Wait for the 15-minute candle to close above the current price before entering.")
