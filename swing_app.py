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

market_open = datetime.time(9, 15)
market_close = datetime.time(15, 30)
# Market is active if Weekday (0-4) AND Time is within trading hours
is_market_active = (now.weekday() < 5) and (market_open <= now.time() < market_close)

# AUTO-REFRESH (30s during market, 60s otherwise)
st_autorefresh(interval=30000 if is_market_active else 60000, key="quant_refresh_v3")

# --- 2. GOOGLE SHEETS DATABASE ENGINE ---
@st.cache_resource
def init_google_sheet():
    """Initialize connection to Google Sheets with caching"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client

def fetch_sheet_data(tab_name):
    """Safely fetch all records from a specific tab"""
    try:
        client = init_google_sheet()
        sheet = client.open("Swing_Trading_DB").worksheet(tab_name)
        return sheet.get_all_records()
    except Exception as e:
        return []

def save_portfolio_cloud(data):
    """Save Active Portfolio to Cloud (Overwrites Tab)"""
    try:
        client = init_google_sheet()
        sheet = client.open("Swing_Trading_DB").worksheet("Portfolio")
        sheet.clear()
        
        # If data exists, write it. If empty, just clear (or write headers if preferred)
        if len(data) > 0:
            df = pd.DataFrame(data)
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
        else:
            # OPTIONAL: Write headers to keep sheet structure if empty
            headers = ["Date", "Symbol", "Ticker", "Qty", "BuyPrice", "StopPrice", "Strategy"]
            sheet.append_row(headers)
            
    except Exception as e:
        st.error(f"⚠️ Cloud Save Error: {e}")

def log_trade_journal(trade):
    """Append a closed trade to the Journal Tab"""
    try:
        client = init_google_sheet()
        sheet = client.open("Swing_Trading_DB").worksheet("Journal")
        
        # Enforce Column Order for Safety
        row = [
            trade.get("Date", ""),
            trade.get("Symbol", ""),
            trade.get("Ticker", ""),
            trade.get("Qty", 0),
            trade.get("BuyPrice", 0.0),
            trade.get("ExitPrice", 0.0),
            trade.get("ExitDate", ""),
            trade.get("PnL", 0.0),
            trade.get("Result", ""),
            trade.get("Strategy", "")
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"⚠️ Journal Log Error: {e}")

# INITIALIZE SESSION STATE
if 'portfolio' not in st.session_state: st.session_state.portfolio = fetch_sheet_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = fetch_sheet_data("Journal")
if 'alert_log' not in st.session_state: st.session_state.alert_log = {} 

# --- 3. TECHNICAL INDICATORS ---
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

# --- 4. DASHBOARD HEADER ---
st.title("☁️ Elite Quant Terminal")
st.caption(f"⚡ Live Connection: Google Sheet 'Swing_Trading_DB' | 🕒 {now.strftime('%H:%M:%S')}")

# MARKET INDICES DISPLAY
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
cols = st.columns(len(indices) + 1)
for i, (name, ticker) in enumerate(indices.items()):
    try:
        # Threads=False prevents Streamlit Cloud crashes
        df = yf.Ticker(ticker).history(period="5d")
        if not df.empty:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct = ((curr - prev) / prev) * 100
            cols[i].metric(name, f"{curr:,.0f}", f"{pct:+.2f}%")
        else:
            cols[i].metric(name, "0", "0%")
    except: cols[i].metric(name, "-", "-")

status_color = "🟢" if is_market_active else "🔴"
cols[-1].metric("Market Status", "OPEN" if is_market_active else "CLOSED", status_color)
st.divider()

# --- 5. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    
    # Strategy Selection
    mode = st.radio("Strategy Mode:", ["🛡️ Swing (Sentinel)", "🎯 Scalp (Sniper)"])
    
    # Bot Settings
    st.divider()
    st.subheader("🤖 Auto-Bot")
    bot_active = st.checkbox("Enable Auto-Trading", value=False)
    risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.5)
    
    # Manual Sync
    st.divider()
    if st.button("💾 Force Save to Cloud"):
        save_portfolio_cloud(st.session_state.portfolio)
        st.success("✅ Database Synced!")
    
    # Debug Tools
    with st.expander("🔧 Diagnostics"):
        show_all = st.checkbox("Show All Scanner Results", value=True)
        if st.button("Test DB Connection"):
            try:
                init_google_sheet().open("Swing_Trading_DB")
                st.success("✅ Google Sheets Connected")
            except Exception as e:
                st.error(f"❌ Failed: {e}")

# --- 6. DATA FETCHING ENGINE ---
# NIFTY 50 TICKERS
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def get_market_data():
    """Fetch OHLCV data for all tickers efficiently"""
    # Bulk download is faster and uses fewer API calls
    data = yf.download(TICKERS + ["^NSEI"], period="1y", threads=False, progress=False)
    return data['Close'], data['Volume']

# --- 7. MAIN INTERFACE TABS ---
tab1, tab2, tab3 = st.tabs(["🔍 Market Scanner", "💼 Active Portfolio", "📊 Performance Audit"])

# --- TAB 1: SCANNER ---
with tab1:
    scan_placeholder = st.empty()
    try:
        closes, volumes = get_market_data()
        scan_results = []
        
        # Benchmark Performance (Relative Strength)
        nifty_closes = closes['^NSEI'].dropna()
        nifty_perf = nifty_closes.iloc[-1] / nifty_closes.iloc[-60] # 3-month performance

        for ticker in TICKERS:
            try:
                # Prepare Data
                series = closes[ticker].dropna()
                vol_series = volumes[ticker].dropna()
                if series.empty: continue
                
                curr_price = series.iloc[-1]
                
                # --- STRATEGY LOGIC ---
                status, trigger_price = "WAIT", 0.0
                
                if mode == "🛡️ Swing (Sentinel)":
                    # Logic: 5-Day High Breakout + Relative Strength + Above 200 SMA
                    sma200 = series.rolling(200).mean().iloc[-1]
                    high_5d = series.tail(6).iloc[:-1].max()
                    stock_perf = series.iloc[-1] / series.iloc[-60]
                    
                    trigger_price = high_5d
                    if curr_price > high_5d and curr_price > sma200 and stock_perf > nifty_perf:
                        status = "BUY SIGNAL"
                
                else: # Sniper Mode
                    # Logic: Bollinger Squeeze + Volume Spike + RSI Momentum
                    bb_w = calculate_bollinger_width(series).iloc[-1]
                    rsi = calculate_rsi(series).iloc[-1]
                    vol_ma = vol_series.rolling(20).mean().iloc[-1]
                    
                    if bb_w < 0.10: status = "SQUEEZE (Watch)"
                    elif (vol_series.iloc[-1] > vol_ma * 1.5) and rsi > 55:
                        status = "BREAKOUT"
                        trigger_price = curr_price

                # --- RESULT PROCESSING ---
                gap_pct = ((curr_price - trigger_price) / trigger_price) * 100 if trigger_price > 0 else 0
                
                if show_all or status not in ["WAIT", "SQUEEZE (Watch)"]:
                    scan_results.append({
                        "Stock": ticker.replace(".NS", ""),
                        "Status": status,
                        "Price": round(curr_price, 2),
                        "Trigger": round(trigger_price, 2),
                        "Gap %": f"{gap_pct:.1f}%"
                    })
                
                # --- AUTO-BOT EXECUTION ---
                if bot_active and status in ["BUY SIGNAL", "BREAKOUT"]:
                    # Check if we already own it
                    current_holdings = [x['Symbol'] for x in st.session_state.portfolio]
                    symbol = ticker.replace(".NS", "")
                    
                    if symbol not in current_holdings:
                        new_trade = {
                            "Date": now.strftime("%Y-%m-%d"),
                            "Symbol": symbol,
                            "Ticker": ticker,
                            "Qty": 1, # Default Qty
                            "BuyPrice": curr_price,
                            "StopPrice": curr_price * (1 - (risk_per_trade/100)),
                            "Strategy": mode
                        }
                        st.session_state.portfolio.append(new_trade)
                        save_portfolio_cloud(st.session_state.portfolio)
                        st.toast(f"🤖 Bot Bought: {symbol} at {curr_price}")
                        
            except: continue
        
        # Display Results
        if scan_results:
            df_scan = pd.DataFrame(scan_results)
            # Sort: Buy Signals -> Breakouts -> Watch -> Wait
            sort_map = {"BUY SIGNAL": 0, "BREAKOUT": 1, "SQUEEZE (Watch)": 2, "WAIT": 3}
            df_scan['Sort'] = df_scan['Status'].map(sort_map)
            df_scan = df_scan.sort_values('Sort').drop('Sort', axis=1)
            scan_placeholder.dataframe(df_scan, use_container_width=True, hide_index=True)
        else:
            scan_placeholder.info("System Scanning... No signals found yet.")
            
    except Exception as e:
        scan_placeholder.error(f"Scanner Error: {e}")

# --- TAB 2: PORTFOLIO ---
with tab2:
    if st.session_state.portfolio:
        # Fetch Live Prices for Portfolio
        tickers = [p['Ticker'] for p in st.session_state.portfolio]
        live_data = yf.download(tickers, period="1d", interval="1m", threads=False, progress=False)['Close']
        
        total_value = 0
        total_invested = 0
        
        # --- PORTFOLIO LOOP ---
        for i, trade in enumerate(st.session_state.portfolio):
            # Get Current Price Safely
            try:
                if len(tickers) > 1: price = live_data[trade['Ticker']].dropna().iloc[-1]
                else: price = live_data.dropna().iloc[-1]
            except: price = trade['BuyPrice'] # Fallback if fetch fails
            
            qty = int(trade['Qty'])
            buy_price = float(trade['BuyPrice'])
            stop_price = float(trade['StopPrice'])
            
            # P&L Calculation
            cur_val = price * qty
            inv_val = buy_price * qty
            pnl = cur_val - inv_val
            pnl_pct = (pnl / inv_val) * 100
            
            total_value += cur_val
            total_invested += inv_val
            
            # --- SMART EXIT LOGIC ---
            status_msg = ""
            new_sl = stop_price
            
            # 1. Breakeven Rule (Risk Free at +3%)
            if pnl_pct > 3.0 and stop_price < buy_price:
                new_sl = buy_price
                status_msg = "🛡️ RISK FREE"
                
            # 2. Trailing Stop Rule (Trail at +5%)
            elif pnl_pct > 5.0:
                trail = price * 0.98 # 2% Trail
                if trail > stop_price:
                    new_sl = trail
                    status_msg = "📈 TRAILING"
            
            # 3. Stop Hit Rule
            if price < new_sl:
                status_msg = "❌ STOP HIT"
            
            # Update Stop Loss in Memory if Changed
            if new_sl != stop_price:
                st.session_state.portfolio[i]['StopPrice'] = round(new_sl, 2)
                save_portfolio_cloud(st.session_state.portfolio) # Auto-Save Trailing Stop
            
            # --- ROW DISPLAY ---
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**{trade['Symbol']}**")
            c2.write(f"Entry: {buy_price:.2f}")
            c3.metric("LTP", f"{price:.2f}", f"{pnl_pct:.2f}%")
            c4.metric("Stop Loss", f"{new_sl:.2f}", help="Auto-Managed by System")
            
            if c5.button(f"✅ CLOSE {status_msg}", key=f"btn_close_{i}"):
                # Create Closed Trade Record
                closed_trade = trade.copy()
                closed_trade['ExitPrice'] = price
                closed_trade['ExitDate'] = now.strftime("%Y-%m-%d")
                closed_trade['PnL'] = pnl
                closed_trade['Result'] = "WIN" if pnl > 0 else "LOSS"
                
                # Execute Logic
                log_trade_journal(closed_trade)          # 1. Save to History
                st.session_state.journal.append(closed_trade)
                st.session_state.portfolio.pop(i)        # 2. Remove from Active
                save_portfolio_cloud(st.session_state.portfolio) # 3. Sync Cloud
                st.rerun()
        
        st.divider()
        # Summary Metrics
        if total_invested > 0:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Invested", f"₹{total_invested:,.0f}")
            m2.metric("Current Value", f"₹{total_value:,.0f}")
            m3.metric("Total P&L", f"₹{(total_value-total_invested):,.0f}", f"{((total_value-total_invested)/total_invested)*100:.2f}%")
        
    else:
        st.info("Portfolio is Empty. Scanner is active...")

# --- TAB 3: ANALYSIS ---
with tab3:
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        df_j['PnL'] = pd.to_numeric(df_j['PnL'])
        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'])
        
        st.header("📈 Strategy Audit")
        
        # 1. Weekly Analysis
        st.subheader("Weekly Performance")
        current_week = df_j[df_j['ExitDate'] > (pd.Timestamp(now) - pd.Timedelta(days=7))]
        
        if not current_week.empty:
            total_pnl = current_week['PnL'].sum()
            win_count = len(current_week[current_week['PnL'] > 0])
            total_count = len(current_week)
            win_rate = (win_count / total_count) * 100
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Net Profit (7D)", f"₹{total_pnl:,.2f}")
            k2.metric("Trades Taken", total_count)
            k3.metric("Win Rate", f"{win_rate:.1f}%")
            
            st.bar_chart(current_week, x="Symbol", y="PnL")
        else:
            st.info("No trades closed in the last 7 days.")
            
        st.divider()
        
        # 2. Heroes & Villains
        c1, c2 = st.columns(2)
        with c1:
            st.write("🏆 **Top Winners**")
            if not df_j.empty:
                st.dataframe(df_j.nlargest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
        with c2:
            st.write("⚠️ **Top Losers**")
            if not df_j.empty:
                st.dataframe(df_j.nsmallest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
            
    else:
        st.info("Journal is Empty. Close trades to generate analysis.")
