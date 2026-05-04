import streamlit as st
import gspread
import pandas as pd
import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

# Setup timezone and date for the logger
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")

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
    if not st.session_state.get('db_connected', False): return
    if data is None: return
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Portfolio")
            if len(data) > 0:
                df = pd.DataFrame(data)
                df = df.fillna("") 
                write_data = [df.columns.values.tolist()] + df.values.tolist()
            else:
                write_data = [["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "StopPrice", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "AI_Confidence"]]
            sheet.clear()
            sheet.update(write_data)
    except Exception as e: print(f"Cloud Save Error: {e}")

def log_trade_journal(trade):
    if not st.session_state.db_connected: return False
    
    # 🟢 VULNERABILITY 1 PATCH: Wrapping numbers in float() and int()
    row = [
        trade.get("Date", ""), trade.get("EntryTime", ""), trade.get("Symbol", ""), trade.get("Ticker", ""),
        int(trade.get("Qty", 0)), float(trade.get("BuyPrice", 0.0)), float(trade.get("ExitPrice", 0.0)),
        trade.get("ExitDate", ""), trade.get("ExitTime", ""), float(trade.get("PnL", 0.0)), trade.get("Result", ""),
        trade.get("Strategy", ""), float(trade.get("VIX", 0.0)), float(trade.get("Nifty_Trend", 0.0)),
        float(trade.get("RVol", 0.0)), float(trade.get("RSI", 0.0)), float(trade.get("SMA200_Dist", 0.0)),
        float(trade.get("SMA20_Dist", 0.0)), float(trade.get("Wick_Reject", 0.0)), float(trade.get("Nifty_5D", 0.0)),
        float(trade.get("Trap_Score", 0.0)), float(trade.get("Momentum_Velocity", 0.0)), float(trade.get("AI_Confidence", 0.0))
    ]
    
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Journal")
            if not sheet.row_values(1):
                headers = ["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "ExitPrice", "ExitDate", "ExitTime", "PnL", "Result", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "AI_Confidence"]
                sheet.append_row(headers)
            sheet.append_row(row)
            return True
    except: return False
        
def log_ai_veto(trade):
    if not st.session_state.get('db_connected', False): return False
    
    # 1. Grab the live system clock
    import datetime
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(ist).strftime("%Y-%m-%d")
    
    # 2. Package the row EXACTLY like your old code, keeping your float() wraps and "Outcome"
    row_data = [
        real_today,  # 🟢 Using live clock instead of trade.get("Date")
        trade.get("Time", ""), 
        trade.get("Symbol", ""),
        float(trade.get("Price", 0.0)), 
        float(trade.get("AI_Confidence", 0.0)),
        float(trade.get("VIX", 0.0)), 
        float(trade.get("Nifty_Trend", 0.0)),
        float(trade.get("RVol", 0.0)), 
        float(trade.get("RSI", 0.0)), 
        float(trade.get("SMA200_Dist", 0.0)), 
        float(trade.get("SMA20_Dist", 0.0)), 
        float(trade.get("Wick_Reject", 0.0)), 
        float(trade.get("Nifty_5D", 0.0)),
        float(trade.get("Trap_Score", 0.0)), 
        float(trade.get("Momentum_Velocity", 0.0)),
        "VETOED" 
    ]
    
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("AI_Veto_Log")
            
            # 3. Fetch recent rows to check for duplicates
            all_values = sheet.get_all_values()
            recent_rows = all_values[-50:] if len(all_values) > 50 else all_values
            
            symbol = trade.get("Symbol", "")
            
            # 4. THE CLOUD SHIELD: Scan the recent cloud rows
            for row in recent_rows:
                # Date is column A (index 0) and Symbol is column C (index 2)
                if len(row) > 2 and row[0] == real_today and row[2] == symbol:
                    # Duplicate found! Silently block the database write
                    return True 
            
            # 5. If no duplicate is found, proceed with writing the data
            if not all_values:
                headers = ["Date", "Time", "Symbol", "Price", "AI_Confidence", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "Outcome"]
                sheet.append_row(headers)
            
            sheet.append_row(row_data)
            return True 
    except Exception as e: 
        print(f"Veto Log Error: {e}")
    return False

def log_signal_cloud(symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist, sma20_dist, wick_reject, nifty_5d, price):
    if not st.session_state.get('db_connected', False): return False
    
    # 🟢 THE FIX: Force the function to check the live clock right now
    import datetime
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(ist).strftime("%Y-%m-%d")

    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Signal_Log")
            all_values = sheet.get_all_values()
            recent_rows = all_values[-20:] if len(all_values) > 20 else all_values
            
            for row in recent_rows:
                # 🟢 Using real_today instead of the frozen today_str
                if len(row) > 1 and row[0] == real_today and row[1] == symbol:
                    return True 
            
            if not all_values:
                headers = ["Date", "Symbol", "Time", "Status", "Nifty_Trend", "VIX", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Price"]
                sheet.append_row(headers)
            
            # 🟢 Using real_today for the actual log injection
            sheet.append_row([real_today, symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist, sma20_dist, wick_reject, nifty_5d, price])
            return True 
    except Exception as e: 
        print(f"Cloud Log Error: {e}")
    return False

def load_signals_from_cloud():
    history = {}
    
    # 🟢 THE FIX: Force the function to check the live clock to fetch today's history
    import datetime
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(ist).strftime("%Y-%m-%d")

    try:
        data = fetch_sheet_data("Signal_Log")
        if data:
            df = pd.DataFrame(data)
            if not df.empty and 'Date' in df.columns:
                # 🟢 Filter by real_today instead of the frozen today_str
                today_data = df[df['Date'] == real_today]
                for _, row in today_data.iterrows():
                    history[row['Symbol']] = str(row['Time']) # Force string just in case
    except Exception as e: 
        print(f"Error loading history: {e}")
    return history
