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

# Background sync every 15s during market hours
st_autorefresh(interval=15000 if is_open else 60000, key="pro_sync")

# Initialize Watchlist in Session State
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. INDEX HEADER (STICKY-READY) ---
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
            prev_close = df_hist['Close'].iloc[0]
            change = curr - prev_close
            pct = (change / prev_close) * 100
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({pct:+.2f}%)")
    except:
        idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 3. MANUAL STOCK DEEP-DIVE ---
st.subheader("🎯 Manual Stock Deep-Dive")
lookup_ticker = st.text_input("Analyze any NSE Stock (e.g., ZOMATO, IRFC):", "").upper()

if lookup_ticker:
    full_t = f"{lookup_ticker}.NS"
    try:
        with st.spinner(f"Analyzing {lookup_ticker}..."):
            raw_data = yf.download([full_t, "^NSEI"], period="1y", interval="1d", progress=False)
            h = raw_data['Close'][full_t].dropna()
            n_h = raw_data['Close']['^NSEI'].dropna()
            
            cp = h.iloc[-1]
            dma200 = h.rolling(200).mean().iloc[-1]
            ema20 = h.ewm(span=20, adjust=False).mean().iloc[-1]
            r_high = h.tail(20).max()
            
            # RSI Math
            delta = h.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # RS Check
            is_leader = (h.iloc[-1]/h.iloc[-63]) > (n_h.iloc[-1]/n_h.iloc[-63])

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Price", f"₹{cp:,.2f}")
            m2.metric("RSI", f"{rsi:.1f}")
            m3.metric("EMA (20)", f"₹{ema20:,.2f}")
            m4.metric("Market Leader", "YES" if is_leader else "NO")

            if cp > dma200 and 40 < rsi < 65 and is_leader:
                st.success(f"🚀 {lookup_ticker} satisfies all Pro-Swing criteria!")
            else:
                st.warning("⏳ Signal: WAIT")
                st.info(f"💡 **Entry Recommendation:**")
                if rsi > 65: st.write(f"Wait for pullback to **EMA-20 (₹{ema20:,.2f})**.")
                elif cp < dma200: st.write(f"Wait for trend reversal above **200-DMA (₹{dma200:,.2f})**.")
                else: st.write(f"Buy on breakout above **₹{r_high:,.2f}**.")

            if st.button(f"➕ Add {lookup_ticker} to Watchlist"):
                if lookup_ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(lookup_ticker)
                    st.toast(f"{lookup_ticker} Added!")
    except:
        st.error("Ticker not found.")

st.divider()

# --- 4. SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("📋 My Watchlist")
    if st.session_state.watchlist:
        for stock in st.session_state.watchlist:
            st.write(f"🔹 **{stock}**")
        if st.button("Clear Watchlist"):
            st.session_state.watchlist = []
    else:
        st.write("Watchlist empty.")
    
    st.divider()
    st.header("🛡️ Strategy Control")
    mode = st.sidebar.radio("Rigidity", ["Normal", "Pro"])
    cap = st.sidebar.number_input("Capital", value=50000)
    risk_p = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 5. FULL NIFTY 50 SCANNER ---
st.subheader("📊 Nifty 50 Real-Time Scan")
NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

@st.cache_data(ttl=30)
def get_bulk_data():
    # Syncing Nifty 50 + Benchmark
    h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Scanning Nifty 50..."):
        h_data, l_data = get_bulk_data()
    
    nifty_3m_perf = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
    results = []
    total_prof = 0.0

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            # Indicators
            dma200_v = hc.rolling(200).mean().iloc[-1]
            delta = hc.diff()
            rsi_v = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
            
            # Pro Metrics
            vol_mult = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
            rs_beat = (hc.iloc[-1] / hc.iloc[-63]) - 1 > nifty_3m_perf

            # Decision Logic
            if mode == "Pro":
                is_buy = (price > dma200_v and 40 < rsi_v < 65 and vol_mult > 1.1 and rs_beat)
            else:
                is_buy = (price > dma200_v and 40 < rsi_v < 70)

            # Risk calculation
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
                "Profit": profit,
                "RSI": round(rsi_v, 1),
                "Vol": f"{vol_mult:.1f}x",
                "Leader": "Yes" if rs_beat else "No"
            })
        except: continue

    df = pd.DataFrame(results)
    df['s'] = df['Action'].apply(lambda x: 0 if x == "✅ BUY" else 1)
    df = df.sort_values('s').drop(columns=['s'])
    
    st.sidebar.metric("💰 Potential Profit", f"₹{total_prof:,.2f}")
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)

except Exception as e:
    st.error(f"Syncing... {e}")
