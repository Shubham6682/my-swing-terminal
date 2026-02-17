import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_autorefresh import st_autorefresh

# --- 1. SYSTEM SETUP ---
st.set_page_config(page_title="Elite Quant Terminal (Cloud)", layout="wide")

# TIMEZONE
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

# MARKET HOURS (09:15 - 15:30)
market_start = datetime.time(9, 15)
market_end = datetime.time(15, 30)
is_open = (now.weekday() < 5) and (market_start <= now.time() < market_end)

st_autorefresh(interval=30000 if is_open else 60000, key="cloud_indices_fix")

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def init_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client

def load_data(sheet_name):
    try:
        client = init_connection()
        sheet = client.open("Swing_Trading_DB").worksheet(sheet_name)
        data = sheet.get_all_records()
        return data
    except Exception as e:
        return []

def save_data(data, sheet_name):
    try:
        client = init_connection()
        sheet = client.open("Swing_Trading_DB").worksheet(sheet_name)
        sheet.clear() 
        if len(data) > 0:
            df = pd.DataFrame(data)
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Cloud Save Failed: {e}")

def append_to_journal(trade):
    try:
        client = init_connection()
        sheet = client.open("Swing_Trading_DB").worksheet("Journal")
        values = list(trade.values())
        sheet.append_row(values)
    except Exception as e:
        st.error(f"Journal Log Failed: {e}")

# Load Data
if 'portfolio' not in st.session_state: st.session_state.portfolio = load_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = load_data("Journal")
if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 

# --- 3. HELPER FUNCTIONS ---
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

# --- 4. HEADER (Restored Indices) ---
st.title("☁️ Elite Quant Terminal: Cloud Edition")
st.caption(f"Connected to Google Sheet 'Swing_Trading_DB'")

indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        # Fetching Live Index Data
        df_i = yf.Ticker(ticker).history(period="5d")
        if not df_i.empty:
            c, p = df_i['Close'].iloc[-1], df_i['Close'].iloc[-2]
            idx_cols[i].metric(name, f"{c:,.2f}", f"{((c-p)/p)*100:+.2f}%")
        else:
            idx_cols[i].metric(name, "Loading...", "0.00%")
    except: 
        idx_cols[i].metric(name, "Error", "0.00%")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**\n{now.strftime('%H:%M:%S')}")
st.divider()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🧠 Strategy Engine")
    strategy_mode = st.radio("Mode:", ["🛡️ Pro Sentinel (Swing)", "🎯 Elite Sniper (Extreme)"])
    show_all = st.checkbox("Show All Stocks (Debug)", value=True)
    
    st.divider()
    st.header("🤖 Auto-Bot")
    auto_trade_on = st.checkbox("Active Trading", value=False)
    risk_p = st.slider("Risk (%)", 0.5, 3.0, 1.5)
    
    st.divider()
    if st.button("💾 Force Cloud Save"):
        save_data(st.session_state.portfolio, "Portfolio")
        st.success("Saved!")
    
    st.divider()
    st.write("🔌 **Diagnostics**")
    if st.button("Test Google Connection"):
        try:
            client = init_connection()
            sheet = client.open("Swing_Trading_DB")
            st.success(f"✅ Connected: {sheet.title}")
        except Exception as e:
            st.error(f"❌ Failed: {e}")

# --- 6. DATA ENGINE ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS_NS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def fetch_data():
    h = yf.download(TICKERS_NS + ["^NSEI"], period="1y", threads=False, progress=False)['Close']
    l = yf.download(TICKERS_NS, period="1d", interval="1m", threads=False, progress=False)['Close']
    v = yf.download(TICKERS_NS, period="1mo", threads=False, progress=False)['Volume']
    if l.empty or l.dropna(how='all').empty: l = h.tail(1)
    return h, l, v

# --- 7. TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Scanner", "🚀 Active Portfolio", "📈 Analysis Center"])

# --- TAB 1: SCANNER ---
with tab1:
    table_placeholder = st.empty()
    try:
        h_data, l_data, v_data = fetch_data()
        results = []
        nifty_perf = h_data['^NSEI'].iloc[-1] / h_data['^NSEI'].iloc[-63]

        for t in TICKERS_NS:
            try:
                hist = h_data[t].dropna()
                ltp = float(l_data[t].dropna().iloc[-1])
                status, trigger = "⏳ WAIT", 0.0
                
                if strategy_mode == "🛡️ Pro Sentinel (Swing)":
                    high_5d = hist.tail(6).iloc[:-1].max()
                    trigger = round(high_5d * 1.002, 2)
                    is_leader = (hist.iloc[-1]/hist.iloc[-63]) > nifty_perf
                    dma200 = hist.rolling(200).mean().iloc[-1]
                    if ltp >= trigger and ltp > dma200 and is_leader: status = "🎯 CONFIRMED"
                    
                else: 
                    rsi = calculate_rsi(hist).iloc[-1]
                    bb_width = calculate_bollinger_width(hist).iloc[-1]
                    vol_spike = v_data[t].iloc[-1] > (v_data[t].rolling(20).mean().iloc[-1] * 1.5)
                    if bb_width < 0.10: status = "👀 COILING"
                    elif vol_spike and rsi > 55: 
                        status = "🚀 BREAKOUT"
                        trigger = ltp
                    else: status = "😴 SLEEPING"

                gap = ((ltp - trigger)/trigger)*100
                if status != "😴 SLEEPING" or show_all or strategy_mode == "🛡️ Pro Sentinel (Swing)":
                     results.append({"Stock": t.replace(".NS",""), "Status": status, "LTP": round(ltp,2), "Entry": trigger, "Gap %": f"{gap:.2f}%"})

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
                        save_data(st.session_state.portfolio, "Portfolio") # CLOUD SAVE
                        st.toast(f"🤖 BOUGHT {sym}")
            except: continue
        
        if results:
            df_disp = pd.DataFrame(results)
            df_disp['Sort'] = df_disp['Status'].map({"🎯 CONFIRMED": 0, "🚀 BREAKOUT": 0, "👀 COILING": 1, "⏳ WAIT": 2, "😴 SLEEPING": 3})
            df_disp = df_disp.sort_values('Sort').drop('Sort', axis=1)
            table_placeholder.dataframe(df_disp, use_container_width=True, hide_index=True)
        else:
            empty_df = pd.DataFrame(columns=["Stock", "Status", "LTP", "Entry", "Gap %"])
            table_placeholder.dataframe(empty_df, use_container_width=True, hide_index=True)
            
    except Exception as e: st.error(f"Data Error: {e}")

# --- TAB 2: ACTIVE PORTFOLIO ---
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

        changes_made = False
        for i, trade in enumerate(st.session_state.portfolio):
            try:
                cv = get_price(trade['Ticker'])
                current_profit_pct = ((cv - trade['BuyPrice']) / trade['BuyPrice']) * 100
                
                new_sl = trade['StopPrice']
                status_msg = ""
                
                # Smart Exit Logic
                if current_profit_pct > 3.0 and trade['StopPrice'] < trade['BuyPrice']:
                    new_sl = trade['BuyPrice']
                    status_msg = "🛡️ RISK FREE"
                elif current_profit_pct > 5.0:
                    trail_price = cv * 0.98
                    if trail_price > new_sl:
                        new_sl = trail_price
                        status_msg = "📈 TRAILING UP"
                
                if cv < new_sl: status_msg = "❌ STOP HIT"

                if new_sl != trade['StopPrice']:
                    st.session_state.portfolio[i]['StopPrice'] = round(new_sl, 2)
                    changes_made = True
                
                pl = (cv - trade['BuyPrice']) * trade['Qty']
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.write(f"**{trade['Symbol']}**")
                c2.write(f"Entry: {trade['BuyPrice']}")
                c3.metric("LTP", f"{round(cv, 2)}", f"{current_profit_pct:.2f}%")
                c4.metric("Stop Loss", f"{round(new_sl, 2)}", help="Auto-updates")
                
                if c5.button(f"✅ CLOSE {status_msg}", key=f"close_{i}"):
                    closed_trade = trade.copy()
                    closed_trade['ExitPrice'] = cv
                    closed_trade['ExitDate'] = now.strftime("%Y-%m-%d")
                    closed_trade['PnL'] = pl
                    closed_trade['Result'] = "WIN" if pl > 0 else "LOSS"
                    
                    append_to_journal(closed_trade)
                    st.session_state.journal.append(closed_trade)
                    st.session_state.portfolio.pop(i)
                    save_data(st.session_state.portfolio, "Portfolio")
                    st.rerun()

            except: continue
        
        if changes_made:
            save_data(st.session_state.portfolio, "Portfolio")

    else: st.info("Portfolio Empty")

# --- TAB 3: ANALYSIS CENTER ---
with tab3:
    st.header("📈 Weekly Performance Review")
    
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'])
        
        st.subheader("1. This Week's P&L Curve")
        current_week = df_j[df_j['ExitDate'] > (pd.Timestamp(now) - pd.Timedelta(days=7))]
        
        if not current_week.empty:
            week_pl = current_week['PnL'].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("Week's Net P&L", f"₹{week_pl:.2f}", delta_color="normal")
            col2.metric("Trades Taken", len(current_week))
            win_pct = (len(current_week[current_week['PnL']>0])/len(current_week)*100)
            col3.metric("Win Rate", f"{win_pct:.1f}%")
            st.bar_chart(current_week, x='Symbol', y='PnL')
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("🏆 **Top Profit Makers**")
                winners = current_week[current_week['PnL'] > 0].sort_values("PnL", ascending=False).head(3)
                if not winners.empty: st.dataframe(winners[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.info("No winners this week.")
            with c2:
                st.write("⚠️ **Top Loss Makers**")
                losers = current_week[current_week['PnL'] < 0].sort_values("PnL", ascending=True).head(3)
                if not losers.empty: st.dataframe(losers[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.success("No losers this week!")
        else: st.info("No closed trades yet this week.")
        
    else: st.info("Journal Empty. Close a trade to start analysis.")
