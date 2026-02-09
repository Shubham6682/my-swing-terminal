import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from concurrent.futures import ThreadPoolExecutor
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Flash Swing Scanner", layout="wide")
st_autorefresh(interval=300000, key="datarefresh") # 5 min refresh

# --- DATA FETCHING (CACHED) ---
@st.cache_data(ttl=3600)
def get_nifty50_list():
    """Fetches the Nifty 50 ticker list from NSE."""
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return [s + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'SBIN.NS']

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- THE ENGINE (PARALLEL PROCESSING) ---
def process_ticker(ticker, capital, risk_pct):
    try:
        # We only need 1y data for 200 DMA
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200: return None
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # Risk Logic
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.98, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share <= 0: return None
        
        # Calculator
        risk_amount = capital * (risk_pct / 100)
        qty = int(risk_amount // risk_per_share)
        target = round(cmp + (risk_per_share * 2), 2)
        
        # Action Logic
        is_bullish = cmp > dma_200
        action = "✅ BUY ZONE" if (is_bullish and 40 < rsi < 65) else "⏳ WAIT"
        
        return {
            "Stock": ticker.replace(".NS", ""),
            "Price": round(cmp, 2),
            "200 DMA": round(dma_200, 2),
            "RSI": round(rsi, 1),
            "Stop Loss": stop_loss,
            "Target": target,
            "Qty": qty,
            "Action": action
        }
    except:
        return None

# --- UI ---
st.title("⚡ Flash Swing Terminal (Nifty 50)")
st.sidebar.header("⚙️ Strategy Settings")
cap = st.sidebar.number_input("Capital (₹)", 100000)
risk = st.sidebar.slider("Risk per trade (%)", 0.5, 2.0, 1.0)

if st.sidebar.button("Force Refresh Data"):
    st.cache_data.clear()

with st.spinner(f"Scanning Nifty 50 in parallel..."):
    tickers = get_nifty50_list()
    
    # This is the speed booster: ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda x: process_ticker(x, cap, risk), tickers))

# Filter out None results
final_data = [r for r in results if r is not None]

if final_data:
    df = pd.DataFrame(final_data)
    
    # Show only Buy Zone by default for clarity
    only_buy = st.checkbox("Show only Buy Zone stocks", value=True)
    if only_buy:
        df = df[df['Action'] == "✅ BUY ZONE"]

    st.dataframe(
        df.style.background_gradient(subset=['RSI'], cmap='RdYlGn_r'),
        use_container_width=True,
        hide_index=True
    )
else:
    st.error("Market data fetch failed. Check your internet or wait for market open.")

st.caption(f"Last scanned at: {datetime.datetime.now().strftime('%H:%M:%S')}")
