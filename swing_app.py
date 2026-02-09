import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
ST_CAPITAL = 100000  # Default Capital
ST_RISK_PCT = 1      # 1% Risk per trade

# Set page config
st.set_page_config(page_title="Nifty 50 Swing Scanner", layout="wide")
st_autorefresh(interval=300000, key="datarefresh")

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_symbols():
    try:
        url = 'https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return [s + ".NS" for s in df['Symbol'].tolist()]
    except:
        # Fallback list if NSE link is down
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'HINDALCO.NS']

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, capital, risk_pct):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 200: return None
        
        df['200_DMA'] = df['Close'].rolling(window=200).mean()
        df['RSI'] = calculate_rsi(df)
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['200_DMA'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        
        # --- SWING LOGIC ---
        is_bullish = cmp > dma_200
        rsi_status = "HOT" if rsi > 70 else ("COLD" if rsi < 40 else "SAFE")
        
        # --- RISK CALCULATOR ---
        # Stop Loss at recent 20-day low (Safety Floor)
        stop_loss = round(float(df['Close'].tail(20).min()) * 0.98, 2)
        risk_per_share = cmp - stop_loss
        
        if risk_per_share <= 0: return None # Protection against math errors
        
        # How much money can we lose? (1% of 1,00,000 = 1,000)
        total_risk_allowed = capital * (risk_pct / 100)
        qty = int(total_risk_allowed // risk_per_share)
        
        target = round(cmp + (risk_per_share * 2), 2)
        
        action = "✅ BUY ZONE" if (is_bullish and rsi_status == "SAFE") else "⏳ WAIT"

        return {
            "Stock": ticker.replace(".NS", ""),
            "CMP": round(cmp, 2),
            "200 DMA": round(dma_200, 2),
            "RSI": round(rsi, 2),
            "Status": rsi_status,
            "Stop Loss": stop_loss,
            "Target (1:2)": target,
            "Shares to Buy": qty,
            "Action": action
        }
    except:
        return None

# --- UI INTERFACE ---
st.sidebar.title("💰 Risk Manager")
user_capital = st.sidebar.number_input("Your Total Trading Capital (₹)", value=100000, step=5000)
user_risk = st.sidebar.slider("Risk Per Trade (%)", 0.5, 3.0, 1.0, 0.5)

st.title("🏹 Nifty 50 Dynamic Swing Scanner")
st.write(f"Scanning Nifty 50 stocks for **Price > 200 DMA** and **RSI < 70**.")

if st.button("Manual Scan Now"):
    st.cache_data.clear()

with st.spinner('Analyzing 50 stocks...'):
    symbols = get_nifty50_symbols()
    results = []
    # Using a progress bar for UX
    progress_bar = st.progress(0)
    for i, symbol in enumerate(symbols):
        res = analyze_stock(symbol, user_capital, user_risk)
        if res: results.append(res)
        progress_bar.progress((i + 1) / len(symbols))

if results:
    final_df = pd.DataFrame(results)
    
    # Custom Styling
    def style_action(val):
        color = '#27ae60' if "BUY" in val else '#95a5a6'
        return f'background-color: {color}; color: white; font-weight: bold'

    # Filtered View (Show only Buy Zone by default)
    show_all = st.checkbox("Show all Nifty 50 stocks (including WAIT)")
    if not show_all:
        final_df = final_df[final_df['Action'] == "✅ BUY ZONE"]

    st.dataframe(
        final_df.style.map(style_action, subset=['Action']),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No high-conviction trades found right now. Check back in 5 mins.")
