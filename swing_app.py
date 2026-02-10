import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 Signal Monitor", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15-min Sync

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_list():
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return dict(zip(df['Symbol'] + ".NS", df['Sector']))
    except:
        return {'RELIANCE.NS': 'ENERGY', 'TCS.NS': 'IT', 'SBIN.NS': 'BANKING'}

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI ---
st.title("🏹 Nifty 50 Institutional Terminal")

st.sidebar.header("🛡️ Strategy Settings")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000, min_value=100)
risk_p = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, 1.0, 0.5)

# Status
now = datetime.datetime.now()
st.subheader(f"Status: {'🟢 LIVE' if (9 <= now.hour < 16 and now.weekday() < 5) else '⚪ MARKET CLOSED'}")

with st.spinner("Analyzing all 50 stocks..."):
    sector_map = get_nifty50_list()
    tickers = list(sector_map.keys())
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False)

results = []
for t in tickers:
    try:
        df = data[t].dropna()
        if len(df) < 200: continue
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # Risk Math
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.985, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share > 0:
            qty = int((cap * (risk_p / 100)) // risk_per_share)
            # FII Check
            fii = "🟢 Accumulating" if (df['Volume'].iloc[-1] > df['Volume'].tail(20).mean() and cmp > df['Open'].iloc[-1]) else "⚪ Neutral"
            
            # CRITERION: Price > 200 DMA AND RSI between 40-65
            is_valid = (cmp > dma_200 and 40 < rsi < 65)
            action = "✅ BUY" if is_valid else "⏳ WAIT"
            
            results.append({
                "Stock": t.replace(".NS", ""),
                "Price": round(cmp, 2),
                "200 DMA": round(dma_200, 2),
                "RSI": round(
