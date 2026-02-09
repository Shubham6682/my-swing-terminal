import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Custom Institutional Terminal", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15-min Precision Window

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_with_sectors():
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

# --- UI LAYOUT ---
st.title("🏹 Nifty 50 Custom Institutional Terminal")

# SIDEBAR: STRATEGY & FILTERS
st.sidebar.header("🛡️ Strategy Settings")
user_cap = st.sidebar.number_input("Total Capital (₹)", value=50000, min_value=100, step=5000)
user_risk = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, 1.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filter Options")
# Filter 1: Main Buy Signal
only_buy = st.sidebar.checkbox("Show ONLY '✅ BUY' signals", value=True)
# Filter 2: FII Sentiment (Now Optional)
only_fii = st.sidebar.checkbox("Show ONLY 'Accumulating' stocks", value=False)

# Status Indicator
now = datetime.datetime.now()
st.subheader(f"Status: {'🟢 LIVE' if (9 <= now.hour < 16 and now.weekday() < 5) else '⚪ MARKET CLOSED (Showing Last Data)'}")

with st.spinner("Processing Nifty 50 Precision Data..."):
    sector_map = get_nifty50_with_sectors()
    tickers = list(sector_map.keys())
    
    # Bulk download for zero lag
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False)

results = []
for t in tickers:
    try:
        df = data[t].dropna()
        if df.empty or len(df) < 200: continue
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # FII Sentiment Proxy (Volume + Price Action)
        vol_avg = df['Volume'].tail(20).mean()
        curr_vol = df['Volume'].iloc[-1]
        is_accumulating = (curr_vol > vol_avg and cmp > df['Open'].iloc[-1])
        fii_status = "🟢 Accumulating" if is_accumulating else "⚪ Neutral"
        
        # Precision Risk Math
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.985, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share > 0:
            qty = int((user_cap * (user_risk / 100)) // risk_per_share)
            profit_goal = round(qty * (risk_per_share * 2), 2)
            
            # Action logic: Above 200 DMA + RSI in "Safe Zone"
            action = "✅ BUY" if (cmp > dma_200 and 40 < rsi < 65) else "⏳ WAIT"
            
            results.append({
                "Stock": t.replace(".NS", ""),
                "Sector": sector_map.get(t, "N/A"),
                "Price": round(cmp, 2),
                "RSI": round(rsi, 1),
                "FII Sentiment": fii_status,
                "Qty": qty,
                "Stop Loss": stop_loss,
                "Target (1:2)": round(cmp + (risk_per_share * 2), 2),
                "Action": action,
                "Potential Profit": profit_goal
            })
    except:
        continue

# --- DISPLAY LOGIC ---
if results:
    full_df = pd.DataFrame(results)
    
    # Apply Filters based on Sidebar Toggles
    filtered_df = full_df.copy()
    if only_buy:
        filtered_df = filtered_df[filtered_df['Action'] == "✅ BUY"]
    if only_fii:
        filtered_df = filtered_df[filtered_df['FII Sentiment'] == "🟢 Accumulating"]

    # Sidebar Potential Profit Metric
    st.sidebar.markdown("---")
    current_profit_potential = filtered_df['Potential Profit'].sum()
    st.sidebar.metric("💰 Signal Profit Potential", f"₹{current_profit_potential:,.2f}")
    st.sidebar.caption(f"Based on {len(filtered_df)} visible signals.")

    # Show Table
    st.dataframe(filtered_df.drop(columns=['Potential Profit']), use_container_width=True, hide_index=True)
else:
    st.warning("🔄 Data sync in progress. Please wait a moment...")

st.info(f"💡 Real-time precision data. Last Updated: {now.strftime('%H:%M:%S')}")
