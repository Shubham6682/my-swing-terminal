import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Nifty 50 Full Scanner", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") 

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
st.title("🏹 Nifty 50 Full Institutional Terminal")

st.sidebar.header("🛡️ Risk Settings")
user_cap = st.sidebar.number_input("Capital (₹)", 50000)
user_risk = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# IMPORTANT: I moved the toggle here so you see it immediately
show_all_stocks = st.checkbox("🔍 Show ALL 50 Stocks (Uncheck to see BUY signals only)", value=True)

with st.spinner("Downloading Nifty 50 Data..."):
    sector_map = get_nifty50_list()
    tickers = list(sector_map.keys())
    # Period 2y ensures 200 DMA is perfectly accurate
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False)

results = []
skipped_count = 0

for t in tickers:
    try:
        # Check if ticker exists in download
        if t not in data.columns.levels[0]:
            skipped_count += 1
            continue
            
        df = data[t].dropna()
        if len(df) < 200: 
            skipped_count += 1
            continue
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # Risk Logic
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.985, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share > 0:
            qty = int((user_cap * (user_risk / 100)) // risk_per_share)
            action = "✅ BUY" if (cmp > dma_200 and 40 < rsi < 65) else "⏳ WAIT"
            
            results.append({
                "Stock": t.replace(".NS", ""),
                "Price": round(cmp, 2),
                "RSI": round(rsi, 1),
                "Action": action,
                "Qty": qty,
                "Stop Loss": stop_loss,
                "Target": round(cmp + (risk_per_share * 2), 2),
                "Sector": sector_map.get(t, "N/A")
            })
    except:
        skipped_count += 1
        continue

if results:
    full_df = pd.DataFrame(results)
    
    # Apply Filtering
    display_df = full_df if show_all_stocks else full_df[full_df['Action'] == "✅ BUY"]
    
    st.sidebar.metric("✅ Successfully Scanned", f"{len(full_df)} / 50")
    if skipped_count > 0:
        st.sidebar.warning(f"⚠️ Skipped {skipped_count} stocks (No Data)")

    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.error("Total Data Failure. Please Refresh.")

st.caption(f"Last Updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
