import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Real-Time Nifty 50 Scanner", layout="wide")
# Set to 15 minutes as requested for precision
st_autorefresh(interval=900000, key="datarefresh") 

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_with_sectors():
    """Fetches the official Nifty 50 list directly from NSE archives."""
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        # Create a mapping of Ticker: Sector
        return dict(zip(df['Symbol'] + ".NS", df['Sector']))
    except:
        # Emergency backup list if NSE link fails
        return {'RELIANCE.NS': 'ENERGY', 'TCS.NS': 'IT', 'HDFCBANK.NS': 'FINANCIAL SERVICES', 'ICICIBANK.NS': 'FINANCIAL SERVICES', 'INFY.NS': 'IT', 'SBIN.NS': 'FINANCIAL SERVICES'}

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI LAYOUT ---
st.title("🏹 Real-Time Nifty 50 Institutional Terminal")

st.sidebar.header("🛡️ Strategy Settings")
# Change 1: Removed 1 Lakh restriction (Min set to ₹1,000)
user_cap = st.sidebar.number_input("Total Capital (₹)", value=50000, min_value=1000, step=5000)
user_risk = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, 1.0, 0.5)

# Status Indicator
now = datetime.datetime.now()
st.subheader(f"Status: {'🟢 LIVE MARKET' if (9 <= now.hour < 16 and now.weekday() < 5) else '⚪ MARKET CLOSED (Showing Last Available Price)'}")

with st.spinner("Fetching Real-Time Nifty 50 Data..."):
    sector_map = get_nifty50_with_sectors()
    tickers = list(sector_map.keys())
    
    # Change 2 & 3: Bulk download for speed, but processing ALL 50
    # Period 1y is needed to calculate the 200 DMA precisely
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False)

results = []
for t in tickers:
    try:
        df = data[t].dropna()
        if df.empty: continue
        
        # Real-Time Price Logic: Using the very last tick from the download
        cmp = float(df['Close'].iloc[-1])
        
        # Parameters for Precision
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # FII Sentiment Proxy (Volume spikes + Price Action)
        vol_avg = df['Volume'].tail(20).mean()
        curr_vol = df['Volume'].iloc[-1]
        fii_status = "🟢 Accumulating" if (curr_vol > vol_avg and cmp > df['Open'].iloc[-1]) else "⚪ Neutral"
        
        # Swing Risk Math
        # Stop Loss = 20-day low with a 1.5% buffer
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.985, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share > 0:
            qty = int((user_cap * (user_risk / 100)) // risk_per_share)
            profit_goal = round(qty * (risk_per_share * 2), 2)
            
            # Action logic: Trend + RSI Stability
            action = "✅ BUY" if (cmp > dma_200 and 40 < rsi < 65) else "⏳ WAIT"
            
            results.append({
                "Stock": t.replace(".NS", ""),
                "Sector": sector_map.get(t, "N/A"),
                "Price": round(cmp, 2),
                "RSI": round(rsi, 1),
                "FII Accumulation": fii_status,
                "Shares to Buy": qty,
                "Stop Loss": stop_loss,
                "Target (1:2)": round(cmp + (risk_per_share * 2), 2),
                "Action": action,
                "Potential Profit": profit_goal
            })
    except:
        continue

# Display logic
if results:
    full_df = pd.DataFrame(results)
    buy_df = full_df[full_df['Action'] == "✅ BUY"]
    
    # Sidebar Metric
    st.sidebar.markdown("---")
    st.sidebar.metric("💰 Buy Signal Profit Potential", f"₹{buy_df['Potential Profit'].sum():,.2f}")
    st.sidebar.write(f"Total Stocks Scanned: {len(full_df)}")

    # Main Table
    show_all = st.checkbox("Show all 50 stocks (Uncheck to see BUY signals only)", value=True)
    display_df = full_df if show_all else buy_df
    
    # Display table without the Profit column for cleaner UI
    st.dataframe(display_df.drop(columns=['Potential Profit']), use_container_width=True, hide_index=True)
else:
    st.warning("🔄 Connecting to NSE servers... If no data appears, please refresh the page.")

st.info(f"💡 Real-time data from yfinance. Last Updated: {now.strftime('%H:%M:%S')}")
