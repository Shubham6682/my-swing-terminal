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

st_autorefresh(interval=15000 if is_open else 60000, key="pro_sync")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

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

# --- 3. MANUAL SEARCH ---
st.subheader("🎯 Manual Stock Deep-Dive")
lookup_ticker = st.text_input("Analyze any NSE Stock (e.g., ZOMATO, HERO):", "").upper()

if lookup_ticker:
    full_t = f"{lookup_ticker}.NS"
    try:
        raw_data = yf.download([full_t, "^NSEI"], period="1y", interval="1d", progress=False)
        h = raw_data['Close'][full_t].dropna()
        n_h = raw_data['Close']['^NSEI'].dropna()
        cp = h.iloc[-1]
        dma200 = h.rolling(200).mean().iloc[-1]
        ema20 = h.ewm(span=20, adjust=False).mean().iloc[-1]
        
        delta = h.diff()
        rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
        is_leader = (h.iloc[-1]/h.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Price", f"₹{cp:,.2f}")
        m2.metric("RSI", f"{rsi:.1f}")
        m3.metric("EMA (20)", f"₹{ema20:,.2f}")
        m4.metric("Market Leader", "YES" if is_leader else "NO")

        if cp > dma200 and 40 < rsi < 65:
            st.success(f"🚀 {lookup_ticker} satisfies Swing Criteria!")
        else:
            st.warning("⏳ Wait for entry.")

        if st.button(f"➕ Add {lookup_ticker} to Watchlist"):
            if lookup_ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(lookup_ticker)
    except:
        st.error("Ticker not found.")

st.divider()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📋 Watchlist")
    for stock in st.session_state.watchlist: st.write(f"🔹 {stock}")
    if st.button("Clear"): st.session_state.watchlist = []
    
    st.divider()
    st.header("🛡️ Strategy Control")
    mode = st.radio("Rigidity", ["Normal", "Pro"])
    cap = st.number_input("Capital", value=50000)
    risk_p = st.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 5. NIFTY 50 SCANNER ---
st.subheader("📊 Nifty 50 Real-Time Scan")
NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

@st.cache_data(ttl=30)
def get_bulk_data():
    h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Scanning..."):
        h_data, l_data = get_bulk_data()
    
    n_perf = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
    results = []

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            dma200_v = hc.rolling(200).mean().iloc[-1]
            
            delta = hc.diff()
            rsi_v = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
            
            vol_m = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
            rs_b = (hc.iloc[-1] / hc.iloc[-63]) - 1 > n_perf

            if mode == "Pro":
                is_buy = (price > dma200_v and 40 < rsi_v < 65 and vol_m > 1.1 and rs_b)
            else:
                is_buy = (price > dma200_v and 40 < rsi_v < 70)

            # --- PROFIT FIX LOGIC ---
            stop_price = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_per_share = price - stop_price
            
            qty = 0
            profit = 0.0
            target_price = 0.0

            if is_buy:
                target_price = round(price + (risk_per_share * 2), 2)
                if risk_per_share > 0:
                    qty = int((cap * (risk_p / 100)) // risk_per_share)
                    if qty == 0 and cap >= price:
                        qty = 1 # Force 1 share if you have enough capital
                    profit = round(qty * (risk_per_share * 2), 2)

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Stop Loss": round(stop_price, 2),
                "Target": target_price,
                "Qty": qty,
                "Profit": profit,
                "RSI": round(rsi_v, 1)
            })
        except: continue

    df = pd.DataFrame(results)
    df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    df = df.sort_values('s').drop(columns=['s'])
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)

except Exception as e:
    st.error(f"Syncing... {e}")
