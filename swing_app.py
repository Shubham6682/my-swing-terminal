import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz
import os
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Auto-Bot Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Market Hours: 9:15 AM - 3:30 PM IST (Refresh every 30s)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=30000 if is_open else 60000, key="auto_bot_sync")

# --- 2. PERSISTENCE LAYER ---
if 'portfolio' not in st.session_state:
    if os.path.exists(PORTFOLIO_FILE):
        st.session_state.portfolio = pd.read_csv(PORTFOLIO_FILE).to_dict('records')
    else: st.session_state.portfolio = []

if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 
if 'watchlist' not in st.session_state: st.session_state.watchlist = []
if 'triggers' not in st.session_state: st.session_state.triggers = {}

# --- 3. HELPER MATH FUNCTIONS ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_width(series, period=20):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return ((sma + (2 * std)) - (sma - (2 * std))) / sma

# --- 4. HEADER ---
st.title("🏹 Elite Auto-Bot Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df_i = yf.Ticker(ticker).history(period="5d")
        if not df_i.empty:
            c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
            idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
    except: pass
idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 5. SIDEBAR (BOT CONTROL) ---
with st.sidebar:
    st.header("🧠 Strategy Engine")
    strategy_mode = st.radio("Select Intelligence Mode:", 
                             ["🛡️ Pro Sentinel (Swing)", "🎯 Elite Sniper (Extreme)"])
    
    st.divider()
    st.header("🤖 Auto-Trading Bot")
    auto_trade_on = st.checkbox("Activate Paper Trading Bot", value=False, help="Automatically adds CONFIRMED stocks to portfolio.")
    risk_p = st.slider("Bot Risk per Trade (%)", 0.5, 3.0, 1.5)
    
    st.divider()
    st.header("🔔 Bot Activity Feed")
    if not st.session_state.alert_log: st.info("Bot is idle...")
    else:
        for s, ts in sorted(st.session_state.alert_log.items(), key=lambda x: x[1], reverse=True)[:5]:
            st.success(f"🚀 {s}: {int((time.time()-ts)/60)}m ago")

# --- 6. DATA ENGINE ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def fetch_data():
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", progress=False)['Close']
    l = yf.download(TICKERS_NS, period="1d", interval="1m", progress=False)['Close']
    v = yf.download(TICKERS_NS, period="1mo", progress=False)['Volume']
    if l.empty or l.dropna(how='all').empty: l = h.tail(1)
    return h, l, v

# --- 7. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Hunter", "🚀 Virtual Portfolio", "🎯 Watchlist"])

with tab1:
    try:
        h_data, l_data, v_data = fetch_data()
        results = []
        nifty_perf = h_data['^NSEI'].iloc[-1] / h_data['^NSEI'].iloc[-63]

        for t in TICKERS_NS:
            try:
                hist = h_data[t].dropna()
                ltp = float(l_data[t].dropna().iloc[-1])
                prev_close = float(hist.iloc[-2])
                day_change = ((ltp - prev_close) / prev_close) * 100
                
                status, trigger, note = "⏳ WAIT", 0.0, ""
                
                # --- STRATEGY 1: PRO SENTINEL ---
                if strategy_mode == "🛡️ Pro Sentinel (Swing)":
                    dma200 = hist.rolling(200).mean().iloc[-1]
                    high_5d = hist.tail(6).iloc[:-1].max()
                    trigger = round(high_5d * 1.002, 2)
                    is_leader = (hist.iloc[-1]/hist.iloc[-63]) > nifty_perf
                    
                    if ltp >= trigger and ltp > dma200 and is_leader: status = "🎯 CONFIRMED"
                    
                    gap = ((ltp - trigger)/trigger)*100
                    note = "🟢 SAFE ZONE"
                    if day_change < -1.5: note = "🔴 WEAK"
                    elif not is_leader: note = "🟡 LAGGARD"
                    elif ltp < dma200: note = "🔴 DOWN TREND"
                    elif gap > 1.8: note = "🟡 CHASING"
                    
                    results.append({"Stock": t.replace(".NS",""), "Status": status, "LTP": round(ltp, 2), "Day %": f"{day_change:+.2f}%", "Risk Info": note, "Entry": trigger, "Gap %": f"{gap:+.2f}%"})

                # --- STRATEGY 2: ELITE SNIPER ---
                else:
                    rsi = calculate_rsi(hist).iloc[-1]
                    bb_width = calculate_bollinger_width(hist).iloc[-1]
                    vol_spike = v_data[t].iloc[-1] > (v_data[t].rolling(20).mean().iloc[-1] * 1.5)
                    
                    status = "😴 SLEEPING"
                    if bb_width < 0.10: status = "👀 COILING (Squeeze)"
                    elif vol_spike and day_change > 1.5 and rsi > 55: 
                        status = "🚀 BREAKOUT"
                        trigger = ltp
                    
                    if status != "😴 SLEEPING":
                        results.append({"Stock": t.replace(".NS",""), "Status": status, "LTP": round(ltp, 2), "Day %": f"{day_change:+.2f}%", "RSI": round(rsi, 1), "Vol Spike": "🔥 YES" if vol_spike else "No", "Squeeze": "✅ YES" if bb_width < 0.10 else "No"})

                # --- 🤖 AUTO-TRADING BOT LOGIC ---
                if auto_trade_on and (status == "🎯 CONFIRMED" or status == "🚀 BREAKOUT"):
                    stock_sym = t.replace(".NS","")
                    current_holdings = [p['Symbol'] for p in st.session_state.portfolio]
                    
                    if stock_sym not in current_holdings:
                        buy_price = trigger if trigger > 0 else ltp
                        st.session_state.portfolio.append({"Ticker": t, "Symbol": stock_sym, "Qty": 1, "BuyPrice": buy_price, "StopPrice": round(buy_price * (1 - (risk_p/100)), 2)})
                        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
                        st.toast(f"🤖 BOT EXECUTED: Bought {stock_sym}", icon="🛒")
                        st.session_state.alert_log[stock_sym] = time.time()
                        
            except: continue
        
        if results: st.dataframe(pd.DataFrame(results).sort_values("Status"), use_container_width=True, hide_index=True)
        else: st.info("Scanning Market...")

    except Exception as e: st.error(f"Engine Error: {e}")

with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        live_p = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        if live_p.empty: live_p = h_data[p_list].tail(1)
        
        disp_p = []
        total_invested = 0
        total_current_value = 0
        
        for i in st.session_state.portfolio:
            try:
                cv = float(live_p[i['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(live_p.dropna().iloc[-1])
                invested = i['BuyPrice'] * i['Qty']
                current_val = cv * i['Qty']
                
                total_invested += invested
                total_current_value += current_val
                
                disp_p.append({"Stock": i['Symbol'], "Qty": i['Qty'], "Entry": i['BuyPrice'], "SL": i['StopPrice'], "Current": round(cv, 2), "P&L": round(current_val - invested, 2)})
            except: continue
            
        # --- PORTFOLIO DASHBOARD ---
        total_pl = total_current_value - total_invested
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Invested", f"₹{total_invested:,.2f}")
        col2.metric("Current Value", f"₹{total_current_value:,.2f}")
        col3.metric("Total P&L", f"₹{total_pl:,.2f}", f"{(total_pl/total_invested*100) if total_invested > 0 else 0:.2f}%")
        st.divider()
        
        st.dataframe(pd.DataFrame(disp_p), use_container_width=True, hide_index=True)

    with st.expander("➕ Manual Entry"):
        c1, c2, c3 = st.columns(3)
        nt = c1.selectbox("Ticker", TICKERS_NS)
        nq = c2.number_input("Qty", min_value=1)
        np = c3.number_input("Price", min_value=1.0)
        if st.button("Add Trade"):
            st.session_state.portfolio.append({"Ticker": nt, "Symbol": nt.replace(".NS",""), "Qty": nq, "BuyPrice": np, "StopPrice": np * (1 - (risk_p/100))})
            pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
            st.rerun()

with tab3:
    st.subheader("🎯 Watchlist")
    lu = st.selectbox("Quick Add:", NIFTY_50)
    if st.button(f"Add {lu}"):
        if lu not in st.session_state.watchlist: st.session_state.watchlist.append(lu)
    st.divider()
    for s in st.session_state.watchlist: st.write(f"🔹 {s}")
