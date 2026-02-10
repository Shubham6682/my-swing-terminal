import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 Full Monitor", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15-minute sync

# --- FULL NIFTY 50 TICKER LIST ---
NIFTY_50_TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI INTERFACE ---
st.title("🏹 Nifty 50 Total Signal Monitor")
st.sidebar.header("🛡️ Risk Settings")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, 1.0)

# Status and Time
now = datetime.datetime.now()
st.subheader(f"Last Sync: {now.strftime('%H:%M:%S')} | Refresh: 15 Mins")

with st.spinner("Downloading data for all 50 stocks..."):
    # Bulk download with threads for reliability
    data = yf.download(NIFTY_50_TICKERS, period="2y", interval="1d", group_by='ticker', progress=False, threads=True)

results = []

for t in NIFTY_50_TICKERS:
    # Default values to ensure the row is ALWAYS created
    row = {
        "Stock": t.replace(".NS", ""),
        "Price": "N/A",
        "200 DMA": "N/A",
        "RSI": "N/A",
        "Action": "⏳ WAIT",
        "Reason": "Data Unstable"
    }
    
    try:
        if t in data.columns.levels[0]:
            df = data[t].dropna()
            if len(df) >= 200:
                cmp = float(df['Close'].iloc[-1])
                dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
                rsi_val = float(calculate_rsi(df['Close']).iloc[-1])
                
                # Precision Risk Math
                stop_loss = float(df['Low'].tail(20).min()) * 0.985
                risk_per_share = cmp - stop_loss
                
                # CRITERIA: Above 200 DMA and RSI between 40-65
                is_bullish = cmp > dma_200
                is_rsi_safe = 40 < rsi_val < 65
                
                if is_bullish and is_rsi_safe:
                    qty = int((cap * (risk_p / 100)) // risk_per_share) if risk_per_share > 0 else 0
                    row.update({
                        "Price": round(cmp, 2),
                        "200 DMA": round(dma_200, 2),
                        "RSI": round(rsi_val, 1),
                        "Action": "✅ BUY",
                        "Reason": f"Qty: {qty}"
                    })
                else:
                    fail_reason = ""
                    if not is_bullish: fail_reason += "Below 200DMA "
                    if not is_rsi_safe: fail_reason += "RSI Out of Range"
                    
                    row.update({
                        "Price": round(cmp, 2),
                        "200 DMA": round(dma_200, 2),
                        "RSI": round(rsi_val, 1),
                        "Action": "⏳ WAIT",
                        "Reason": fail_reason.strip()
                    })
    except Exception:
        pass
    
    results.append(row)

# --- DISPLAY ENGINE ---
if results:
    full_df = pd.DataFrame(results)

    # CSS for Row Highlighting
    def style_rows(row):
        if row['Action'] == "✅ BUY":
            return ['background-color: #27ae60; color: white'] * len(row)
        else:
            return ['background-color: #ff4d4d; color: white'] * len(row)

    # Force sort so BUY signals are at the top
    full_df['Sort_Order'] = full_df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    full_df = full_df.sort_values('Sort_Order').drop('Sort_Order', axis=1)

    st.dataframe(
        full_df.style.apply(style_rows, axis=1),
        use_container_width=True, 
        hide_index=True
    )
else:
    st.error("Terminal Sync Failed. Please check the logs.")

st.info("💡 Only Green rows fulfill the Swing criteria (Price > 200 DMA & RSI 40-65).")
