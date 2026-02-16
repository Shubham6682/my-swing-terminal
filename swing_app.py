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
JOURNAL_FILE = "trade_journal.csv"    # Realized P&L (Closed Trades)
DAILY_LOG_FILE = "daily_equity.csv"   # Daily Snapshots (Net Worth)
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# Refresh Rate
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
st_autorefresh(interval=30000 if is_open else 60000, key="quant_final_sync")

# --- 2. PERSISTENCE & DATA LOADING ---
def load_data(file):
    if os.path.exists(file): return pd.read_csv(file).to_dict('records')
    return []

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data(PORTFOLIO_FILE)
if 'journal' not in st.session_state: st.session_state.journal = load_data(JOURNAL_FILE)
if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 

# --- 3. HELPER FUNCTIONS ---
def save_journal(trade):
    df = pd.DataFrame(st.session_state.journal)
    new_row = pd.DataFrame([trade])
    if not df.empty:
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        df = new_row
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
st.title("🏹 Elite Quant Terminal: Automated Ledger")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        # threads=False to prevent crashes
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
    # threads=False is CRITICAL
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", threads=False, progress=False)['Close']
    l = yf.download(TICKERS_NS, period="1d", interval="1m", threads=False, progress=False)['Close']
    v = yf.download(TICKERS_NS, period="1mo", threads=False, progress=False)['Volume']
    if l.empty or l.dropna(how='all').empty: l = h.tail(1)
    return h, l, v

# --- 7. TABS ---
# This line creates the tabs. They MUST be created here.
tab1, tab2, tab3 = st.tabs(["📊 Scanner", "🚀 Active Portfolio", "📈 Performance & Analysis"])

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
                
                # Logic Switch
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

                gap = ((ltp - trigger)/trigger)*100
                
                # Add to results
                results.append({"Stock": t.replace(".NS",""), "Status": status, "LTP": round(ltp,2), "Entry": trigger, "Gap %": f"{gap:.2f}%"})

                # Bot Logic
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
        
        # Display Results
        if results:
            df_disp = pd.DataFrame(results)
            df_disp['Sort'] = df_disp['Status'].map({"🎯 CONFIRMED": 0, "🚀 BREAKOUT": 0, "👀 COILING": 1, "⏳ WAIT": 2})
            df_disp = df_disp.sort_values('Sort').drop('Sort', axis=1)
            st.dataframe(df_disp, use_container_width=True, hide_index=True)
            
    except Exception as e: st.info(f"Scanning... {e}")

# --- TAB 2: ACTIVE PORTFOLIO + AUTO SNAPSHOT ---
with tab2:
    current_portfolio_value = 0
    if st.session_state.portfolio:
        p_list = [i['Ticker'] for i in st.session_state.portfolio]
        live_p = yf.download(p_list, period="1d", interval="1m", threads=False, progress=False)['Close']
        if live_p.empty: live_p = h_data[p_list].tail(1)
        
        total_invested = 0
        def get_price(ticker):
            try: return float(live_p[ticker].dropna().iloc[-1]) if len(p_list)>1 else float(live_p.dropna().iloc[-1])
            except: return 0.0

        for trade in st.session_state.portfolio:
            cv = get_price(trade['Ticker'])
            if cv > 0:
                total_invested += trade['BuyPrice'] * trade['Qty']
                current_portfolio_value += cv * trade['Qty']
        
        net_pl = current_portfolio_value - total_invested
        pl_pct = (net_pl / total_invested * 100) if total_invested > 0 else 0
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Invested", f"₹{total_invested:,.2f}")
        k2.metric("Current Value", f"₹{current_portfolio_value:,.2f}")
        k3.metric("Net P&L", f"₹{net_pl:,.2f}", f"{pl_pct:.2f}%")
        st.divider()

        # --- AUTO-LOGIC: MARKET CLOSE SNAPSHOT ---
        # If market is closed AND we haven't saved today's log yet -> Save it.
        if not is_open:
            today_str = now.strftime("%Y-%m-%d")
            log_df = pd.DataFrame()
            if os.path.exists(DAILY_LOG_FILE): log_df = pd.read_csv(DAILY_LOG_FILE)
            
            # Check if today is already logged
            if log_df.empty or today_str not in log_df['Date'].values:
                new_log = {"Date": today_str, "TotalValue": current_portfolio_value, "NetPnL": net_pl}
                if not log_df.empty:
                    log_df = pd.concat([log_df, pd.DataFrame([new_log])], ignore_index=True)
                else:
                    log_df = pd.DataFrame([new_log])
                log_df.to_csv(DAILY_LOG_FILE, index=False)
                st.toast("📸 Daily Performance Snapshot Saved!")

        for i, trade in enumerate(st.session_state.portfolio):
            try:
                cv = get_price(trade['Ticker'])
                pl = (cv - trade['BuyPrice']) * trade['Qty']
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.write(f"**{trade['Symbol']}**")
                c2.write(f"{trade['BuyPrice']}")
                c3.write(f"{round(cv, 2)}")
                c4.metric("P&L", f"{pl:.2f}")
                if c5.button("✅ CLOSE", key=f"close_{i}"):
                    closed_trade = trade.copy()
                    closed_trade['ExitPrice'] = cv
                    closed_trade['ExitDate'] = now.strftime("%Y-%m-%d")
                    closed_trade['PnL'] = pl
                    closed_trade['Result'] = "WIN" if pl > 0 else "LOSS"
                    save_journal(closed_trade)
                    st.session_state.portfolio.pop(i)
                    pd.DataFrame(st.session_state.portfolio).to_csv(PORTFOLIO_FILE, index=False)
                    st.rerun()
            except: continue
    else: st.info("Portfolio Empty")

# --- TAB 3: ANALYSIS CENTER (WEEKLY REPORT) ---
with tab3:
    st.header("📈 Weekly Performance Review")
    
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        # Ensure ExitDate is datetime
        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'])
        
        # 1. VISUALIZE THE WEEK
        st.subheader("1. This Week's P&L Curve")
        # Filter for current week's data only
        current_week = df_j[df_j['ExitDate'] > (pd.Timestamp(now) - pd.Timedelta(days=7))]
        
        if not current_week.empty:
            # Show the Net P&L for this week
            week_pl = current_week['PnL'].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("Week's Net P&L", f"₹{week_pl:.2f}", delta_color="normal")
            col2.metric("Trades Taken", len(current_week))
            win_pct = (len(current_week[current_week['PnL']>0])/len(current_week)*100)
            col3.metric("Win Rate", f"{win_pct:.1f}%")
            
            st.bar_chart(current_week, x='Symbol', y='PnL')
            
            st.divider()
            
            # 2. HEROES & VILLAINS (Best vs Worst)
            st.subheader("2. Stock Performance Attribution")
            c1, c2 = st.columns(2)
            
            with c1:
                st.write("🏆 **Top Profit Makers**")
                winners = current_week[current_week['PnL'] > 0].sort_values("PnL", ascending=False).head(3)
                if not winners.empty:
                    st.dataframe(winners[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.info("No winners this week.")
                
            with c2:
                st.write("⚠️ **Top Loss Makers**")
                losers = current_week[current_week['PnL'] < 0].sort_values("PnL", ascending=True).head(3)
                if not losers.empty:
                    st.dataframe(losers[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.success("No losers this week! 🎉")

        else:
            st.info("No closed trades yet this week. Close positions in Tab 2 to see the report.")
            
        st.divider()

        # 3. LONG TERM HISTORY
        st.subheader("3. Monthly Ledger")
        # Resample by Month (M)
        monthly = df_j.set_index('ExitDate').resample('M')['PnL'].sum().reset_index()
        monthly['ExitDate'] = monthly['ExitDate'].dt.strftime('%B %Y')
        st.dataframe(monthly, use_container_width=True)
        
        # Download Data
        csv = df_j.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Trade History (CSV)", csv, "full_trade_history.csv", "text/csv")
        
    else:
        st.info("Your Journal is empty. The analysis will start automatically after your first trade.")
