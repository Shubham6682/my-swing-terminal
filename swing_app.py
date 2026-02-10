import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- SETTINGS ---
st.set_page_config(page_title="Nifty 50 Total Monitor", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15-min Sync

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_full_list():
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return dict(zip(df['Symbol'] + ".NS", df['Sector']))
    except:
        # Fallback to a hardcoded list if the NSE link is blocked
        tickers = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 
                   'SBIN.NS', 'BHARTIARTL.NS', 'LICI.NS', 'ITC.NS', 'HINDUNILVR.NS']
        return {t: "CORE" for t in tickers}

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI ---
st.title("🏹 Nifty 50 Total Monitor")
st.sidebar.header("⚙️ Risk Settings")
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

now = datetime.datetime.now()
st.write(f"Showing all 50 stocks. Last Sync: **{now.strftime('%H:%M:%S')}**")

with st.spinner("Forcing sync for all 50 Nifty stocks..."):
    sector_map = get_nifty50_full_list()
    tickers = list(sector_map.keys())
    # Period 2y ensures 200 DMA is perfectly accurate
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False)

results = []
for t in tickers:
    # Initialize a row with default values so it ALWAYS shows up
    stock_data = {
        "Stock": t.replace(".NS", ""),
        "Sector": sector_map.get(t, "N/A"),
        "Price": "N/A",
        "RSI": "N/A",
        "Action": "⏳ WAIT",
        "Reason": "Data Missing"
    }
    
    try:
        if t in data.columns.levels[0]:
            df = data[t].dropna()
            if len(df) >= 200:
                cmp = float(df['Close'].iloc[-1])
                dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
                rsi_val = float(calculate_rsi(df['Close']).iloc[-1])
                
                # Risk Logic
                stop_loss = round(float(df['Low'].tail(20).min()) * 0.985, 2)
                risk_per_share = cmp - stop_loss
                
                # CRITERION CHECK
                is_bullish = cmp > dma_200
                is_rsi_safe = 40 < rsi_val < 65
                
                stock_data.update({
                    "Price": round(cmp, 2),
                    "RSI": round(rsi_val, 1),
                    "Action": "✅ BUY" if (is_bullish and is_rsi_safe) else "⏳ WAIT",
                    "Reason": "Trend/RSI Fail" if not (is_bullish and is_rsi_safe) else "Ready"
                })
    except:
        pass
    
    results.append(stock_data)

if results:
    full_df = pd.DataFrame(results)

    # --- ROW HIGHLIGHTER ---
    def color_rows(row):
        if row['Action'] == "✅ BUY":
            return ['background-color: #27ae60; color: white'] * len(row)
        else:
            # All non-BUY stocks turn red as requested
            return ['background-color: #ff4d4d; color: white'] * len(row)

    st.dataframe(
        full_df.style.apply(color_rows, axis=1),
        use_container_width=True, 
        hide_index=True
    )
else:
    st.error("Severe Data Error: Could not generate the table.")
