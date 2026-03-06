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
from analysis import run_advanced_audit

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Elite Quant Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")

market_open = datetime.time(9, 15)
market_close = datetime.time(15, 30)
is_market_active = (now.weekday() < 5) and (market_open <= now.time() < market_close)

# --- MARKET HOURS REFRESH LOGIC ---
if is_market_active:
    st_autorefresh(interval=30000, key="quant_v18_active_only")
else:
    st.info("🌙 Market is Closed. Auto-refresh is paused to save resources.")

# --- 2. GOOGLE SHEETS ENGINE ---
if 'db_connected' not in st.session_state: st.session_state.db_connected = False

@st.cache_resource
def init_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client
    except: return None

def fetch_sheet_data(tab_name):
    try:
        client = init_google_sheet()
        if client: 
            st.session_state.db_connected = True 
            return client.open("Swing_Trading_DB").worksheet(tab_name).get_all_records()
    except: 
        st.session_state.db_connected = False 
        return []
    return []

def save_portfolio_cloud(data):
    if not st.session_state.db_connected: return
    if data is None: return
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Portfolio")
            if len(data) > 0:
                df = pd.DataFrame(data)
                # 🛡️ BUG FIX: Sanitize missing legacy data so Google Sheets doesn't crash
                df = df.fillna("") 
                write_data = [df.columns.values.tolist()] + df.values.tolist()
            else:
                # 🟢 AI UPGRADE: Added AI Feature headers to fallback empty portfolio
                write_data = [["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "StopPrice", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist"]]
            sheet.clear()
            sheet.update(write_data)
    except Exception as e:
        print(f"Cloud Save Error: {e}")

def log_trade_journal(trade):
    if not st.session_state.db_connected: return False
    # 🟢 AI UPGRADE: Inject the 5 new Market Context features into the Journal row
    row = [
        trade.get("Date", ""), trade.get("EntryTime", ""), trade.get("Symbol", ""), trade.get("Ticker", ""),
        trade.get("Qty", 0), trade.get("BuyPrice", 0.0), trade.get("ExitPrice", 0.0),
        trade.get("ExitDate", ""), trade.get("ExitTime", ""), trade.get("PnL", 0.0), trade.get("Result", ""),
        trade.get("Strategy", ""), trade.get("VIX", 0.0), trade.get("Nifty_Trend", 0.0),
        trade.get("RVol", 0.0), trade.get("RSI", 0.0), trade.get("SMA200_Dist", 0.0)
    ]
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Journal")
            if not sheet.row_values(1):
                # 🟢 AI UPGRADE: Expand Journal headers
                headers = ["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "ExitPrice", "ExitDate", "ExitTime", "PnL", "Result", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist"]
                sheet.append_row(headers)
            sheet.append_row(row)
            return True
    except: return False

def log_signal_cloud(symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist):
    if not st.session_state.db_connected: return False
    for attempt in range(3): 
        try:
            client = init_google_sheet()
            if client:
                sheet = client.open("Swing_Trading_DB").worksheet("Signal_Log")
                if not sheet.row_values(1):
                    headers = ["Date", "Symbol", "Time", "Status", "Nifty_Trend", "VIX", "RVol", "RSI", "SMA200_Dist"]
                    sheet.append_row(headers)
                # 🟢 FULL AI PARITY: Logging the complete micro and macro environment
                sheet.append_row([today_str, symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist])
                return True 
        except: time.sleep(1) 
    return False

def load_signals_from_cloud():
    history = {}
    try:
        data = fetch_sheet_data("Signal_Log")
        if data:
            df = pd.DataFrame(data)
            if not df.empty and 'Date' in df.columns:
                today_data = df[df['Date'] == today_str]
                for _, row in today_data.iterrows():
                    history[row['Symbol']] = row['Time']
    except: pass
    return history

# --- 3. SESSION STATE ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = fetch_sheet_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = fetch_sheet_data("Journal")
if 'blacklist' not in st.session_state: st.session_state.blacklist = []
if 'notifications' not in st.session_state: st.session_state.notifications = []

if 'last_run_date' not in st.session_state or st.session_state.last_run_date != today_str:
    st.session_state.last_run_date = today_str
    st.session_state.signal_history = load_signals_from_cloud()
    st.session_state.blacklist = []
    st.session_state.notifications = []

# --- 4. SIDEBAR & NOTIFICATIONS ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    mode = st.radio("Strategy Mode:", ["🛡️ Swing (Sentinel)", "🎯 Scalp (Sniper)"])
    st.divider()
    
    st.subheader("🤖 Auto-Bot")
    if st.session_state.db_connected:
        bot_active = st.checkbox("Enable Auto-Buying", value=True)
        auto_sell = st.checkbox("Enable Auto-Sell-Off", value=True, help="Automatically sells when SL is hit")
    else:
        st.error("⚠️ Offline: Trading Disabled")
        bot_active, auto_sell = False, False
        
    risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.5)
    
    st.divider()
    st.subheader("🔔 Notification Log")
    if not st.session_state.notifications:
        st.caption("No recent activity.")
    else:
        for note in reversed(st.session_state.notifications[-8:]):
            st.info(note)
            
    if st.button("🗑️ Clear Logs"):
        st.session_state.notifications = []
        st.rerun()
        
    st.divider()
    if st.button("💾 Force Save to Cloud"):
        save_portfolio_cloud(st.session_state.portfolio)
        if st.session_state.db_connected: st.success("Synced!")
        
    if st.button("🔄 Force Reload DB"):
        st.session_state.journal = fetch_sheet_data("Journal")
        st.session_state.portfolio = fetch_sheet_data("Portfolio")
        st.success("Data reloaded from Cloud!")
        st.rerun()

    with st.expander("🔧 Diagnostics"):
        show_all = st.checkbox("Show 'WAIT' Stocks", value=True) 
        if st.button("Test DB Connection"):
            if init_google_sheet(): 
                st.session_state.db_connected = True
                st.success("✅ Connected")
            else: 
                st.session_state.db_connected = False
                st.error("❌ Failed")

# --- 5. INDICATORS & MARKET DATA ---
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

NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def get_market_data():
    try:
        if now.time() < datetime.time(9, 0): return pd.DataFrame(), pd.DataFrame()
        # 🟢 AI UPGRADE: Appended ^INDIAVIX to pull the Fear Gauge
        data = yf.download(TICKERS + ["^NSEI", "^INDIAVIX"], period="1y", threads=False, progress=False)
        return data['Close'], data['Volume']
    except: return pd.DataFrame(), pd.DataFrame()

closes, volumes = get_market_data()

is_safe_to_buy = False 
market_status_msg = "⚪ MARKET DATA LOADING..."

if not closes.empty and '^NSEI' in closes.columns:
    nifty_closes = closes['^NSEI'].dropna()
    if len(nifty_closes) > 20:
        nifty_sma20 = nifty_closes.rolling(20).mean().iloc[-1]
        nifty_curr = nifty_closes.iloc[-1]
        nifty_prev = nifty_closes.iloc[-2]
        
        intraday_pct = ((nifty_curr - nifty_prev) / nifty_prev) * 100
        is_macro_bullish = nifty_curr > nifty_sma20
        is_bleeding = intraday_pct < -0.3
        
        is_safe_to_buy = is_macro_bullish and not is_bleeding
        
        if is_bleeding:
            market_status_msg = f"🔴 CRITICAL: NIFTY BLEEDING ({intraday_pct:.2f}%). ALL BUYING HALTED."
        elif not is_macro_bullish:
            market_status_msg = f"🔴 MARKET MOOD: BEARISH (Below 20 SMA). Buying Paused."
        else:
            market_status_msg = f"🟢 MARKET MOOD: BULLISH (Up {intraday_pct:.2f}%)"
else:
    if now.time() < datetime.time(9, 15): market_status_msg = "🌙 PRE-MARKET: Waiting for 9:15 AM..."
    else: market_status_msg = "⚠️ NIFTY DATA ERROR (Running Safe Mode)"

c1, c2 = st.columns([3, 1])
with c1:
    st.title("☁️ Elite Quant Terminal")
    if st.session_state.db_connected: st.caption("✅ Cloud Database: Connected")
    else: st.caption("🚫 Cloud Database: DISCONNECTED (Trading Disabled)")
    if "CRITICAL" in market_status_msg: st.error(market_status_msg)
    elif "BULLISH" in market_status_msg: st.success(market_status_msg)
    elif "BEARISH" in market_status_msg: st.warning(market_status_msg)
    elif "PRE-MARKET" in market_status_msg: st.info(market_status_msg)
    else: st.warning(market_status_msg)

with c2:
    status_emoji = "🟢" if is_market_active else "🔴"
    st.metric("Market Time (IST)", f"{now.strftime('%H:%M:%S')}", f"{status_emoji} {'OPEN' if is_market_active else 'CLOSED'}")

indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
cols = st.columns(len(indices))
for i, (name, ticker) in enumerate(indices.items()):
    try:
        df = yf.Ticker(ticker).history(period="5d")
        if not df.empty:
            curr, prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
            pct = ((curr - prev) / prev) * 100
            color = "green" if pct >= 0 else "red"
            cols[i].markdown(f"<div style='border:1px solid #333; padding:10px; border-radius:5px; text-align:center;'><small>{name}</small><br><b style='font-size:18px;'>{curr:,.0f}</b><br><span style='color:{color}; font-size:14px;'>{pct:+.2f}%</span></div>", unsafe_allow_html=True)
    except: cols[i].write("-")
st.divider()

# --- 6. TABS ---
tab1, tab2, tab3 = st.tabs(["🔍 Market Scanner", "💼 Active Portfolio", "📊 Performance Audit"])

# --- TAB 1: SCANNER ---
with tab1:
    scan_placeholder = st.empty()
    try:
        scan_results = []
        new_trades_added = False
        nifty_perf = 0.0
        if not closes.empty and '^NSEI' in closes.columns:
             nifty_closes = closes['^NSEI'].dropna()
             if not nifty_closes.empty and len(nifty_closes) > 60:
                nifty_perf = nifty_closes.iloc[-1] / nifty_closes.iloc[-60]
                 # --- 🟢 NEW: CUSTOM WATCHLIST ANALYZER ---
        st.markdown("### 🔍 Custom Watchlist Analyzer")
        c_input = st.text_input("Type any NSE Ticker to test the math (e.g., ZOMATO, RVNL, SUZLON):", "").strip().upper()
        
        if c_input:
            custom_sym = c_input.replace('.NS', '')
            custom_ticker = f"{custom_sym}.NS"
            with st.spinner(f"Running quant engine on {custom_sym}..."):
                try:
                    c_data = yf.download(custom_ticker, period="1y", progress=False, threads=False)
                    if not c_data.empty and 'Close' in c_data.columns and 'Volume' in c_data.columns:
                        c_closes = c_data['Close'].squeeze().dropna()
                        c_vols = c_data['Volume'].squeeze().dropna()
                        
                        if len(c_closes) > 60:
                            # 1. Pull current data
                            c_curr_price = float(c_closes.iloc[-1])
                            c_curr_vol = float(c_vols.iloc[-1])
                            c_vol_sma20 = float(c_vols.rolling(20).mean().iloc[-1])
                            c_rsi = float(calculate_rsi(c_closes).iloc[-1])
                            
                            c_status, c_trigger = "⏳ WAIT", 0.0
                            
                            # 2. Run the strategy math
                            if mode == "🛡️ Swing (Sentinel)":
                                c_high_5d = c_closes.tail(6).iloc[:-1].max()
                                c_sma200 = c_closes.rolling(200).mean().iloc[-1]
                                c_perf = c_closes.iloc[-1] / c_closes.iloc[-60]
                                c_trigger = c_high_5d
                                
                                if c_curr_price > c_high_5d and c_curr_price > c_sma200 and c_perf > nifty_perf:
                                    c_status = "🎯 CONFIRMED" if is_safe_to_buy else "⛔ MKT WEAK"
                            else:
                                c_bb_w = calculate_bollinger_width(c_closes).iloc[-1]
                                if c_bb_w < 0.10: c_status = "👀 WATCH (Squeeze)"
                                elif (c_curr_vol > c_vol_sma20 * 1.5) and c_rsi > 55:
                                    if is_safe_to_buy: 
                                        c_status = "🚀 BREAKOUT"
                                        c_trigger = c_curr_price
                                    else: c_status = "⛔ MKT WEAK"
                            
                            # 3. Draw the Results Card
                            bg_color = "#d4edda" if c_status in ["🎯 CONFIRMED", "🚀 BREAKOUT"] else ("#fff3cd" if c_status == "👀 WATCH (Squeeze)" else "#f8f9fa")
                            border_color = "#28a745" if c_status in ["🎯 CONFIRMED", "🚀 BREAKOUT"] else ("#ffeeba" if c_status == "👀 WATCH (Squeeze)" else "#6c757d")
                            vol_surge = (c_curr_vol / c_vol_sma20) * 100 if c_vol_sma20 > 0 else 0
                            
                            st.markdown(f"""
                            <div style='border: 2px solid {border_color}; border-radius: 8px; padding: 15px; background-color: {bg_color}; color: #333;'>
                                <h4 style='margin-top:0px; color: #111;'>{custom_sym} System Diagnostics</h4>
                                <b>Signal:</b> {c_status} &nbsp;|&nbsp; <b>LTP:</b> ₹{c_curr_price:.2f} &nbsp;|&nbsp; <b>Target/Entry:</b> ₹{c_trigger:.2f}<br>
                                <b>RSI:</b> {c_rsi:.1f} &nbsp;|&nbsp; <b>Volume Surge:</b> {vol_surge:.0f}%
                            </div>
                            """, unsafe_allow_html=True)
                        else: st.warning(f"Not enough historical data to calculate 200 SMA on {custom_sym}.")
                    else: st.error("Invalid Ticker. Make sure it's an NSE stock.")
                except Exception as e: st.error(f"Error evaluating {custom_sym}: {e}")
        
        st.divider()
        # --- END CUSTOM ANALYZER ---

        active_symbols_now = []

        for ticker in TICKERS:
            try:
                if ticker not in closes.columns: continue
                series = closes[ticker].dropna()
                vol_series = volumes[ticker].dropna()
                if series.empty: continue
                
                curr_price = series.iloc[-1]
                if pd.isna(curr_price): continue
                
                curr_vol = vol_series.iloc[-1]
                vol_sma20 = vol_series.rolling(20).mean().iloc[-1]
                
                status, trigger_price = "⏳ WAIT", 0.0
                symbol = ticker.replace(".NS", "")
                
                # 🟢 NEW: Isolate raw mathematical trigger from market filter
                raw_technical_trigger = False 
                
                if mode == "🛡️ Swing (Sentinel)":
                    high_5d = series.tail(6).iloc[:-1].max()
                    sma200 = series.rolling(200).mean().iloc[-1]
                    if len(series) > 60: stock_perf = series.iloc[-1] / series.iloc[-60]
                    else: stock_perf = 0
                    trigger_price = high_5d
                    
                    if curr_price > high_5d and curr_price > sma200 and stock_perf > nifty_perf:
                        raw_technical_trigger = True
                        if is_safe_to_buy: status = "🎯 CONFIRMED"
                        else: status = "⛔ MKT WEAK"
                else: 
                    bb_w = calculate_bollinger_width(series).iloc[-1]
                    rsi = calculate_rsi(series).iloc[-1]
                    vol_ma = vol_series.rolling(20).mean().iloc[-1]
                    
                    if bb_w < 0.10: status = "👀 WATCH (Squeeze)"
                    elif (vol_series.iloc[-1] > vol_ma * 1.5) and rsi > 55:
                        raw_technical_trigger = True
                        if is_safe_to_buy: 
                            status = "🚀 BREAKOUT"
                            trigger_price = curr_price
                        else: 
                            status = "⛔ MKT WEAK"

                gap_pct = ((curr_price - trigger_price) / trigger_price) * 100 if trigger_price > 0 else 0
                
                signal_time = "-"
                
                # 🧠 1. CALCULATE ALL AI FEATURES FIRST (For both Logging and Buying)
                n_trend = round(float(intraday_pct), 2) if 'intraday_pct' in locals() else 0.0
                try: c_vix = round(float(closes['^INDIAVIX'].dropna().iloc[-1]), 2)
                except: c_vix = 15.0
                
                c_rvol = round(float(curr_vol / vol_sma20), 2) if vol_sma20 > 0 else 1.0
                c_rsi = round(float(calculate_rsi(series).iloc[-1]), 2)
                
                c_sma200 = series.rolling(200).mean().iloc[-1]
                c_dist = round(float(((curr_price - c_sma200) / c_sma200) * 100), 2) if c_sma200 > 0 else 0.0

                # 🟢 2. LOGGING UPGRADE: Push all features to the Signal Log
                if raw_technical_trigger:
                    active_symbols_now.append(symbol)
                    if now.time() >= datetime.time(9, 15):
                        if symbol not in st.session_state.signal_history:
                            current_time_str = now.strftime("%H:%M")
                            st.session_state.signal_history[symbol] = current_time_str
                            
                            log_signal_cloud(symbol, current_time_str, status, n_trend, c_vix, c_rvol, c_rsi, c_dist)
                    
                if symbol in st.session_state.signal_history:
                    signal_time = st.session_state.signal_history[symbol]
                    start_time_obj = datetime.datetime.strptime(signal_time, "%H:%M").time()
                    cutoff_start = datetime.time(10, 0)
                    cutoff_now = datetime.time(15, 0)
                    
                    if now.time() >= cutoff_now and start_time_obj <= cutoff_start:
                        # 🛡️ FATAL FLAW PATCH: Verify the stock didn't crash during the day
                        if raw_technical_trigger:
                            if curr_vol > vol_sma20: 
                                status = "✅ STRONG BUY" if is_safe_to_buy else "⛔ MKT WEAK"
                            else: 
                                status = "⚠️ LOW VOL"
                        else:
                            status = "❌ FAILED SETUP" # It spiked in the morning but died by the afternoon

                scan_results.append({
                    "Stock": symbol, "Status": status, "Signal Time": signal_time,
                    "Price": round(curr_price, 2), "Entry": round(trigger_price, 2),
                    "Vol vs Avg": f"{(curr_vol/vol_sma20)*100:.0f}%" if vol_sma20 > 0 else "0%",
                    "Gap %": f"{gap_pct:.1f}%"
                })
                
                # 🟢 3. BUY EXECUTION UPGRADE: Reuse the exact same AI features
                if bot_active and status in ["🎯 CONFIRMED", "🚀 BREAKOUT", "✅ STRONG BUY"]:
                    current_holdings = [x['Symbol'] for x in st.session_state.portfolio]
                    if symbol not in current_holdings and symbol not in st.session_state.blacklist:
                        
                        new_trade = {
                            "Date": now.strftime("%Y-%m-%d"), "EntryTime": now.strftime("%H:%M:%S"),
                            "Symbol": symbol, "Ticker": ticker, "Qty": 1, "BuyPrice": curr_price,
                            "StopPrice": curr_price * (1 - (risk_per_trade/100)), "Strategy": mode,
                            # 🧠 SILENT AI FEATURES
                            "VIX": c_vix, "Nifty_Trend": n_trend, "RVol": c_rvol,
                            "RSI": c_rsi, "SMA200_Dist": c_dist
                        }
                        
                        st.session_state.portfolio.append(new_trade)
                        new_trades_added = True
                        st.session_state.notifications.append(f"🟢 {now.strftime('%H:%M')} - BOT BOUGHT: {symbol} at ₹{curr_price:.2f}")
                        st.toast(f"🤖 Bot Bought: {symbol}")
            except: continue

        if scan_results:
            df_scan = pd.DataFrame(scan_results)
            sort_map = {"✅ STRONG BUY": 0, "🎯 CONFIRMED": 1, "🚀 BREAKOUT": 1, "⚠️ LOW VOL": 2, "⛔ MKT WEAK": 3, "👀 WATCH (Squeeze)": 4, "⏳ WAIT": 5}
            df_scan['Sort'] = df_scan['Status'].map(sort_map)
            df_scan = df_scan.sort_values('Sort').drop('Sort', axis=1)
            
            def highlight_status(s):
                if s['Status'] == '✅ STRONG BUY': return ['background-color: #d4edda; color: #155724'] * len(s)
                elif s['Status'] == '⛔ MKT WEAK': return ['background-color: #f8d7da; color: #721c24'] * len(s)
                elif s['Status'] == '⚠️ LOW VOL': return ['background-color: #fff3cd; color: #856404'] * len(s)
                else: return [''] * len(s)
            
            if not show_all: df_scan = df_scan[df_scan['Status'] != '⏳ WAIT']
            scan_placeholder.dataframe(df_scan.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
            
            if bot_active and new_trades_added:
                save_portfolio_cloud(st.session_state.portfolio)
        else: scan_placeholder.info("Scanner Active. No signals found yet.")
    except Exception as e: scan_placeholder.error(f"Scanner Error: {e}")

# --- TAB 2: PORTFOLIO & AUTO-EXIT ---
with tab2:
    if st.session_state.portfolio:
        tickers = [p['Ticker'] for p in st.session_state.portfolio]
        try:
            live_data = yf.download(tickers, period="1d", interval="1m", threads=False, progress=False)['Close']
        except: live_data = pd.DataFrame()
        
        total_val, total_inv = 0, 0
        portfolio_changed = False
        remaining_stocks = []
        
        today_pnl = 0.0
        today_count = 0
        winners = 0
        losers = 0
        today_str = now.strftime("%Y-%m-%d") 
        
        for i, trade in enumerate(st.session_state.portfolio):
            api_glitch = False
            try:
                if len(tickers) > 1 and not live_data.empty: price = live_data[trade['Ticker']].dropna().iloc[-1]
                elif not live_data.empty: price = live_data.dropna().iloc[-1]
                else: 
                    price = float(trade['BuyPrice'])
                    api_glitch = True
                if pd.isna(price): 
                    price = float(trade['BuyPrice'])
                    api_glitch = True
            except: 
                price = float(trade['BuyPrice'])
                api_glitch = True
            
            qty = int(trade['Qty'])
            buy = float(trade['BuyPrice'])
            sl = float(trade['StopPrice'])
            
            cur_val = price * qty
            inv_val = buy * qty
            pnl = cur_val - inv_val
            pnl_pct = (pnl / inv_val) * 100
            
            total_val += cur_val
            total_inv += inv_val
            
            if not api_glitch:
                if pnl > 0: winners += 1
                elif pnl < 0: losers += 1
            
            if str(trade.get('Date')) == today_str:
                today_pnl += pnl
                today_count += 1
            
            msg, new_sl = "", sl
            
            if not api_glitch:
                if pnl_pct > 4.0 and sl < buy:
                    new_sl = buy
                    msg = "🛡️ RISK FREE"
                
                if pnl_pct > 6.0:
                    trail = round(price * 0.96, 2)
                    if trail > new_sl:
                        new_sl = trail
                        msg = "📈 TRAILING"
                
                if price <= new_sl: msg = "❌ STOP HIT"
                
                new_sl = round(new_sl, 2)
                if new_sl != sl:
                    trade['StopPrice'] = new_sl
                    portfolio_changed = True
            
            action_taken = False
            
            is_already_sold = any(
                j.get('Symbol') == trade['Symbol'] and str(j.get('ExitDate')) == now.strftime("%Y-%m-%d") 
                for j in st.session_state.journal
            )

            if is_already_sold:
                portfolio_changed = True
                action_taken = True
                if trade['Symbol'] not in st.session_state.blacklist:
                    st.session_state.blacklist.append(trade['Symbol'])
            
            elif auto_sell and not api_glitch and (price <= new_sl):
                closed_trade = trade.copy()
                closed_trade.update({
                    'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 
                    'ExitTime': now.strftime("%H:%M:%S"), 'PnL': pnl, 
                    'Result': "WIN" if pnl > 0 else "LOSS"
                })
                
                if log_trade_journal(closed_trade):
                    st.session_state.notifications.append(f"🛑 {now.strftime('%H:%M')} - AUTO-SOLD: {trade['Symbol']} at ₹{price:.2f}")
                    st.session_state.journal.append(closed_trade)
                    st.session_state.blacklist.append(trade['Symbol'])
                    portfolio_changed = True
                    action_taken = True

            if not action_taken:
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.write(f"**{trade['Symbol']}**")
                c2.write(f"Entry: {buy:.2f}")
                
                if api_glitch: c3.metric("LTP", "API Syncing...", "Holding...")
                else: c3.metric("LTP", f"{price:.2f}", f"{pnl_pct:.2f}%")
                    
                c4.metric("Stop Loss", f"{new_sl:.2f}", help="Auto-Managed")
                
                if c5.button(f"✅ CLOSE {msg}", key=f"close_{trade['Symbol']}", disabled=api_glitch):
                    closed_trade = trade.copy()
                    closed_trade.update({
                        'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 
                        'ExitTime': now.strftime("%H:%M:%S"), 'PnL': pnl, 
                        'Result': "WIN" if pnl > 0 else "LOSS"
                    })
                    
                    if log_trade_journal(closed_trade):
                        st.session_state.notifications.append(f"👤 {now.strftime('%H:%M')} - MANUALLY CLOSED: {trade['Symbol']} at ₹{price:.2f}")
                        st.session_state.blacklist.append(trade['Symbol'])
                        st.session_state.journal.append(closed_trade)
                        portfolio_changed = True
                        action_taken = True

            if not action_taken:
                remaining_stocks.append(trade)
        
        if portfolio_changed:
            st.session_state.portfolio = remaining_stocks
            save_portfolio_cloud(st.session_state.portfolio)
            st.rerun()

        st.divider()
        if total_inv > 0:
            st.markdown("### 📊 Live Portfolio Health")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Capital Deployed", f"₹{total_inv:,.2f}")
            
            total_floating_pnl = total_val - total_inv
            total_roi_pct = (total_floating_pnl / total_inv) * 100 if total_inv > 0 else 0.0
            c2.metric("Total Floating PnL", f"₹{total_floating_pnl:,.2f}", f"{total_roi_pct:.2f}% Overall")
            
            if today_pnl >= 0: c3.metric(f"Today's PnL ({today_count} trades)", f"₹{today_pnl:,.2f}", "📈 Sourced Today")
            else: c3.metric(f"Today's PnL ({today_count} trades)", f"₹{today_pnl:,.2f}", "📉 Sourced Today")
                
            c4.metric("Live Market Heat", f"{winners} Green / {losers} Red", border=True)
    else: st.info("Portfolio Empty. Go to Scanner to find stocks.")

# --- TAB 3: ANALYSIS ---
with tab3:
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        
        if 'PnL' in df_j.columns:
            df_j['PnL'] = df_j['PnL'].astype(str).str.replace(r'[₹,a-zA-Z\s]', '', regex=True)
            df_j['PnL'] = pd.to_numeric(df_j['PnL'], errors='coerce').fillna(0)
        else:
            df_j['PnL'] = 0

        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'], errors='coerce')
        curr_trades = df_j[df_j['ExitDate'].notnull()]
        
        if not curr_trades.empty:
            pnl = curr_trades['PnL'].sum()
            wins = len(curr_trades[curr_trades['PnL'] > 0])
            total = len(curr_trades)
            rate = (wins / total) * 100 if total > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Net Profit (All Time)", f"₹{pnl:,.2f}")
            k2.metric("Total Trades", total)
            k3.metric("Win Rate", f"{rate:.1f}%")
            st.bar_chart(curr_trades, x="Symbol", y="PnL")
            
            st.divider()
            if 'show_audit' not in st.session_state:
                st.session_state.show_audit = False
                
            if st.button("📊 Toggle Deep Performance Audit"):
                st.session_state.show_audit = not st.session_state.show_audit
                
            if st.session_state.show_audit:
                run_advanced_audit(df_j)
        else: st.info("No valid trades found in Journal.")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.write("🏆 **All Winners**")
            winners = df_j[df_j['PnL'] > 0]
            if not winners.empty:
                st.dataframe(winners.sort_values('PnL', ascending=False)[['Symbol', 'PnL', 'Strategy']], hide_index=True)
            else: st.write("No wins yet.")
            
        with c2:
            st.write("⚠️ **All Losers**")
            losers = df_j[df_j['PnL'] < 0]
            if not losers.empty:
                st.dataframe(losers.sort_values('PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
            else: st.write("No losses yet.")
    else: st.info("Journal Empty. Close trades to see analysis.")







