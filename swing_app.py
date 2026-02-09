import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from concurrent.futures import ThreadPoolExecutor
from streamlit_autorefresh import st_autorefresh

# --- SETTINGS ---
st.set_page_config(page_title="Nifty 50 Swing Scanner", layout="wide")
st_autorefresh(interval=300000, key="datarefresh") # Auto-refresh 5 mins

# --- DATA HELPERS ---
@st.cache_data(ttl=3600)
def get_nifty50_list():
    """Fetches the Nifty 50 ticker list from NSE."""
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return [s + ".NS" for s in df['Symbol'].tolist()]
    except:
        # Fallback list if NSE archives are slow
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'HINDALCO.NS']

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def process_ticker(ticker, capital, risk_pct):
    try:
        # Fetch 1y data
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200: return None
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # Risk Parameters
        # Stop Loss: 20-day low with a 2% extra buffer
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.98, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share <= 0: return None
        
        # Position Sizing
        total_risk_val = capital * (risk_pct / 100)
        qty = int(total_risk_val // risk_per_share)
        target = round(cmp + (risk_per_share * 2), 2)
        
        # Logical Signal
        is_bullish = cmp > dma_200
        # Criteria: Above 200 DMA + RSI is in 'Safe' range (40-65)
        action = "✅ BUY" if (is_bullish and 40 < rsi < 65) else "⏳ WAIT"
        
        return {
            "Stock": ticker.replace(".NS", ""),
            "Price": round(cmp, 2),
            "200 DMA": round(dma_200, 2),
            "RSI": round(rsi, 1),
            "Stop Loss": stop_loss,
            "Target (1:2)": target,
            "Qty to Buy": qty,
            "Action": action
        }
    except:
        return None

# --- WEBSITE INTERFACE ---
st.title("🏹 Nifty 50 Dynamic Swing Scanner")
st.write(f"Scanned at: **{datetime.datetime.now().strftime('%H:%M:%S')} IST**")

# Sidebar
st.sidebar.header("📊 Risk Manager")
user_cap = st.sidebar.number_input("Total Capital (₹)", 100000, step=10000)
user_risk = st.sidebar.slider("Risk per Trade (%)", 0.5, 2.0, 1.0, 0.5)

# Scanner Logic
with st.spinner("Analyzing Nifty 50 Stocks in Parallel..."):
    symbols = get_nifty50_list()
    # Speed Booster: Multi-threading
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda x: process_ticker(x, user_cap, user_risk), symbols))

final_list = [r for r in results if r is not None]

if final_list:
    df_results = pd.DataFrame(final_list)
    
    # Filter Toggle
    only_buy = st.checkbox("🔥 Show only 'BUY' signals", value=True)
    if only_buy:
        df_results = df_results[df_results['Action'] == "✅ BUY"]

    # Display the clean table (NO STYLING = NO ERRORS)
    st.dataframe(df_results, use_container_width=True, hide_index=True)
    
else:
    st.error("Could not fetch data. Please check connection or if market is open.")

st.info("💡 **Entry Rule:** Only enter if the Action is BUY and a 15-minute candle closes above today's high.")
