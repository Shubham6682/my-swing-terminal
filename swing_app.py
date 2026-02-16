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
st.set_page_config(page_title="Elite Quant Terminal", layout="wide")
PORTFOLIO_FILE = "virtual_portfolio.csv"
JOURNAL_FILE = "trade_journal.csv" # <--- NEW: PERMANENT RECORD
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Refresh: 30s (Open) / 60s (Closed)
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=30000 if is_open else 60000, key="quant_sync")

# --- 2. PERSISTENCE LAYER ---
def load_data(file, default_cols):
    if os.path.exists(file): return pd.read_csv(file).to_dict('records')
    return []

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data(PORTFOLIO_FILE, [])
if 'journal' not in st.session_state: st.session_state.journal = load_data(JOURNAL_FILE, []) # <--- LOAD HISTORY
if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 

# --- 3. HELPER FUNCTIONS ---
def save_journal(trade):
    # Appends a closed trade to the permanent CSV
    df = pd.DataFrame(st.session_state.journal)
    df = pd.concat([df, pd.DataFrame([trade])], ignore_index=True)
    df.to_csv(JOURNAL_FILE, index=False)
    st.session_state.journal = df.to_dict('records')

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
st.title("🏹 Elite Quant Terminal: Forward Testing Engine")
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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🧠 Strategy Engine")
    strategy_mode = st.radio("Mode:", ["🛡️ Pro Sentinel (Swing)", "🎯 Elite Sniper (Extreme)"])
    st.divider()
    st.header("🤖 Auto-Bot")
    auto_trade_on = st.checkbox("Active Trading", value=False)
    risk_p = st.slider("Risk (%)", 0.5, 3.0, 1.5)
    st.divider()
    st.header("🔔 Live Feed")
    if not st.session_state.alert_log: st.info("Scanning...")
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
tab1, tab2, tab3, tab4 = st.tabs(["📊 Scanner", "🚀 Active Portfolio", "🎯 Watchlist", "📈 Performance Report"])

# --- TAB 1: SCANNER ---
with tab1:
    try:
        h_data, l_data, v_data = fetch_data()
        results = []
        nifty_perf = h_data['^NSEI'].iloc[-1] / h_data['^NSEI'].iloc[-63]

        for t in TICKERS_NS:
            try:
                hist = h_data[t].dropna()
                ltp = float(l_data[t].dropna().iloc[-1])
                status, trigger = "⏳ WAIT", 0.0
                
                # --- STRATEGY LOGIC ---
                if strategy_mode == "🛡️ Pro Sentinel (Swing)":
                    high_5d = hist.tail(6).iloc[:-1].max()
                    trigger = round(high_5d * 1.002, 2)
                    is_leader = (hist.iloc[-1]/hist.iloc[-63]) > nifty_perf
                    dma200 = hist.rolling(200).mean().iloc[-1]
                    if ltp >= trigger and ltp > dma200 and is_leader: status = "🎯 CONFIRMED"
                    
                else: # Sniper
                    rsi = calculate_rsi(hist).iloc[-1]
                    bb_width = calculate_bollinger_width(hist).iloc[-1]
                    vol_spike = v_data[t].iloc[-1] > (v_data[t].rolling(20).mean().iloc[-1] * 1.5)
                    if bb_width < 0.10: status = "👀 COILING"
                    elif vol_spike and rsi > 55: 
                        status = "🚀 BREAKOUT"
                        trigger = ltp

                # --- DISPLAY ---
                gap = ((ltp - trigger)/trigger)*100
                if status != "⏳ WAIT" and status != "👀 COILING":
                    results.append({"Stock": t.replace(".NS",""), "Status": status, "LTP": ltp, "Entry": trigger, "Gap %": f"{gap:.2f}%"})

                # --- AUTO-BOT EXECUTION ---
                if auto_trade_on and (status == "🎯 CONFIRMED" or status == "🚀 BREAKOUT"):
                    sym = t.replace(".NS","")
                    holdings = [p['Symbol'] for p in st.session_state.portfolio]
                    if sym not in holdings:
                        trade = {
                            "Date": now.strftime("%Y-%m-%d"),
                            "Symbol": sym, "Ticker": t, "Qty": 1,
                            "BuyPrice": trigger if trigger > 0 else ltp,
                            "StopPrice": round((trigger if trigger > 0 else ltp) * (1 - risk_p/100), 2),
                            "Strategy": strategy_mode
                        }
                        st.session_state.portfolio.append(trade)
                        pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
                        st.toast(f"🤖 BOUGHT {sym}")
                        st.session_state.alert_log[sym] = time.time()
            except: continue
        
        st.dataframe(pd.DataFrame(results))
    except: st.info("Scanning...")

# --- TAB 2: ACTIVE PORTFOLIO ---
with tab2:
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        live_p = yf.download(p_list, period="1d", interval="1m", progress=False)['Close']
        if live_p.empty: live_p = h_data[p_list].tail(1)
        
        # Display Table with "CLOSE TRADE" Button
        for i, trade in enumerate(st.session_state.portfolio):
            cv = float(live_p[trade['Ticker']].dropna().iloc[-1]) if len(p_list)>1 else float(live_p.dropna().iloc[-1])
            pl = (cv - trade['BuyPrice']) * trade['Qty']
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**{trade['Symbol']}**")
            c2.write(f"Entry: {trade['BuyPrice']}")
            c3.write(f"LTP: {round(cv, 2)}")
            c4.metric("P&L", f"{pl:.2f}")
            
            if c5.button("✅ CLOSE", key=f"close_{i}"):
                # 1. LOG TO JOURNAL
                closed_trade = trade.copy()
                closed_trade['ExitPrice'] = cv
                closed_trade['ExitDate'] = now.strftime("%Y-%m-%d")
                closed_trade['PnL'] = pl
                closed_trade['Result'] = "WIN" if pl > 0 else "LOSS"
                save_journal(closed_trade)
                
                # 2. REMOVE FROM PORTFOLIO
                st.session_state.portfolio.pop(i)
                pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
                st.rerun()
        st.divider()

# --- TAB 3: WATCHLIST ---
with tab3:
    st.write("Target Stocks...")

# --- TAB 4: PERFORMANCE REPORT (THE NEW ENGINE) ---
with tab4:
    st.header("📈 Strategy Performance Report")
    
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        
        # A. HIGH-LEVEL METRICS
        total_trades = len(df_j)
        wins = df_j[df_j['PnL'] > 0]
        losses = df_j[df_j['PnL'] <= 0]
        win_rate = (len(wins) / total_trades) * 100
        total_profit = df_j['PnL'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Trades", total_trades)
        m2.metric("Win Rate", f"{win_rate:.1f}%")
        m3.metric("Net Profit", f"₹{total_profit:.2f}", delta_color="normal")
        m4.metric("Avg Win", f"₹{wins['PnL'].mean():.2f}" if not wins.empty else "0")
        
        st.divider()
        
        # B. STRATEGY BREAKDOWN
        st.subheader("Strategy Analysis")
        strat_perf = df_j.groupby('Strategy')['PnL'].sum().reset_index()
        st.bar_chart(strat_perf, x='Strategy', y='PnL')
        
        # C. TRADE HISTORY LOG
        st.subheader("Trade Ledger")
        st.dataframe(df_j.sort_values("ExitDate", ascending=False), use_container_width=True)
        
        # D. EXPORT FOR EXCEL
        csv = df_j.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report (CSV)", csv, "trading_report.csv", "text/csv")
        
    else:
        st.info("No closed trades yet. The report will generate automatically after your first sale.")
