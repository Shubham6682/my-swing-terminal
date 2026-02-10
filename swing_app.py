import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Nifty 50 Profit Terminal", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 1-min Sync

# --- MASTER TICKER LIST ---
NIFTY_50 = [
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

# --- UI ---
st.title("🏹 Nifty 50 Precision Profit Terminal")

# Sidebar - Settings
st.sidebar.header("🛡️ Risk & Capital")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000, step=5000)
risk_p = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, 0.5)

# Clock Logic
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.datetime.now(ist)
st.markdown(f"**Live Sync:** `{now_ist.strftime('%H:%M:%S')}` IST")

with st.spinner("Downloading real-time market data..."):
    # Dual-Sync: 2y for Trend, 1d for Price
    hist_data = yf.download(NIFTY_50, period="2y", interval="1d", group_by='ticker', progress=False)
    live_data = yf.download(NIFTY_50, period="1d", interval="1m", group_by='ticker', progress=False)

results = []
total_profit_pool = 0.0

for t in NIFTY_50:
    # Initialize basic row
    row = {"Stock": t.replace(".NS", ""), "Price": 0.0, "Action": "⏳ WAIT", "Qty": 0, "Profit Potential": 0.0, "RSI": 0.0}
    
    try:
        # Check if ticker exists in both downloaded sets
        if t in hist_data.columns.levels[0] and t in live_data.columns.levels[0]:
            df_h = hist_data[t].dropna()
            df_l = live_data[t].dropna()
            
            if not df_h.empty and not df_l.empty:
                price = float(df_l['Close'].iloc[-1])
                dma_200 = float(df_h['Close'].rolling(window=200).mean().iloc[-1])
                rsi_val = float(calculate_rsi(df_h['Close']).iloc[-1])
                
                # Risk Logic: Using 20-day low with 1.5% buffer
                recent_low = float(df_h['Low'].tail(20).min())
                stop_loss = recent_low * 0.985
                risk_per_share = price - stop_loss
                
                # FII Volume Accumulation Check
                vol_avg = df_h['Volume'].tail(20).mean()
                curr_vol = df_l['Volume'].sum()
                fii = "🟢 Accumulating" if (curr_vol > vol_avg and price > df_l['Open'].iloc[0]) else "⚪ Neutral"
                
                # Strategy: Trend > 200 DMA and RSI between 40-65
                is_valid = (price > dma_200 and 40 < rsi_val < 65)
                
                if is_valid and risk_per_share > 0:
                    qty = int((cap * (risk_p / 100)) // risk_per_share)
                    reward = risk_per_share * 2
                    profit = round(qty * reward, 2)
                    
                    total_profit_pool += profit
                    row.update({
                        "Price": round(price, 2),
                        "Action": "✅ BUY",
                        "Qty": qty,
                        "Target": round(price + reward, 2),
                        "Profit Potential": profit,
                        "RSI": round(rsi_val, 1),
                        "FII": fii
                    })
                else:
                    row.update({
                        "Price": round(price, 2),
                        "Action": "⏳ WAIT",
                        "RSI": round(rsi_val, 1),
                        "FII": fii
                    })
    except Exception:
        pass
    results.append(row)

# --- DISPLAY ENGINE ---
if results:
    # Sidebar Metrics
    st.sidebar.markdown("---")
    st.sidebar.metric("💰 Total Potential Profit", f"₹{total_profit_pool:,.2f}")
    st.sidebar.write(f"Risking **₹{cap * (risk_p/100):.2f}** per trade")

    df = pd.DataFrame(results)
    
    # Sorting: Push Green setups to the top
    df['Sort'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    df = df.sort_values('Sort').drop('Sort', axis=1)

    # Styling for Visual Impact
    def style_rows(row):
        color = '#27ae60' if row['Action'] == "✅ BUY" else '#ff4d4d'
        return [f'background-color: {color}; color: white'] * len(row)

    st.dataframe(
        df.style.apply(style_rows, axis=1), 
        use_container_width=True, 
        hide_index=True
    )
else:
    st.error("Data refresh failed. Check server logs.")
