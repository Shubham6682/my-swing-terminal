import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Pro-Trader Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=10000 if is_open else 60000, key="pro_sync")

# --- 2. THE TICKERS ---
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

# --- 3. STABLE INDEX HEADER ---
st.title("🏹 Pro-Trader Swing Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        if not df_live.empty and not df_hist.empty:
            curr = df_live['Close'].iloc[-1]
            prev = df_hist['Close'].iloc[0]
            change = curr - prev
            pct = (change / prev) * 100
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
    except:
        idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 4. SIDEBAR ---
st.sidebar.header("🛡️ Risk Management")
cap = st.sidebar.number_input("Total Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)

# --- 5. THE PRO ENGINE ---
@st.cache_data(ttl=30)
def get_deep_data():
    # 2 Years for DMA, 6 Months for RS Calculation
    h = yf.download(NIFTY_50 + ["^NSEI"], period="2y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Running Professional Analysis..."):
        h_data, l_data = get_deep_data()

    # Nifty Performance for RS Calculation
    nifty_3m_change = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1

    results = []
    total_prof = 0.0

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            vol_hist = h_data['Volume'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            # 1. Trend & RSI
            dma200 = hc.rolling(200).mean().iloc[-1]
            delta = hc.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

            # 2. Volume Surge (Pro Check)
            avg_vol = vol_hist.tail(20).mean()
            curr_vol = vol_hist.iloc[-1]
            vol_multiplier = curr_vol / avg_vol
            
            # 3. Relative Strength (Pro Check)
            stock_3m_change = (hc.iloc[-1] / hc.iloc[-63]) - 1
            is_outperformer = stock_3m_change > nifty_3m_change

            # FINAL PRO SIGNAL
            # Must be: Above 200DMA AND RSI 40-65 AND Volume > 1.2x Avg AND Beating Nifty
            is_buy = (price > dma200 and 40 < rsi < 65 and vol_multiplier > 1.2 and is_outperformer)
            
            # Risk Math
            stop = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_amt = price - stop
            
            qty, profit = 0, 0.0
            if is_buy and risk_amt > 0:
                qty = int((cap * (risk_p / 100)) // risk_amt)
                profit = round(qty * (risk_amt * 2), 2)
                total_prof += profit

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ PRO BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Qty": qty,
                "Profit": profit,
                "RSI": round(rsi, 1),
                "Vol Multiplier": f"{vol_multiplier:.1f}x",
                "Beats Nifty": "Yes" if is_outperformer else "No"
            })
        except: continue

    if results:
        df = pd.DataFrame(results)
        df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ PRO BUY" else 1)
        df = df.sort_values('s').drop(columns=['s'])
        
        st.sidebar.divider()
        st.sidebar.metric("💰 Pro Potential Profit", f"₹{total_prof:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)

except Exception:
    st.info("Syncing professional data streams...")
