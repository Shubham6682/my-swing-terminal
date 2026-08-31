import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz
import time
from streamlit_autorefresh import st_autorefresh
from analysis import run_advanced_audit
from ghost_dashboard import render_ghost_portfolio  

# 🟢 THE MODULAR IMPORTS (Updated to include V3)
from ai_core import load_ai_brain, ask_ai_gatekeeper, load_v3_brain, ask_v3_challenger
from indicators import calculate_rsi, calculate_bollinger_width
from database import init_google_sheet, fetch_sheet_data, save_portfolio_cloud, log_trade_journal, log_ai_veto, log_signal_cloud, load_signals_from_cloud, sync_ghost_labels_to_cloud
from agent_interceptor import evaluate_and_log_shadow_trade, auto_grade_shadow_log, fetch_todays_shadow_log
from vision_analyzer import evaluate_and_log_vision_trade

# --- 1. SYSTEM CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(page_title="Elite Quant Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")

# 🟢 LOAD BOTH BRAINS INTO MEMORY
ai_model = load_ai_brain()
v3_model = load_v3_brain()

market_open = datetime.time(9, 15)
market_close = datetime.time(15, 30)
is_market_active = (now.weekday() < 5) and (market_open <= now.time() < market_close)

if is_market_active:
    st_autorefresh(interval=300000, key="quant_v18_active_only")
else:
    st.info("🌙 Market is Closed. Auto-refresh is paused to save resources.")

if 'db_connected' not in st.session_state: st.session_state.db_connected = False

# --- 3. SESSION STATE ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = fetch_sheet_data("Portfolio")
if 'journal' not in st.session_state: st.session_state.journal = fetch_sheet_data("Journal")
if 'blacklist' not in st.session_state: st.session_state.blacklist = []
if 'notifications' not in st.session_state: st.session_state.notifications = []
if 'vetoed_today' not in st.session_state: st.session_state.vetoed_today = [] # 🟢 VULNERABILITY 2: Memory Bank added
if 'shadow_logged_today' not in st.session_state: st.session_state.shadow_logged_today = []
if 'vision_logged_today' not in st.session_state: st.session_state.vision_logged_today = [] # 🟢 NEW VISION MEMORY

# Reset everything if it is a new day
if 'last_run_date' not in st.session_state or st.session_state.last_run_date != today_str:
    st.session_state.last_run_date = today_str
    st.session_state.signal_history = load_signals_from_cloud()
    st.session_state.blacklist = []
    st.session_state.notifications = []
    st.session_state.vetoed_today = []
    st.session_state.vision_logged_today = [] # 🟢 NEW VISION RESET
    
    # 🟢 SEED THE MEMORY BANK FROM GOOGLE SHEETS
    if st.session_state.db_connected:
        try:
            sheet_id = st.secrets["gcp_service_account"]["sheet_id"]
            # 1. Fetch memory of what was already logged today (Agentic Log)
            st.session_state.shadow_logged_today = fetch_todays_shadow_log(sheet_id)
            
            # 🟢 FIX 2: Clone the Agentic cloud memory to the Vision AI so it survives page reloads!
            st.session_state.vision_logged_today = list(st.session_state.shadow_logged_today)
            
            # 2. Run the morning grader
            auto_grade_shadow_log(sheet_id)
        except Exception as e:
            st.session_state.shadow_logged_today = []
            st.session_state.vision_logged_today = [] # 🟢 Keep synced on error
    else:
        st.session_state.shadow_logged_today = []
        st.session_state.vision_logged_today = [] # 🟢 Keep synced offline

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
        
    risk_per_trade = st.slider("Swing Risk (%)", 1.0, 8.0, 3.0)
    
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

    st.divider()
    st.subheader("🛠️ Emergency API Override")
    use_manual_nifty = st.checkbox("Force Manual Nifty Data", help="Check this if yfinance is frozen or showing old dates.")
    manual_intraday = st.number_input("Enter Live Nifty % (e.g., -0.45)", value=0.00, step=0.05)
    manual_5d = st.number_input("Enter 5-Day Nifty % (e.g., -2.10)", value=0.00, step=0.05)

# --- 5. MARKET DATA & SHIELD ---
NIFTY_50 = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"]
TICKERS = [f"{t}.NS" for t in NIFTY_50]

@st.cache_data(ttl=60)
def get_market_data():
    try:
        # 🟢 FIX 1: Extracted 'Open' prices to fix the Wick Math vulnerabilities globally
        if now.time() < datetime.time(9, 0): return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        data = yf.download(TICKERS + ["^NSEI", "^INDIAVIX"], period="1y", threads=False, progress=False)
        return data['Close'], data['Volume'], data['High'], data['Open']
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

closes, volumes, highs, opens = get_market_data()

nifty_5d_trend = 0.0  
intraday_pct = 0.0    
is_safe_to_buy = False
market_status_msg = "⚪ MARKET DATA LOADING..."

if use_manual_nifty:
    intraday_pct = float(manual_intraday)
    nifty_5d_trend = float(manual_5d)
    is_bleeding = intraday_pct < -0.3
    is_macro_bullish = True 
    is_safe_to_buy = not is_bleeding
    if is_bleeding: market_status_msg = f"🔴 MANUAL OVERRIDE: Nifty Bleeding ({intraday_pct:.2f}%) - Buying Halted"
    else: market_status_msg = f"⚠️ MANUAL OVERRIDE ACTIVE: Intraday {intraday_pct}%, 5-Day {nifty_5d_trend}%"

elif not closes.empty and '^NSEI' in closes.columns:
    nifty_closes = closes['^NSEI'].dropna()
    if len(nifty_closes) > 20:
        last_data_date = nifty_closes.index[-1].tz_localize(None).strftime("%Y-%m-%d")
        if last_data_date != today_str:
            market_status_msg = f"⚠️ API LAG: yfinance stuck on {last_data_date}. Waiting for live sync..."
            is_safe_to_buy = False 
        else:
            nifty_sma20 = nifty_closes.rolling(20).mean().iloc[-1]
            nifty_curr = nifty_closes.iloc[-1]
            nifty_prev = nifty_closes.iloc[-2]
            if len(nifty_closes) > 5:
                nifty_5d_prev = nifty_closes.iloc[-6]
                nifty_5d_trend = ((nifty_curr - nifty_5d_prev) / nifty_5d_prev) * 100
            intraday_pct = ((nifty_curr - nifty_prev) / nifty_prev) * 100
            is_macro_bullish = nifty_curr > nifty_sma20
            is_bleeding = intraday_pct < -0.3
            is_safe_to_buy = is_macro_bullish and not is_bleeding
            if is_bleeding: market_status_msg = f"🔴 CRITICAL: NIFTY BLEEDING ({intraday_pct:.2f}%). ALL BUYING HALTED."
            elif not is_macro_bullish: market_status_msg = f"🔴 MARKET MOOD: BEARISH (Below 20 SMA). Buying Paused."
            else: market_status_msg = f"🟢 MARKET MOOD: BULLISH (Up {intraday_pct:.2f}%)"
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
        # 🟢 FIX 3: Failsafe set to 999.0 so bleeding stocks do not accidentally pass the Relative Strength check during an API error
        nifty_perf = 999.0 
        
        if not closes.empty and '^NSEI' in closes.columns:
             nifty_closes = closes['^NSEI'].dropna()
             if not nifty_closes.empty and len(nifty_closes) > 60:
                nifty_perf = nifty_closes.iloc[-1] / nifty_closes.iloc[-60]
                 
        st.markdown("### 🔍 Custom Watchlist Analyzer")
        c_input = st.text_input("Type any NSE Ticker to test the math (e.g., SBIN, RVNL, SUZLON):", "").strip().upper()
        
        if c_input:
            custom_sym = c_input.replace('.NS', '')
            custom_ticker = f"{custom_sym}.NS"
            with st.spinner(f"Running quant engine on {custom_sym}..."):
                try:
                    c_data = yf.download(custom_ticker, period="1y", progress=False, threads=False)
                    # 🟢 FIX 1: Ensuring Open is pulled for Custom Ticker
                    if not c_data.empty and 'Close' in c_data.columns and 'Volume' in c_data.columns and 'Open' in c_data.columns:
                        c_closes = c_data['Close'].squeeze().dropna()
                        c_vols = c_data['Volume'].squeeze().dropna()
                        c_opens = c_data['Open'].squeeze().dropna()
                        
                        if len(c_closes) > 60:
                            c_curr_price = float(c_closes.iloc[-1])
                            c_curr_open = float(c_opens.iloc[-1]) # 🟢 Extracted
                            c_curr_vol = float(c_vols.iloc[-1])
                            c_vol_sma20 = float(c_vols.rolling(20).mean().iloc[-1])
                            c_rsi = float(calculate_rsi(c_closes).iloc[-1])
                            
                            c_status, c_trigger = "⏳ WAIT", 0.0
                            
                            # --- PHASE 1: TECHNICAL MATH ---
                            if mode == "🛡️ Swing (Sentinel)":
                                c_high_5d = c_closes.tail(6).iloc[:-1].max()
                                c_sma200_base = c_closes.rolling(200).mean().iloc[-1] if len(c_closes) >= 200 else c_curr_price
                                c_perf = c_closes.iloc[-1] / c_closes.iloc[-60]
                                c_trigger = c_high_5d
                                
                                if c_curr_price > c_high_5d and c_curr_price > c_sma200_base and c_perf > nifty_perf:
                                    c_status = "🎯 CONFIRMED" if is_safe_to_buy else "⛔ MKT WEAK"
                            else:
                                c_bb_w = calculate_bollinger_width(c_closes).iloc[-1]
                                if c_bb_w < 0.10: c_status = "👀 WATCH (Squeeze)"
                                elif (c_curr_vol > c_vol_sma20 * 1.5) and c_rsi > 55:
                                    if is_safe_to_buy: 
                                        c_status = "🚀 BREAKOUT"
                                        c_trigger = c_curr_price
                                    else: c_status = "⛔ MKT WEAK"

                            # --- PHASE 2: WAKING UP THE AI BRAIN ---
                            c_rvol = round(float(c_curr_vol / c_vol_sma20), 2) if c_vol_sma20 > 0 else 1.0
                            c_sma200_val = c_closes.rolling(200).mean().iloc[-1] if len(c_closes) >= 200 else c_curr_price
                            c_dist = round(float(((c_curr_price - c_sma200_val) / c_sma200_val) * 100), 2) if c_sma200_val > 0 else 0.0
                            c_sma20 = c_closes.rolling(20).mean().iloc[-1]
                            c_sma20_dist = round(float(((c_curr_price - c_sma20) / c_sma20) * 100), 2) if c_sma20 > 0 else 0.0
                            
                            c_highs = c_data['High'].squeeze().dropna()
                            c_daily_high = float(c_highs.iloc[-1])
                            
                            # 🟢 FIX 1: True Wick Rejection Math
                            c_candle_top = max(c_curr_price, c_curr_open)
                            c_wick_reject = round(float(((c_daily_high - c_candle_top) / c_daily_high) * 100), 2) if c_daily_high > 0 else 0.0
                            
                            c_trap_score = round((c_rvol * c_wick_reject) / (1 + abs(c_sma20_dist)), 2)
                            c_mom_vel = round(c_rsi * c_rvol, 2)
                            
                            n_trend = round(float(intraday_pct), 2)
                            c_nifty_5d = round(float(nifty_5d_trend), 2) # 🟢 Added for V3
                            try: c_vix = round(float(closes['^INDIAVIX'].dropna().iloc[-1]), 2)
                            except: c_vix = 15.0
                            
                            stock_data_for_ai = {
                                'RVol': c_rvol, 'RSI': c_rsi, 'SMA200_Dist': c_dist,
                                'SMA20_Dist': c_sma20_dist, 'Wick_Reject': c_wick_reject,
                                'Trap_Score': c_trap_score, 'Momentum_Velocity': c_mom_vel
                            }
                            # 🟢 Added Nifty_5D to macro payload
                            macro_data_for_ai = {'VIX': c_vix, 'Nifty_Trend': n_trend, 'Nifty_5D': c_nifty_5d}
                            
                            # Get the AI Verdicts from BOTH Brains
                            v2_approved, v2_confidence = ask_ai_gatekeeper(ai_model, stock_data_for_ai, macro_data_for_ai)
                            v3_approved, v3_confidence = ask_v3_challenger(v3_model, stock_data_for_ai, macro_data_for_ai)
                            
                            final_approval = v2_approved or v3_approved
                            
                            # --- UI UPDATES BASED ON AI ---
                            if c_status in ["🎯 CONFIRMED", "🚀 BREAKOUT"]:
                                if final_approval:
                                    bg_color, border_color = "#d4edda", "#28a745" 
                                else:
                                    bg_color, border_color = "#f8d7da", "#dc3545" 
                            else:
                                bg_color, border_color = "#f8f9fa", "#6c757d" 

                            vol_surge = (c_curr_vol / c_vol_sma20) * 100 if c_vol_sma20 > 0 else 0
                            
                            st.markdown(f"""
                            <div style='border: 2px solid {border_color}; border-radius: 8px; padding: 15px; background-color: {bg_color}; color: #333;'>
                                <h4 style='margin-top:0px; color: #111;'>{custom_sym} System Diagnostics</h4>
                                <b>Phase 1 Technical:</b> {c_status} &nbsp;|&nbsp; <b>LTP:</b> ₹{c_curr_price:.2f} &nbsp;|&nbsp; <b>Target:</b> ₹{c_trigger:.2f}<br>
                                <b>V2 Champion:</b> {v2_confidence:.2f}% | <b>V3 Challenger:</b> {v3_confidence:.2f}%<br>
                                <hr style='margin: 8px 0; border-top: 1px solid #ccc;'>
                                <small><b>RSI:</b> {c_rsi:.1f} &nbsp;|&nbsp; <b>Vol Surge:</b> {vol_surge:.0f}% &nbsp;|&nbsp; <b>Trap:</b> {c_trap_score} &nbsp;|&nbsp; <b>Reject:</b> {c_wick_reject}%</small>
                            </div>
                            """, unsafe_allow_html=True)
                        else: st.warning(f"Not enough historical data to calculate metrics on {custom_sym}.")
                    else: st.error("Invalid Ticker. Make sure it's an NSE stock.")
                except Exception as e: st.error(f"Error evaluating {custom_sym}: {e}")
        
        st.divider()

        active_symbols_now = []

        for ticker in TICKERS:
            try:
                if ticker not in closes.columns: continue
                series = closes[ticker].dropna()
                vol_series = volumes[ticker].dropna()
                o_series = opens[ticker].dropna() # 🟢 FIX 1: Open Prices for Scanner
                
                if series.empty: continue
                
                curr_price = series.iloc[-1]
                curr_open = o_series.iloc[-1]
                
                if pd.isna(curr_price): continue
                
                curr_vol = vol_series.iloc[-1]
                vol_sma20 = vol_series.rolling(20).mean().iloc[-1]
                
                status, trigger_price = "⏳ WAIT", 0.0
                symbol = ticker.replace(".NS", "")
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
                        else: status = "⛔ MKT WEAK"

                gap_pct = ((curr_price - trigger_price) / trigger_price) * 100 if trigger_price > 0 else 0
                signal_time = "-"
                
                n_trend = round(float(intraday_pct), 2) if 'intraday_pct' in locals() else 0.0
                c_nifty_5d = round(float(nifty_5d_trend), 2)
                
                try: c_vix = round(float(closes['^INDIAVIX'].dropna().iloc[-1]), 2)
                except: c_vix = 15.0
                
                c_rvol = round(float(curr_vol / vol_sma20), 2) if vol_sma20 > 0 else 1.0
                c_rsi = round(float(calculate_rsi(series).iloc[-1]), 2)
                c_sma200 = series.rolling(200).mean().iloc[-1]
                c_dist = round(float(((curr_price - c_sma200) / c_sma200) * 100), 2) if c_sma200 > 0 else 0.0
                c_sma20 = series.rolling(20).mean().iloc[-1]
                c_sma20_dist = round(float(((curr_price - c_sma20) / c_sma20) * 100), 2) if c_sma20 > 0 else 0.0
                daily_high = highs[ticker].dropna().iloc[-1] if not highs[ticker].dropna().empty else curr_price
                
                # 🟢 FIX 1: True Wick Rejection Math
                candle_top = max(curr_price, curr_open)
                c_wick_reject = round(float(((daily_high - candle_top) / daily_high) * 100), 2) if daily_high > 0 else 0.0

                if raw_technical_trigger:
                    active_symbols_now.append(symbol)
                    if is_market_active:
                        if symbol not in st.session_state.signal_history:
                            current_time_str = now.strftime("%H:%M")
                            st.session_state.signal_history[symbol] = current_time_str
                            log_signal_cloud(symbol, current_time_str, status, n_trend, c_vix, c_rvol, c_rsi, c_dist, c_sma20_dist, c_wick_reject, c_nifty_5d, curr_price)
                    
                if symbol in st.session_state.signal_history:
                    signal_time = st.session_state.signal_history[symbol]
                    start_time_obj = datetime.datetime.strptime(signal_time, "%H:%M").time()
                    cutoff_start = datetime.time(10, 0)
                    cutoff_now = datetime.time(15, 0)
                    
                    if now.time() >= cutoff_now and start_time_obj <= cutoff_start:
                        if raw_technical_trigger:
                            if curr_vol > vol_sma20: status = "✅ STRONG BUY" if is_safe_to_buy else "⛔ MKT WEAK"
                            else: status = "⚠️ LOW VOL"
                        else: status = "❌ FAILED SETUP"

                scan_results.append({
                    "Stock": symbol, "Status": status, "Signal Time": signal_time,
                    "Price": round(curr_price, 2), "Entry": round(trigger_price, 2),
                    "Vol vs Avg": f"{(curr_vol/vol_sma20)*100:.0f}%" if vol_sma20 > 0 else "0%",
                    "Gap %": f"{gap_pct:.1f}%"
                })
                
                is_afternoon = datetime.time(13, 30) <= now.time() < datetime.time(15, 30)
                
                # 🟢 REFACTORED CONDITION: We now let ALL raw technical triggers through so the Agent can evaluate Phantom Trades.
                if bot_active and is_afternoon and raw_technical_trigger:
                    current_holdings = [x['Symbol'] for x in st.session_state.portfolio]
                    if symbol not in current_holdings and symbol not in st.session_state.blacklist:
                        
                        # 1. Calculate the AI variables
                        c_trap_score = round((c_rvol * c_wick_reject) / (1 + abs(c_sma20_dist)), 2)
                        c_mom_vel = round(c_rsi * c_rvol, 2)

                        stock_data_for_ai = {
                            'RVol': c_rvol, 'RSI': c_rsi, 'SMA200_Dist': c_dist,
                            'SMA20_Dist': c_sma20_dist, 'Wick_Reject': c_wick_reject,
                            'Trap_Score': c_trap_score, 'Momentum_Velocity': c_mom_vel
                        }
                        # 🟢 ADDED NIFTY_5D FOR V3
                        macro_data_for_ai = {'VIX': c_vix, 'Nifty_Trend': n_trend, 'Nifty_5D': c_nifty_5d}

                        # 2. Get the V2 Confidence Score (The Champion)
                        v2_approved, v2_confidence = ask_ai_gatekeeper(ai_model, stock_data_for_ai, macro_data_for_ai)
                        
                        # 3. Get the V3 Confidence Score (The Challenger)
                        v3_approved, v3_confidence = ask_v3_challenger(v3_model, stock_data_for_ai, macro_data_for_ai)

                        # 🟢 4. THE DUAL-CORE DECISION MATRIX
                        final_approval = False
                        strategy_tag = ""
                        
                        if v2_approved and v3_approved:
                            final_approval = True
                            strategy_tag = "V2_V3_Agreement"
                        elif v2_approved and not v3_approved:
                            final_approval = True
                            strategy_tag = "V2_Only"
                        elif v3_approved and not v2_approved:
                            final_approval = True
                            strategy_tag = "V3_Only"

                        # 5. 🟢 FIRE THE AGENTIC INTERCEPTOR
                        if symbol not in st.session_state.shadow_logged_today:
                            try:
                                evaluate_and_log_shadow_trade(
                                    ticker=symbol,
                                    entry_price=curr_price,
                                    traditional_score=v2_confidence, # Using V2 as the baseline shadow reference
                                    live_vix=c_vix,
                                    nifty_intraday_pct=n_trend,
                                    is_market_halted=not is_safe_to_buy, 
                                    sheet_id=st.secrets["gcp_service_account"]["sheet_id"] 
                                )
                                st.session_state.shadow_logged_today.append(symbol)
                                time.sleep(5) 
                            except Exception as e:
                                print(f"Shadow logger bypassed for {symbol}: {e}")

                        # 6. 👁️ FIRE THE VISIONARY AI 
                        if symbol not in st.session_state.vision_logged_today:
                            try:
                                ticker_df = pd.DataFrame({'Close': closes[ticker], 'High': highs[ticker]}).dropna().tail(125) 
                                if not ticker_df.empty:
                                    evaluate_and_log_vision_trade(symbol, ticker_df)
                                    st.session_state.vision_logged_today.append(symbol)
                                    time.sleep(1.5)
                            except Exception as e:
                                print(f"Vision shadow logger bypassed for {symbol}: {e}")

                       # 7. THE REAL PORTFOLIO TRADER
                        if status in ["🎯 CONFIRMED", "🚀 BREAKOUT", "✅ STRONG BUY"]:
                            if final_approval:
                                
                                capital_per_trade = 10000 
                                
                                # 🟢 NEW: If price > 10k, buy 1 share. Otherwise, allocate 10k evenly.
                                if curr_price > capital_per_trade:
                                    calculated_qty = 1
                                else:
                                    calculated_qty = int(capital_per_trade / curr_price)

                                new_trade = {
                                    "Date": now.strftime("%Y-%m-%d"), "EntryTime": now.strftime("%H:%M:%S"),
                                    "Symbol": symbol, "Ticker": ticker, 
                                    "Qty": calculated_qty, 
                                    "BuyPrice": curr_price,
                                    "StopPrice": curr_price * (1 - (risk_per_trade/100)), 
                                    "Strategy": strategy_tag, 
                                    "VIX": c_vix, "Nifty_Trend": n_trend, "RVol": c_rvol,
                                    "RSI": c_rsi, "SMA200_Dist": c_dist,
                                    "SMA20_Dist": c_sma20_dist, "Wick_Reject": c_wick_reject, "Nifty_5D": c_nifty_5d,
                                    "Trap_Score": c_trap_score, "Momentum_Velocity": c_mom_vel, 
                                    "AI_Confidence": max(v2_confidence, v3_confidence),
                                    "Max_Profit_%": 0.0, "Max_Drawdown_%": 0.0
                                }
                                st.session_state.portfolio.append(new_trade)
                                new_trades_added = True
                                st.session_state.notifications.append(f"🟢 {now.strftime('%H:%M')} - {strategy_tag}: Bought {calculated_qty}x {symbol}")
                                st.toast(f"🤖 Bot Bought: {calculated_qty} shares of {symbol}")
                            else:
                                # Both V2 and V3 completely rejected it
                                if symbol not in st.session_state.vetoed_today:
                                    st.session_state.notifications.append(f"🛑 {now.strftime('%H:%M')} - BOTH AI VETOED: {symbol}")
                                    vetoed_setup = {
                                        "Date": now.strftime("%Y-%m-%d"), "Time": now.strftime("%H:%M:%S"),
                                        "Symbol": symbol, "Price": curr_price, "AI_Confidence": v2_confidence,
                                        "VIX": c_vix, "Nifty_Trend": n_trend, "RVol": c_rvol,
                                        "RSI": c_rsi, "SMA200_Dist": c_dist,
                                        "SMA20_Dist": c_sma20_dist, "Wick_Reject": c_wick_reject, "Nifty_5D": c_nifty_5d,
                                        "Trap_Score": c_trap_score, "Momentum_Velocity": c_mom_vel
                                    }
                                    log_ai_veto(vetoed_setup)
                                    st.session_state.vetoed_today.append(symbol)
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
        tickers = [f"{str(p['Ticker']).replace(' ', '').replace('.NS', '')}.NS" for p in st.session_state.portfolio]
        try:
            # Replaced the rate-limited 1-minute interval fetch with a robust 1-day LTP fetch
            live_data = yf.download(tickers, period="1d", threads=False, progress=False)['Close']
        except: 
            live_data = pd.DataFrame()
        
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
            clean_ticker = f"{str(trade['Ticker']).replace(' ', '').replace('.NS', '')}.NS"
            try:
                if live_data.empty: raise ValueError("Empty data")
                if isinstance(live_data, pd.DataFrame): price = float(live_data[clean_ticker].dropna().iloc[-1])
                else: price = float(live_data.dropna().iloc[-1])
                if pd.isna(price): raise ValueError("NaN price")
            except Exception as e: 
                price = float(trade['BuyPrice'])
                api_glitch = True
            
            qty = int(trade['Qty'])
            buy = float(trade['BuyPrice'])
            sl = float(trade['StopPrice'])
            
            cur_val = price * qty
            inv_val = buy * qty
            pnl = cur_val - inv_val
            pnl_pct = (pnl / inv_val) * 100

            # 🟢 1. START MFE/MAE INJECTION (FIXED INFINITE RE-RUN BUG)
            current_pnl_pct = round(pnl_pct, 2)
            max_pnl = float(trade.get('Max_Profit_%', 0.0))
            max_dd = float(trade.get('Max_Drawdown_%', 0.0))

            if current_pnl_pct > max_pnl:
                trade['Max_Profit_%'] = current_pnl_pct
                portfolio_changed = True

            if current_pnl_pct < max_dd:
                trade['Max_Drawdown_%'] = current_pnl_pct
                portfolio_changed = True
            # 🟢 END MFE/MAE INJECTION
            
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
                # The 3-5-3 System: Activates at 5%, Trails by 3%
                if pnl_pct >= 5.0:
                    trail = round(price * 0.97, 2)
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
            
            # 🟢 AUTO-SELL BLOCK: The AI is allowed to learn from these
            elif auto_sell and not api_glitch and (price <= new_sl):
                closed_trade = trade.copy()
                closed_trade.update({
                    'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 
                    'ExitTime': now.strftime("%H:%M:%S"), 'PnL': pnl, 
                    'Target_Label': "1 (Winner)" if pnl > 0 else "0 (Loser)", # <--- UNIFIED HERE
                    'Max_Profit_%': trade.get('Max_Profit_%', 0.0),
                    'Max_Drawdown_%': trade.get('Max_Drawdown_%', 0.0)
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
                
                # 🟢 MANUAL-SELL BLOCK: Quarantined from the AI
                if c5.button(f"✅ CLOSE {msg}", key=f"close_{trade['Symbol']}", disabled=api_glitch):
                    closed_trade = trade.copy()
                    closed_trade.update({
                        'ExitPrice': price, 'ExitDate': now.strftime("%Y-%m-%d"), 
                        'ExitTime': now.strftime("%H:%M:%S"), 'PnL': pnl, 
                        'Target_Label': "MANUAL_WIN" if pnl > 0 else "MANUAL_LOSS", # <--- UNIFIED HERE
                        'Max_Profit_%': trade.get('Max_Profit_%', 0.0),
                        'Max_Drawdown_%': trade.get('Max_Drawdown_%', 0.0)
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
    else: 
        st.info("Portfolio Empty. Go to Scanner to find stocks.")

# --- TAB 3: MASTER QUANT AUDIT & STRATEGY DASHBOARD ---
with tab3:
    st.header("📊 Master Quant Analytics")
    st.markdown("Audit mathematical edge across live portfolios, background shadow logs, and AI vetoes.")

    if st.button("🔄 Force Reload Database"):
        st.cache_resource.clear()
        st.session_state.journal = fetch_sheet_data("Journal")
        st.rerun()
    st.divider()

    # Create three distinct sub-tabs aligning with your 3 Google Sheets
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "🕵️ Agentic Shadow Analyzer (Incubation)", 
        "📓 Journal Analyzer (Live Capital)", 
        "🛡️ AI Veto Tracker (Capital Saved)"
    ])

    # ==========================================
    # 1. AGENTIC SHADOW ANALYZER
    # ==========================================
    with sub_tab1:
        st.subheader("🕵️ Agentic Shadow Analyzer")
        st.caption("Evaluating the mathematical edge of T+8 paper trades from the Agentic_Shadow_Log.")
        
        try:
            shadow_data = fetch_sheet_data("Agentic_Shadow_Log")
            df_shadow = pd.DataFrame(shadow_data)
            
            if not df_shadow.empty and 'T8_Final_Outcome' in df_shadow.columns:
                df_shadow = df_shadow[~df_shadow['T8_Final_Outcome'].astype(str).str.contains("TBD")]
                
                if not df_shadow.empty:
                    # Clean data and outcomes
                    df_shadow['Outcome_Num'] = pd.to_numeric(df_shadow['T8_Final_Outcome'], errors='coerce')
                    df_shadow = df_shadow.dropna(subset=['Outcome_Num'])
                    
                    # Ensure Confidence is a series
                    conf_col = df_shadow.get('AI_Confidence', df_shadow.get('Traditional_Score', pd.Series(0, index=df_shadow.index)))
                    df_shadow['AI_Confidence'] = pd.to_numeric(conf_col, errors='coerce').fillna(0)
                    ticker_col = 'Ticker' if 'Ticker' in df_shadow.columns else 'Symbol'
                    df_shadow['Clean_Symbol'] = df_shadow[ticker_col].astype(str).str.replace('.NS', '', regex=False)

                    # Universe Splitter Toggle
                    universe_filter = st.radio(
                        "Select Market Universe to Audit:", 
                        ["Nifty 50 (Streamlit Live)", "Nifty 500 (GitHub Background)"],
                        horizontal=True
                    )
                    
                    # Filter dataset based on EXACT string selection
                    if universe_filter == "Nifty 50 (Streamlit Live)":
                        df_target = df_shadow[df_shadow['Clean_Symbol'].isin(NIFTY_50)]
                        display_title = "Nifty 50 (Large Cap)"
                    else:
                        df_target = df_shadow[~df_shadow['Clean_Symbol'].isin(NIFTY_50)]
                        display_title = "Nifty 500 (Broader Market)"
                    
                    if not df_target.empty:
                        wins = df_target[df_target['Outcome_Num'] == 1]
                        losses = df_target[df_target['Outcome_Num'] == 0]
                        total_shadow = len(df_target)
                        shadow_win_rate = (len(wins) / total_shadow * 100) if total_shadow > 0 else 0
                        
                        gross_profit_est = len(wins) * 5.0
                        gross_loss_est = len(losses) * 3.0
                        shadow_pf = (gross_profit_est / gross_loss_est) if gross_loss_est > 0 else float('inf')

                        st.markdown(f"### {display_title} Performance Overview")
                        c_sa1, c_sa2, c_sa3 = st.columns(3)
                        c_sa1.metric("Closed Shadow Trades", f"{total_shadow}")
                        c_sa2.metric("Win Rate", f"{shadow_win_rate:.1f}%", f"{len(wins)}W - {len(losses)}L")
                        pf_display = f"{shadow_pf:.2f}" if shadow_pf != float('inf') else "∞"
                        c_sa3.metric("Est. Profit Factor", pf_display, "Target: > 1.30")

                        st.markdown("**AI Confidence vs. Win Rate Breakdown**")
                        bins = [0, 50, 55, 60, 65, 70, 100]
                        labels = ['< 50%', '50% - 55%', '55% - 60%', '60% - 65%', '65% - 70%', '70%+']
                        df_target['Confidence_Tier'] = pd.cut(df_target['AI_Confidence'], bins=bins, labels=labels, include_lowest=True)
                        
                        tier_rows = []
                        for label in labels:
                            group = df_target[df_target['Confidence_Tier'] == label]
                            group_total = len(group)
                            if group_total > 0:
                                group_wins = len(group[group['Outcome_Num'] == 1])
                                group_wr = (group_wins / group_total * 100)
                                tier_rows.append({
                                    'Confidence Tier': label,
                                    'Total Setups': group_total,
                                    'Win Rate': f"{group_wr:.1f}%"
                                })
                        
                        if tier_rows:
                            st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)
                        else:
                            st.caption("No data available in confidence tiers yet.")
                    else:
                        st.info(f"No completed T+8 trades found for {universe_filter}.")
                else:
                    st.info("Shadow log has no completed trades yet. All are pending.")
            else:
                st.info("Shadow log is empty or missing 'T8_Final_Outcome' column.")
        except Exception as e:
            st.error(f"Could not load Shadow Log Audit: {e}")

    # ==========================================
    # 2. JOURNAL ANALYZER (Live Capital)
    # ==========================================
    with sub_tab2:
        st.subheader("📓 Journal Analyzer (Live Capital)")
        st.caption("Evaluating deployed capital, Brain head-to-head metrics, and Risk efficiency.")
        
        df_j = pd.DataFrame(st.session_state.journal) if st.session_state.journal else pd.DataFrame()
        
        if not df_j.empty and 'PnL' in df_j.columns:
            # Clean Live Metrics
            df_j['PnL'] = df_j['PnL'].astype(str).str.replace(r'[₹,a-zA-Z\s]', '', regex=True)
            df_j['PnL'] = pd.to_numeric(df_j['PnL'], errors='coerce').fillna(0)
            df_j['AI_Confidence'] = pd.to_numeric(df_j.get('AI_Confidence', 70.0), errors='coerce').fillna(70.0)
            df_j['Strategy'] = df_j.get('Strategy', 'Legacy')
            
            # --- HEAD TO HEAD: V2 vs V3 ---
            st.markdown("### Brain Head-to-Head Scorecard")
            strat_rows = []
            for strat in df_j['Strategy'].unique():
                s_df = df_j[df_j['Strategy'] == strat]
                s_wins = s_df[s_df['PnL'] > 0]
                s_losses = s_df[s_df['PnL'] <= 0]
                s_total = len(s_df)
                s_wr = (len(s_wins) / s_total * 100) if s_total > 0 else 0
                s_gross_prof = s_wins['PnL'].sum()
                s_gross_loss = abs(s_losses['PnL'].sum())
                s_pf = (s_gross_prof / s_gross_loss) if s_gross_loss > 0 else float('inf')
                
                strat_rows.append({
                    'AI Strategy Tag': strat,
                    'Total Trades': s_total,
                    'Win Rate': f"{s_wr:.1f}%",
                    'Net PnL': f"₹{s_df['PnL'].sum():.2f}",
                    'Profit Factor': f"{s_pf:.2f}" if s_pf != float('inf') else "∞"
                })
            st.dataframe(pd.DataFrame(strat_rows), use_container_width=True, hide_index=True)
            st.divider()

            c1, c2 = st.columns(2)
            
            # --- THRESHOLD OPTIMIZER ---
            with c1:
                st.markdown("### 🎛️ Live Threshold Optimizer")
                sim_threshold = st.slider("Min. AI Confidence Threshold (%)", min_value=50.0, max_value=99.0, value=65.0, step=1.0)
                
                sim_trades = df_j[df_j['AI_Confidence'] >= sim_threshold]
                vetoed_by_sim = df_j[df_j['AI_Confidence'] < sim_threshold]
                
                sim_pnl = sim_trades['PnL'].sum()
                sim_total = len(sim_trades)
                sim_wins = len(sim_trades[sim_trades['PnL'] > 0])
                sim_rate = (sim_wins / sim_total * 100) if sim_total > 0 else 0.0
                
                s_c1, s_c2 = st.columns(2)
                s_c1.metric("Simulated Net PnL", f"₹{sim_pnl:,.2f}")
                s_c2.metric("Simulated Win Rate", f"{sim_rate:.1f}%")
                
                saved_losses = len(vetoed_by_sim[vetoed_by_sim['PnL'] < 0])
                missed_wins = len(vetoed_by_sim[vetoed_by_sim['PnL'] > 0])
                if sim_threshold > 50.0:
                    st.caption(f"Strict threshold avoided **{saved_losses} losses** but missed **{missed_wins} wins**.")

            # --- MFE TRAILING STOP AUDIT ---
            with c2:
                st.markdown("### 📈 Trailing Stop Audit (MFE)")
                if 'Max_Profit_%' in df_j.columns:
                    df_j['Max_Profit_%'] = pd.to_numeric(df_j['Max_Profit_%'], errors='coerce').fillna(0)
                    wins_live = df_j[df_j['PnL'] > 0]
                    losses_live = df_j[df_j['PnL'] <= 0]
                    
                    avg_mfe_wins = wins_live['Max_Profit_%'].mean() if not wins_live.empty else 0
                    avg_mfe_losses = losses_live['Max_Profit_%'].mean() if not losses_live.empty else 0
                    
                    st.metric("Avg Peak Profit on Losing Trades", f"+{avg_mfe_losses:.2f}%")
                    st.caption("If this is > 3%, your trailing stop is activating too late.")
                    st.metric("Avg Peak Profit on Winning Trades", f"+{avg_mfe_wins:.2f}%")
                else:
                    st.caption("MFE tracking active. Awaiting new closed trades.")
        else:
            st.info("Journal is empty. No live trades completed yet.")

    # ==========================================
    # 3. AI VETO TRACKER
    # ==========================================
    with sub_tab3:
        st.subheader("🛡️ AI Veto Tracker (AI_Veto_Log)")
        st.markdown("Monitors setups that looked good technically but were rejected by the AI gatekeepers, proving how much capital the models saved you.")
        
        # Load the existing Ghost Dashboard logic which connects to AI_Veto_Log
        try:
            render_ghost_portfolio()
        except Exception as e:
            st.error(f"Error loading AI Veto Tracker: {e}")
