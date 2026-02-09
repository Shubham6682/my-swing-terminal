import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Institutional Swing Terminal", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15-min sync

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_list():
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        # Create a dictionary of Symbol: Sector
        sector_map = dict(zip(df['Symbol'] + ".NS", df['Sector']))
        return sector_map
    except:
        return {'RELIANCE.NS': 'ENERGY', 'TCS.NS': 'IT', 'SBIN.NS': 'BANKING'}

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI INTERFACE ---
st.title("🏹 Institutional Swing Terminal")

st.sidebar.header("🛡️ Strategy Settings")
cap = st.sidebar.number_input("Total Capital (₹)", 100000, step=10000)
risk_p = st.sidebar.slider("Risk per trade (%)", 0.5, 2.0, 1.0, 0.5)

# Status Indicator
now = datetime.datetime.now()
st.subheader(f"Data Status: {'🟢 LIVE' if (9 <= now.hour < 16 and now.weekday() < 5) else '⚪ MARKET CLOSED (Last Data)'}")

with st.spinner("Downloading Nifty 50 Data in Bulk..."):
    sector_dict = get_nifty50_list()
    tickers = list(sector_dict.keys())
    
    # BULK DOWNLOAD (The Fix)
    # We download 1 year of daily data for all 50 stocks at once
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False)

results = []
for t in tickers:
    try:
        df = data[t].dropna()
        if len(df) < 200: continue
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # FII Sentiment Proxy
        vol_avg = df['Volume'].tail(20).mean()
        curr_vol = df['Volume'].iloc[-1]
        fii_status = "🟢 Accumulating" if (curr_vol > vol_avg and df['Close'].iloc[-1] > df['Open'].iloc[-1]) else "⚪ Neutral"
        
        # Risk Math
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.98, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share > 0:
            qty = int((cap * (risk_p / 100)) // risk_per_share)
            profit_goal = round(qty * (risk_per_share * 2), 2)
            
            action = "✅ BUY" if (cmp > dma_200 and 40 < rsi < 65) else "⏳ WAIT"
            
            results.append({
                "Stock": t.replace(".NS", ""),
                "Sector": sector_dict.get(t, "N/A"),
                "Price": round(cmp, 2),
                "RSI": round(rsi, 1),
                "FII Sentiment": fii_status,
                "Qty": qty,
                "Stop Loss": stop_loss,
                "Action": action,
                "Profit Goal": profit_goal
            })
    except:
        continue

if results:
    full_df = pd.DataFrame(results)
    buy_df = full_df[full_df['Action'] == "✅ BUY"]
    
    # Sidebar Metric
    st.sidebar.markdown("---")
    st.sidebar.metric("💰 Total Profit Potential", f"₹{buy_df['Profit Goal'].sum():,.2f}")
    
    # Main View
    show_all = st.checkbox("Show all Nifty 50 stocks", value=False)
    display_df = full_df if show_all else buy_df
    
    st.dataframe(display_df.drop(columns=['Profit Goal']), use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ Data sync in progress. If this persists, the NSE server might be busy. Refreshing in 15 mins...")

st.info(f"💡 Last Sync: {now.strftime('%H:%M:%S')}")
