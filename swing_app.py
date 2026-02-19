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

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Elite Quant Terminal", layout="wide")

# TIMEZONE & MARKET HOURS
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")

market_open = datetime.time(9, 15)
market_close = datetime.time(15, 30)
is_market_active = (now.weekday() < 5) and (market_open <= now.time() < market_close)

# AUTO-REFRESH
st_autorefresh(interval=30000 if is_market_active else 60000, key="quant_refresh_v12_complete")

# --- 2. GOOGLE SHEETS DATABASE ENGINE (ROBUST) ---
if 'db_connected' not in st.session_state: st.session_state.db_connected = False

@st.cache_resource
def init_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e: return None

def fetch_sheet_data(tab_name):
    try:
        client = init_google_sheet()
        if client: 
            st.session_state.db_connected = True 
            return client.open("Swing_Trading_DB").worksheet(tab_name).get_all_records()
    except: 
        st.session_state.db_connected = False 
        return []
    st.session_state.db_connected = False
    return []

# --- PERSISTENT LOGGING WITH RETRY LOGIC ---
def safe_write_to_sheet(tab_name, row_data):
    if not st.session_state.db_connected: return False
    for attempt in range(3): 
        try:
            client = init_google_sheet()
            if client:
                sheet = client.open("Swing_Trading_DB").worksheet(tab_name)
                sheet.append_row(row_data)
                return True 
        except Exception as e:
            time.sleep(1) 
    return False 

def log_signal_cloud(symbol, signal_time):
    safe_write_to_sheet("Signal_Log", [today_str, symbol, signal_time])

def save_portfolio_cloud(data):
    if not st.session_state.db_connected: return
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Portfolio")
            sheet.clear()
            if len(data) > 0:
                df = pd.DataFrame(data)
                sheet.update([df.columns.values.tolist()] + df.values.tolist())
            else:
                sheet.append_row(["Date", "Symbol", "Ticker", "Qty", "BuyPrice", "StopPrice", "Strategy"])
    except: pass

def log_trade_journal(trade):
    if not st.session_state.db_connected: return False
    row = [
        trade.get("Date", ""), trade.get("Symbol", ""), trade.get("Ticker", ""),
        trade.get("Qty", 0), trade.get("BuyPrice", 0.0), trade.get("ExitPrice", 0.0),
        trade.get("ExitDate", ""), trade.get("PnL", 0.0), trade.get("Result", ""),
        trade.get("Strategy", "")
    ]
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Journal")
            first_row = sheet.row_values(1)
            if not first_row:
                headers = ["Date", "Symbol", "Ticker", "Qty", "BuyPrice", "ExitPrice", "ExitDate", "PnL", "Result", "Strategy"]
                sheet.append_row(headers)
            sheet.append_row(row)
            return True 
    except Exception as e:
        st.error(f"Journal Write Error: {e}")
        return False 

# --- LOAD DATA ---
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

# --- INITIALIZE SESSION STATE ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = fetch_sheet_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = fetch_sheet_data("Journal")
if 'blacklist' not in st.session_state: st.session_state.blacklist = []
if 'notifications' not in st.session_state: st.session_state.notifications = []

# MIDNIGHT RESET
if 'last_run_date' not in st.session_state:
    st.session_state.last_run_date = today_str
    st.session_state.signal_history = load_signals_from_cloud()
    st.session_state.blacklist = [] 
    st.session_state.notifications = []

if st.session_state.last_run_date != today_str:
    st.session_state.last_run_date = today_str
    st.session_state.signal_history = load_signals_from_cloud()
    st.session_state.blacklist = [] 
    st.session_state.notifications = []

# --- 3. INDICATORS ---
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

# --- 4. DATA FETCHING ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def get_market_data():
    try:
        if now.time() < datetime.time(9, 0): return pd.DataFrame(), pd.DataFrame()
        data = yf.download(TICKERS + ["^NSEI"], period="1y", threads=False, progress=False)
        return data['Close'], data['Volume']
    except: return pd.DataFrame(), pd.DataFrame()

# --- 5. HEADER & MARKET MOOD ---
closes, volumes = get_market_data()
is_market_bullish = True 
market_status_msg = "⚪ MARKET DATA LOADING..."

if not closes.empty and '^NSEI' in closes.columns:
    nifty_closes = closes['^NSEI'].dropna()
    if not nifty_closes.empty:
        nifty_sma20 = nifty_closes.rolling(20).mean().iloc[-1]
        nifty_curr = nifty_closes.iloc[-1]
        is_market_bullish = nifty_curr > nifty_sma20
        market_status_msg = f"🟢 MARKET MOOD: BULLISH" if is_market_bullish else f"🔴 MARKET MOOD: BEARISH (Buying Paused)"
else:
    if now.time() < datetime.time(9, 15): market_status_msg = "🌙 PRE-MARKET: Waiting for 9:15 AM..."
    else: market_status_msg = "⚠️ NIFTY DATA ERROR (Running Safe Mode)"

c1, c2 = st.columns([3, 1])
with c1:
    st.title("☁️ Elite Quant Terminal")
    if st.session_state.db_connected: st.caption("✅ Cloud Database: Connected")
    else: st.caption("🚫 Cloud Database: DISCONNECTED (Trading Disabled)")
    
    if "BULLISH" in market_status_msg: st.success(market_status_msg)
    elif "BEARISH" in market_status_msg: st.error(market_status_msg)
    elif "PRE-MARKET" in market_status_msg: st.info(market_status_msg)
    else: st.warning(market_status_msg)

with c2:
    status_emoji = "🟢" if is_market_active else "🔴"
    st.metric("Market Time (IST)", f"{now.strftime('%H:%M:%S')}", f"{status_emoji} {'OPEN' if is_market_active else 'CLOSED'}")

# INDICES TICKER
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

# --- 6. SIDEBAR & NOTIFICATIONS ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    mode = st.radio("Strategy Mode:", ["🛡️ Swing (Sentinel)", "🎯 Scalp (Sniper)"])
    st.divider()
    
    st.subheader("🤖 Auto-Bot")
    if st.session_state.db_connected:
        bot_active = st.checkbox("Enable Auto-Buying", value=False)
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

# --- 7. TABS ---
tab1, tab2, tab3 = st.tabs(["🔍 Market Scanner", "💼 Active Portfolio", "📊 Performance Audit"])

# --- TAB 1: SCANNER ---
with tab1:
    scan_placeholder = st.empty()
    try:
        scan_results = []
        nifty_perf = 0.0
        if not closes.empty and '^NSEI' in closes.columns:
             nifty_closes = closes['^NSEI'].dropna()
             if not nifty_closes.empty and len(nifty_closes) > 60:
                nifty_perf = nifty_closes.iloc[-1] / nifty_closes.iloc[-60]

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
                
                # --- STRATEGY ENGINE ---
                if mode == "🛡️ Swing (Sentinel)":
                    high_5d = series.tail(6).iloc[:-1].max()
                    sma200 = series.rolling(200).mean().iloc[-1]
                    if len(series) > 60: stock_perf = series.iloc[-1] / series.iloc[-60]
                    else: stock_perf = 0
                    trigger_price = high_5d
                    if curr_price > high_5d and curr_price > sma200 and stock_perf > nifty_perf:
                        if is_market_bullish: status = "🎯 CONFIRMED"
                        else: status = "⛔ MKT WEAK"
                else: 
                    bb_w = calculate_bollinger_width(series).iloc[-1]
                    rsi = calculate_rsi(series).iloc[-1]
                    vol_ma = vol_series.rolling(20).mean().iloc[-1]
                    if bb_w < 0.10: status = "👀 WATCH (Squeeze)"
                    elif (vol_series.iloc[-1] > vol_ma * 1.5) and rsi > 55:
                        status = "🚀 BREAKOUT"
                        trigger_price = curr_price

                gap_pct = ((curr_price - trigger_price) / trigger_price) * 100 if trigger_price > 0 else 0
                
                if status in ["🎯 CONFIRMED", "🚀 BREAKOUT"]:
                    active_symbols_now.append(symbol)
                    if now.time() >= datetime.time(9, 15):
                        if symbol not in st.session_state.signal_history:
                            current_time_str = now.strftime("%H:%M")
                            st.session_state.signal_history[symbol] = current_time_str
                            log_signal_cloud(symbol, current_time_str)
                    
                    if symbol in st.session_state.signal_history:
                        signal_time = st.session_state.signal_history[symbol]
                        start_time_obj = datetime.datetime.strptime(signal_time, "%H:%M").time()
                        cutoff_start = datetime.time(10, 0)
                        cutoff_now = datetime.time(15, 0)
                        if now.time() >= cutoff_now and start_time_obj <= cutoff_start:
                            if curr_vol > vol_sma20: status = "✅ STRONG BUY"
                            else: status = "⚠️ LOW VOL"

                scan_results.append({
                    "Stock": symbol,
                    "Status": status,
                    "Signal Time": signal_time,
                    "Price": round(curr_price, 2),
                    "Entry": round(trigger_price, 2),
                    "Vol vs Avg": f"{(curr_vol/vol_sma20)*100:.0f}%" if vol_sma20 > 0 else "0%",
                    "Gap %": f"{gap_pct:.1f}%"
                })
                
                # AUTO-BUY LOGIC
                if bot_active and status in ["🎯 CONFIRMED", "🚀 BREAKOUT", "✅ STRONG BUY"]:
                    current_holdings = [x['Symbol'] for x in st.session_state.portfolio]
                    if symbol not in current_holdings and symbol not in st.session_state.blacklist:
                        new_trade = {
                            "Date": now.strftime("%Y-%m-%d"), "Symbol": symbol, "Ticker": ticker,
                            "Qty": 1, "BuyPrice": curr_price,
                            "StopPrice": curr_price * (1 - (risk_per_trade/100)), "Strategy": mode
                        }
                        st.session_state.portfolio.append(new_trade)
                        save_portfolio_cloud(st.session_state.portfolio)
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
            
            # Hide WAIT stocks unless explicitly wanted (can add toggle back if needed)
            df_scan = df_scan[df_scan['Status'] != '⏳ WAIT']
            scan_placeholder.dataframe(df_scan.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
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
        
        for i, trade in enumerate(st.session_state.portfolio):
            try:
                if len(tickers) > 1 and not live_data.empty: price = live_data[trade['Ticker']].dropna().iloc[-1]
                elif not live_data.empty: price = live_data.dropna().iloc[-1]
                else: price = trade['BuyPrice']
                if pd.isna(price): price = trade['BuyPrice']
            except: price = trade['BuyPrice']
            
            qty = int(trade['Qty'])
            buy = float(trade['BuyPrice'])
            sl = float(trade['StopPrice'])
            
            cur_val = price * qty
            inv_val = buy * qty
            pnl = cur_val - inv_val
            pnl_pct = (pnl / inv_val) * 100
            
            total_val += cur_val
            total_inv += inv_val
            
            msg, new_sl = "", sl
            
            # Trailing Stop Loss Logic
            if pnl_pct > 3.0 and sl < buy:
                new_sl = buy
                msg = "🛡️ RISK FREE"
            elif pnl_pct > 5.0:
                trail = price * 0.98
                if trail > sl:
                    new_sl = trail
                    msg = "📈 TRAILING"
            
            if price <= new_sl: msg = "❌ STOP HIT"
            
            if new_sl != sl:
                trade['StopPrice'] = round(new_sl, 2)
                portfolio_changed = True
            
            # --- AUTO-SELL EXECUTION ---
            if auto_sell and price <= new_sl:
                closed_trade = trade.copy()
                closed_trade.update({'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 'PnL': pnl, 'Result': "WIN" if pnl > 0 else "LOSS"})
                
                if log_trade_journal(closed_trade):
                    st.session_state.notifications.append(f"🛑 {now.strftime('%H:%M')} - AUTO-SOLD: {trade['Symbol']} hit SL at ₹{price:.2f}")
                    st.session_state.journal.append(closed_trade)
                    st.session_state.blacklist.append(trade['Symbol'])
                    portfolio_changed = True
                    continue # Skips adding to remaining_stocks (effectively deleting it)
                else:
                    st.error(f"⚠️ Failed to auto-sell {trade['Symbol']} due to Cloud Error.")

            remaining_stocks.append(trade)
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**{trade['Symbol']}**")
            c2.write(f"Entry: {buy:.2f}")
            c3.metric("LTP", f"{price:.2f}", f"{pnl_pct:.2f}%")
            c4.metric("Stop Loss", f"{new_sl:.2f}", help="Auto-Managed")
            
            # MANUAL CLOSE BUTTON (Backup)
            if c5.button(f"✅ CLOSE {msg}", key=f"close_{trade['Symbol']}"):
                closed_trade = trade.copy()
                closed_trade.update({'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 'PnL': pnl, 'Result': "WIN" if pnl > 0 else "LOSS"})
                
                if log_trade_journal(closed_trade):
                    st.session_state.notifications.append(f"👤 {now.strftime('%H:%M')} - MANUALLY CLOSED: {trade['Symbol']} at ₹{price:.2f}")
                    st.session_state.blacklist.append(trade['Symbol'])
                    st.session_state.journal.append(closed_trade)
                    # We need to remove the stock we just appended to remaining_stocks above
                    remaining_stocks.remove(trade) 
                    portfolio_changed = True
                else:
                    st.error("⚠️ INTERNET ERROR: Trade NOT closed! Please click CLOSE again.")
        
        if portfolio_changed:
            st.session_state.portfolio = remaining_stocks
            save_portfolio_cloud(st.session_state.portfolio)
            st.rerun()

        st.divider()
        if total_inv > 0:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Invested", f"₹{total_inv:,.0f}")
            m2.metric("Current Value", f"₹{total_val:,.0f}")
            m3.metric("Total P&L", f"₹{(total_val-total_inv):,.0f}", f"{((total_val-total_inv)/total_inv)*100:.2f}%")
    else: st.info("Portfolio Empty. Go to Scanner to find stocks.")

# --- TAB 3: ANALYSIS ---
with tab3:
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        df_j['PnL'] = pd.to_numeric(df_j['PnL'], errors='coerce').fillna(0)
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
        else: st.info("No valid trades found in Journal.")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.write("🏆 **Top Winners**")
            winners = df_j[df_j['PnL'] > 0]
            if not winners.empty:
                st.dataframe(winners.nlargest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
            else: st.write("No wins yet.")
            
        with c2:
            st.write("⚠️ **Top Losers**")
            losers = df_j[df_j['PnL'] < 0]
            if not losers.empty:
                st.dataframe(losers.nsmallest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
            else: st.write("No losses yet.")
    else: st.info("Journal Empty. Close trades to see analysis.")
