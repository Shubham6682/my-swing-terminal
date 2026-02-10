import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. SETTINGS & REFRESH ---
st.set_page_config(page_title="Nifty 50 Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM IST
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

# Silent background refresh: 10 seconds
st_autorefresh(interval=10000 if is_open else 60000, key="silent_sync")

# --- 2. MASTER TICKER LIST ---
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

# --- 3. LIVE INDEX DASHBOARD (TOP SECTION) ---
# We use a standard layout here to prevent the "White Screen" error
st.title("🏹 Nifty 50 Precision Terminal")

indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        # Separate calls ensure Sensex doesn't lag
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        
        if not df_live.empty and not df_hist.empty:
            curr = df_live['Close'].iloc[-1]
            prev_close = df_hist['Close'].iloc[0]
            change = curr - prev_close
            pct = (change / prev_close) * 100
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
        else:
            idx_cols[i].metric(name, "Fetching...")
    except:
        idx_cols[i].metric(name, "N/A")

status_icon = "🟢 OPEN" if is_open else "⚪ CLOSED"
idx_cols[-1].write(f"**{status_icon}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")

st.divider()

# --- 4. SIDEBAR SETTINGS ---
st.sidebar.header("🛡️ Trade Settings")
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 5. DATA SCANNER ---
@st.cache_data(ttl=30)
def get_live_data():
    h = yf.download(NIFTY_50, period="2y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Analyzing Market Signals..."):
        h_data, l_data = get_live_data()

    results = []
    total_prof = 0.0

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            # Indicator Math
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
        # Pin BUY signals to top
        df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
        df = df.sort_values('s').drop(columns=['s'])
        
        st.sidebar.divider()
        st.sidebar.metric("💰 Potential Profit", f"₹{total_prof:,.2f}")
        
        # DISPLAY: We use height to make the table scrollable while keeping indices visible above it
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)

except Exception:
    st.info("Market stream active...")
