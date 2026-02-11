import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Elite Swing Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'watchlist' not in st.session_state: st.session_state.watchlist = []

# --- 2. INDEX HEADER ---
st.title("🏹 Elite Momentum Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        if not df_live.empty and not df_hist.empty:
            curr, prev = df_live['Close'].iloc[-1], df_hist['Close'].iloc[0]
            change = curr - prev
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({(change/prev)*100:+.2f}%)")
    except: idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 3. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ View Settings")
    view_mode = st.radio("Display Mode", ["Simple (Focus)", "Pro (Deep-Dive)"], help="Simple mode hides complex technical filters for a cleaner view.")
    
    st.divider()
    st.header("🛡️ Strategy Control")
    cap = st.number_input("Total Capital", value=50000)
    risk_p = st.slider("Risk (%)", 0.5, 5.0, 1.0)

# --- 4. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Scanner", "🚀 Virtual Portfolio", "🎯 Watchlist & Lookup"])

# --- TAB 1: SCANNER ---
with tab1:
    NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

    @st.cache_data(ttl=30)
    def get_market_data():
        h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
        l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
        return h, l

    try:
        h_data, l_data = get_market_data()
        n_perf = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
        results = []

        for t in NIFTY_50:
            try:
                hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
                price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
                
                # Math
                dma200 = hc.rolling(200).mean().iloc[-1]
                delta = hc.diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                adr = ((h_data['High'][t] - h_data['Low'][t]) / h_data['Low'][t]).tail(20).mean() * 100
                tightness = ((hc.tail(5).max() - hc.tail(5).min()) / hc.tail(5).min()) * 100
                vol_m = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
                rs_b = (hc.iloc[-1] / hc.iloc[-63]) - 1 > n_perf

                is_buy = (price > dma200 and 40 < rsi < 65)
                
                stop = float(h_data['Low'][t].tail(20).min()) * 0.985
                risk_ps = price - stop
                qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 0
                if qty == 0 and cap >= price: qty = 1
                
                res = {
                    "Stock": t.replace(".NS", ""),
                    "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                    "Price": round(price, 2),
                    "StopLoss": round(stop, 2),
                    "Profit": round(qty * (risk_ps * 2), 2),
                    "RSI": round(rsi, 1),
                }
                
                # Add Pro Metrics ONLY if in Pro Mode
                if view_mode == "Pro (Deep-Dive)":
                    res["ADR%"] = round(adr, 2)
                    res["Tight%"] = round(tightness, 2)
                    res["Vol"] = f"{vol_m:.1f}x"
                    res["Leader"] = "Yes" if rs_b else "No"
                
                results.append(res)
            except: continue

        df = pd.DataFrame(results)
        df['s'] = df['Action'].apply(lambda x: 0 if "BUY" in x else 1)
        df = df.sort_values('s').drop(columns=['s'])
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)
    except: st.info("Scanning...")

# --- TAB 2: PORTFOLIO ---
with tab2:
    st.subheader("🚀 Practice Trading")
    p_col1, p_col2, p_col3 = st.columns(3)
    with p_col1: vt = st.text_input("Stock:", key="vt").upper()
    with p_col2: vq = st.number_input("Qty:", min_value=1, value=1)
    with p_col3: vp = st.number_input("Entry Price:", min_value=0.1, value=100.0)
    
    if st.button("🚀 Execute Trade"):
        if vt:
            st.session_state.portfolio.append({"Ticker": f"{vt}.NS", "Symbol": vt, "Qty": vq, "BuyPrice": vp})
            st.rerun()

    if st.session_state.portfolio:
        p_res = []
        total_pnl = 0.0
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        c_data = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        for i in st.session_state.portfolio:
            try:
                c_px = c_data[i['Ticker']].dropna().iloc[-1] if len(p_list)>1 else c_data.dropna().iloc[-1]
                pnl = (c_px - i['BuyPrice']) * i['Qty']
                total_pnl += pnl
                p_res.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "Current": round(c_px, 2), "P&L": round(pnl, 2)})
            except: continue
        st.dataframe(pd.DataFrame(p_res), use_container_width=True, hide_index=True)
        st.metric("P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
        if st.button("Clear"): 
            st.session_state.portfolio = []
            st.rerun()

# --- TAB 3: LOOKUP ---
with tab3:
    st.subheader("🔍 Stock Watchlist")
    lu = st.text_input("Search Ticker:").upper()
    if lu:
        try:
            p = yf.Ticker(f"{lu}.NS").history(period="1d")['Close'].iloc[-1]
            st.write(f"**Price:** ₹{p:,.2f}")
            if st.button(f"Add {lu}"):
                if lu not in st.session_state.watchlist: st.session_state.watchlist.append(lu)
        except: st.error("Ticker not found.")
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
    if st.button("Clear Watchlist"): st.session_state.watchlist = []; st.rerun()
