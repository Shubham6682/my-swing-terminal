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
is_market_active = (now.weekday() < 5) and (market_open <= now.time() < market_close)

# AUTO-REFRESH
st_autorefresh(interval=30000 if is_market_active else 60000, key="quant_refresh_pro_v3")

# --- 2. GOOGLE SHEETS DATABASE ENGINE ---
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
        if client: return client.open("Swing_Trading_DB").worksheet(tab_name).get_all_records()
    except: return []
    return []

def save_portfolio_cloud(data):
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
    except Exception as e: st.error(f"Cloud Save Error: {e}")

def log_trade_journal(trade):
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Journal")
            row = [
                trade.get("Date", ""), trade.get("Symbol", ""), trade.get("Ticker", ""),
                trade.get("Qty", 0), trade.get("BuyPrice", 0.0), trade.get("ExitPrice", 0.0),
                trade.get("ExitDate", ""), trade.get("PnL", 0.0), trade.get("Result", ""),
                trade.get("Strategy", "")
            ]
            sheet.append_row(row)
    except Exception as e: st.error(f"Journal Log Error: {e}")

# INITIALIZE SESSION STATE
if 'portfolio' not in st.session_state: st.session_state.portfolio = fetch_sheet_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = fetch_sheet_data("Journal")
if 'signal_history' not in st.session_state: st.session_state.signal_history = {}

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
    data = yf.download(TICKERS + ["^NSEI"], period="1y", threads=False, progress=False)
    return data['Close'], data['Volume']

# --- 5. HEADER & MARKET MOOD ---
closes, volumes = get_market_data()
nifty_closes = closes['^NSEI'].dropna()

# MARKET MOOD CALCULATION
nifty_sma20 = nifty_closes.rolling(20).mean().iloc[-1]
nifty_curr = nifty_closes.iloc[-1]
is_market_bullish = nifty_curr > nifty_sma20

c1, c2 = st.columns([3, 1])
with c1:
    st.title("☁️ Elite Quant Terminal")
    if is_market_bullish:
        st.success(f"🟢 MARKET MOOD: BULLISH (Nifty > 20 SMA)")
    else:
        st.error(f"🔴 MARKET MOOD: BEARISH (Nifty < 20 SMA) - Buying Paused")

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

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    mode = st.radio("Strategy Mode:", ["🛡️ Swing (Sentinel)", "🎯 Scalp (Sniper)"])
    st.divider()
    st.subheader("🤖 Auto-Bot")
    bot_active = st.checkbox("Enable Auto-Trading", value=False)
    risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.5)
    st.divider()
    if st.button("💾 Force Save to Cloud"):
        save_portfolio_cloud(st.session_state.portfolio)
        st.success("Synced!")
    with st.expander("🔧 Diagnostics"):
        show_all = st.checkbox("Show 'WAIT' Stocks", value=True) 
        if st.button("Test DB Connection"):
            if init_google_sheet(): st.success("✅ Connected")
            else: st.error("❌ Failed")

# --- 7. TABS ---
tab1, tab2, tab3 = st.tabs(["🔍 Market Scanner", "💼 Active Portfolio", "📊 Performance Audit"])

# --- TAB 1: SCANNER ---
with tab1:
    scan_placeholder = st.empty()
    try:
        scan_results = []
        nifty_perf = nifty_closes.iloc[-1] / nifty_closes.iloc[-60]
        active_signals = []

        for ticker in TICKERS:
            try:
                series = closes[ticker].dropna()
                vol_series = volumes[ticker].dropna()
                if series.empty: continue
                
                curr_price = series.iloc[-1]
                curr_vol = vol_series.iloc[-1]
                vol_sma20 = vol_series.rolling(20).mean().iloc[-1]
                
                status, trigger_price = "⏳ WAIT", 0.0
                symbol = ticker.replace(".NS", "")
                
                # --- STRATEGY ENGINE ---
                if mode == "🛡️ Swing (Sentinel)":
                    high_5d = series.tail(6).iloc[:-1].max()
                    sma200 = series.rolling(200).mean().iloc[-1]
                    stock_perf = series.iloc[-1] / series.iloc[-60]
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
                
                # --- SIGNAL TIMING & VOLUME ---
                signal_time = "-"
                if status in ["🎯 CONFIRMED", "🚀 BREAKOUT"]:
                    active_signals.append(symbol)
                    if symbol not in st.session_state.signal_history:
                        st.session_state.signal_history[symbol] = now.strftime("%H:%M")
                    signal_time = st.session_state.signal_history[symbol]
                    
                    start_time_obj = datetime.datetime.strptime(signal_time, "%H:%M").time()
                    cutoff_start = datetime.time(10, 0)
                    cutoff_now = datetime.time(15, 0)
                    
                    if now.time() >= cutoff_now and start_time_obj <= cutoff_start:
                        if curr_vol > vol_sma20: status = "✅ STRONG BUY"
                        else: status = "⚠️ LOW VOL"

                # APPEND RESULTS (WITH ENTRY PRICE ADDED BACK)
                if show_all or status not in ["⏳ WAIT"]:
                    scan_results.append({
                        "Stock": symbol,
                        "Status": status,
                        "Signal Time": signal_time,
                        "Price": round(curr_price, 2),
                        "Entry": round(trigger_price, 2), # ADDED BACK HERE
                        "Vol vs Avg": f"{(curr_vol/vol_sma20)*100:.0f}%",
                        "Gap %": f"{gap_pct:.1f}%"
                    })
                
                # BOT LOGIC
                if bot_active and status in ["🎯 CONFIRMED", "🚀 BREAKOUT", "✅ STRONG BUY"]:
                    current_holdings = [x['Symbol'] for x in st.session_state.portfolio]
                    if symbol not in current_holdings:
                        new_trade = {
                            "Date": now.strftime("%Y-%m-%d"), "Symbol": symbol, "Ticker": ticker,
                            "Qty": 1, "BuyPrice": curr_price,
                            "StopPrice": curr_price * (1 - (risk_per_trade/100)), "Strategy": mode
                        }
                        st.session_state.portfolio.append(new_trade)
                        save_portfolio_cloud(st.session_state.portfolio)
                        st.toast(f"🤖 Bot Bought: {symbol}")
            except: continue
        
        # CLEANUP
        for s in list(st.session_state.signal_history.keys()):
            if s not in active_signals:
                del st.session_state.signal_history[s]

        # DISPLAY TABLE
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

            scan_placeholder.dataframe(df_scan.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
        else:
            scan_placeholder.info("Scanner Active. No signals found yet.")
            
    except Exception as e:
        scan_placeholder.error(f"Scanner Error: {e}")

# --- TAB 2: PORTFOLIO ---
with tab2:
    if st.session_state.portfolio:
        tickers = [p['Ticker'] for p in st.session_state.portfolio]
        live_data = yf.download(tickers, period="1d", interval="1m", threads=False, progress=False)['Close']
        
        total_val, total_inv = 0, 0
        
        for i, trade in enumerate(st.session_state.portfolio):
            try:
                if len(tickers) > 1: price = live_data[trade['Ticker']].dropna().iloc[-1]
                else: price = live_data.dropna().iloc[-1]
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
            if pnl_pct > 3.0 and sl < buy:
                new_sl = buy
                msg = "🛡️ RISK FREE"
            elif pnl_pct > 5.0:
                trail = price * 0.98
                if trail > sl:
                    new_sl = trail
                    msg = "📈 TRAILING"
            
            if price < new_sl: msg = "❌ STOP HIT"
            
            if new_sl != sl:
                st.session_state.portfolio[i]['StopPrice'] = round(new_sl, 2)
                save_portfolio_cloud(st.session_state.portfolio)
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**{trade['Symbol']}**")
            c2.write(f"Entry: {buy:.2f}")
            c3.metric("LTP", f"{price:.2f}", f"{pnl_pct:.2f}%")
            c4.metric("Stop Loss", f"{new_sl:.2f}", help="Auto-Managed")
            
            if c5.button(f"✅ CLOSE {msg}", key=f"close_{i}"):
                closed_trade = trade.copy()
                closed_trade.update({'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 'PnL': pnl, 'Result': "WIN" if pnl > 0 else "LOSS"})
                log_trade_journal(closed_trade)
                st.session_state.journal.append(closed_trade)
                st.session_state.portfolio.pop(i)
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
        df_j['PnL'] = pd.to_numeric(df_j['PnL'])
        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'])
        
        st.subheader("Weekly Performance")
        curr_week = df_j[df_j['ExitDate'] > (pd.Timestamp(now) - pd.Timedelta(days=7))]
        
        if not curr_week.empty:
            pnl = curr_week['PnL'].sum()
            rate = (len(curr_week[curr_week['PnL'] > 0]) / len(curr_week)) * 100
            k1, k2, k3 = st.columns(3)
            k1.metric("Net Profit (7D)", f"₹{pnl:,.2f}")
            k2.metric("Trades", len(curr_week))
            k3.metric("Win Rate", f"{rate:.1f}%")
            st.bar_chart(curr_week, x="Symbol", y="PnL")
        else: st.info("No trades in last 7 days.")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.write("🏆 **Top Winners**")
            st.dataframe(df_j.nlargest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
        with c2:
            st.write("⚠️ **Top Losers**")
            st.dataframe(df_j.nsmallest(5, 'PnL')[['Symbol', 'PnL', 'Strategy']], hide_index=True)
    else: st.info("Journal Empty. Close trades to see analysis.")
