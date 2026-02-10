import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Pro Swing Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=10000 if is_open else 60000, key="pro_sync")

# --- 2. INDEX HEADER ---
st.title("🏹 Pro Swing Terminal")
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

# --- 3. MANUAL STOCK DEEP-DIVE ---
st.subheader("🎯 Manual Stock Deep-Dive")
lookup_ticker = st.text_input("Enter NSE Stock Ticker (e.g., ZOMATO, HAL, KAYNES):", "").upper()

if lookup_ticker:
    try:
        full_t = f"{lookup_ticker}.NS"
        with st.spinner(f"Analyzing {lookup_ticker}..."):
            # Fetch data for deep dive
            raw_h = yf.download([full_t, "^NSEI"], period="1y", interval="1d", progress=False)
            h = raw_h['Close'][full_t].dropna()
            nifty_h = raw_h['Close']['^NSEI'].dropna()
            
            # Math
            cp = h.iloc[-1]
            dma200 = h.rolling(200).mean().iloc[-1]
            
            # RSI
            delta = h.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # RS (Beating Nifty)
            stock_3m = (h.iloc[-1] / h.iloc[-63]) - 1
            nifty_3m = (nifty_h.iloc[-1] / nifty_h.iloc[-63]) - 1
            beats = stock_3m > nifty_3m
            
            # Volume
            vol_h = raw_h['Volume'][full_t].dropna()
            v_mult = vol_h.iloc[-1] / vol_h.tail(20).mean()

            # Display Analysis
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Current Price", f"₹{cp:,.2f}")
            m1.write(f"Trend: {'✅ ABOVE 200DMA' if cp > dma200 else '❌ BELOW 200DMA'}")
            
            m2.metric("RSI (14)", f"{rsi:.1f}")
            m2.write(f"Momentum: {'✅ HEALTHY' if 40 < rsi < 65 else '❌ WEAK/OVERBOUGHT'}")
            
            m3.metric("Volume Multiplier", f"{v_mult:.1f}x")
            m3.write(f"Institutions: {'✅ BUYING' if v_mult > 1.1 else '❌ NEUTRAL'}")
            
            m4.metric("Vs Nifty (3M)", f"{stock_3m*100:+.1f}%")
            m4.write(f"Leader: {'✅ YES' if beats else '❌ LAGGARD'}")
            
            if cp > dma200 and 40 < rsi < 65 and v_mult > 1.1 and beats:
                st.success(f"🚀 {lookup_ticker} satisfies ALL Pro-Swing criteria!")
            else:
                st.warning(f"⏳ {lookup_ticker} is not quite ready for a Pro-Entry yet.")
    except:
        st.error("Invalid Ticker. Please use standard NSE names.")

st.divider()

# --- 4. SIDEBAR & MAIN SCANNER ---
st.sidebar.header("🛡️ Strategy Control")
mode = st.sidebar.radio("Scanner Rigidity", ["Normal (Aggressive)", "Pro (Conservative)"])
cap = st.sidebar.number_input("Capital (₹)", value=50000)
risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# Main Scanner logic (as before)
NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

@st.cache_data(ttl=30)
def get_bulk_data():
    h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Scanning Nifty 50..."):
        h_data, l_data = get_bulk_data()
    
    nifty_3m_val = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
    results = []
    
    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            dma200_v = hc.rolling(200).mean().iloc[-1]
            rsi_v = 100 - (100 / (1 + (hc.diff().where(hc.diff() > 0, 0).rolling(14).mean() / -hc.diff().where(hc.diff() < 0, 0).rolling(14).mean()))).iloc[-1]
            vol_m = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
            rs_b = (hc.iloc[-1] / hc.iloc[-63]) - 1 > nifty_3m_val

            if mode == "Pro (Conservative)":
                is_buy = (price > dma200_v and 40 < rsi_v < 65 and vol_m > 1.1 and rs_b)
            else:
                is_buy = (price > dma200_v and 40 < rsi_v < 70)

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "RSI": round(rsi_v, 1),
                "Vol": f"{vol_m:.1f}x",
                "Beats Nifty": "Yes" if rs_b else "No"
            })
        except: continue

    df = pd.DataFrame(results)
    df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    df = df.sort_values('s').drop(columns=['s'])
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)

except Exception as e:
    st.error(f"Syncing... {e}")
