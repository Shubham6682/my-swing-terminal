import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Status Logic
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

# Silent background refresh: 10s for indices/stocks balance
st_autorefresh(interval=10000 if is_open else 60000, key="silent_sync")

# --- 2. PERMANENT SIDEBAR INDICES (STICKY) ---
with st.sidebar:
    st.header("🌍 Market Indices")
    indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    
    for name, ticker in indices.items():
        try:
            t_obj = yf.Ticker(ticker)
            # Fetch minimal data for maximum speed
            df_live = t_obj.history(period="1d", interval="1m")
            df_hist = t_obj.history(period="2d")
            
            if not df_live.empty and not df_hist.empty:
                curr = df_live['Close'].iloc[-1]
                prev = df_hist['Close'].iloc[0]
                change = curr - prev
                pct = (change / prev) * 100
                st.metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            else:
                st.metric(name, "N/A")
        except:
            st.metric(name, "Offline")
    
    st.divider()
    status_txt = "🟢 MARKET OPEN" if is_open else "⚪ MARKET CLOSED"
    st.write(f"**{status_txt}**")
    st.write(f"IST: {now.strftime('%H:%M:%S')}")
    st.divider()
    
    # Trade Settings moved below indices
    st.header("🛡️ Trade Settings")
    cap = st.number_input("Capital (₹)", value=50000)
    risk_p = st.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 3. MAIN TERMINAL UI ---
st.title("🏹 Nifty 50 Precision Terminal")

# --- 4. DATA SCANNER ---
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

@st.cache_data(ttl=30)
def get_market_data():
    h = yf.download(NIFTY_50, period="2y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Analyzing Signals..."):
        h_data, l_data = get_market_data()

    results = []
    total_prof = 0.0

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            # Technicals
            dma200 = float(hc.rolling(200).mean().iloc[-1])
            delta = hc.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

            is_buy = (price > dma200 and 40 < rsi < 65)
            stop = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_amt = price - stop
            
            qty, profit = 0, 0.0
            if is_buy and risk_amt > 0:
                qty = int((cap * (risk_p / 100)) // risk_amt)
                profit = round(qty * (risk_amt * 2), 2)
                total_prof += profit

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Qty": qty,
                "Target": round(price + (risk_amt * 2), 2) if is_buy else 0.0,
                "Profit": profit,
                "RSI": round(rsi, 1)
            })
        except: continue

    if results:
        df = pd.DataFrame(results)
        # Sorting: Green signals up
        df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
        df = df.sort_values('s').drop(columns=['s'])
        
        st.sidebar.metric("💰 Total Potential Profit", f"₹{total_prof:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.info("Market stream syncing...")
