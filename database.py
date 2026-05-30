import os
import toml
import streamlit as st
import gspread
import pandas as pd
import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

# 🟢 Global instantiation (Kept for boot logs, but functions will use dynamic time)
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")

@st.cache_resource
def init_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # 1. Try standard Streamlit approach first (for live UI app)
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
        except Exception:
            # 2. Fallback for Bare Python Mode (VS Code Terminal / GitHub Actions)
            # 🟢 THE FIX: Calculate the absolute, explicit path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            secrets_path = os.path.join(current_dir, ".streamlit", "secrets.toml")
            
            if os.path.exists(secrets_path):
                with open(secrets_path, "r") as f:
                    secrets = toml.load(f)
                
                if "gcp_service_account" in secrets:
                    creds_dict = dict(secrets["gcp_service_account"])
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    return client
            
            # If it still fails, print the EXACT path it was searching so you can debug
            print(f"🔴 Fallback failed: Searched for secrets at: {secrets_path}")
            return None
    except Exception as e:
        print(f"🔴 Critical Sheet Auth Error: {e}")
        return None
        
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
                # 🟢 THE FIX: Added "Max_Profit_%" and "Max_Drawdown_%" to the end of this list
                write_data = [["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "StopPrice", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "AI_Confidence", "Max_Profit_%", "Max_Drawdown_%"]]
            sheet.clear()
            sheet.update(write_data)
    except Exception as e: print(f"Cloud Save Error: {e}")

def log_trade_journal(trade):
    if not st.session_state.get('db_connected', False): return False
    
    # 🟢 Safe converter functions that catch blank strings and missing data
    def safe_float(val):
        try:
            if val == "" or val is None: return 0.0
            return float(val)
        except (ValueError, TypeError):
            return 0.0
            
    def safe_int(val):
        try:
            if val == "" or val is None: return 0
            return int(val)
        except (ValueError, TypeError):
            return 0

    # 🟢 Apply the safe converters to your row
    row = [
        trade.get("Date", ""), trade.get("EntryTime", ""), trade.get("Symbol", ""), trade.get("Ticker", ""),
        safe_int(trade.get("Qty", 0)), safe_float(trade.get("BuyPrice", 0.0)), safe_float(trade.get("ExitPrice", 0.0)),
        trade.get("ExitDate", ""), trade.get("ExitTime", ""), safe_float(trade.get("PnL", 0.0)), 
        trade.get("Target_Label", ""), # <--- UNIFIED HERE
        trade.get("Strategy", ""), safe_float(trade.get("VIX", 0.0)), safe_float(trade.get("Nifty_Trend", 0.0)),
        safe_float(trade.get("RVol", 0.0)), safe_float(trade.get("RSI", 0.0)), safe_float(trade.get("SMA200_Dist", 0.0)),
        safe_float(trade.get("SMA20_Dist", 0.0)), safe_float(trade.get("Wick_Reject", 0.0)), safe_float(trade.get("Nifty_5D", 0.0)),
        safe_float(trade.get("Trap_Score", 0.0)), safe_float(trade.get("Momentum_Velocity", 0.0)), safe_float(trade.get("AI_Confidence", 0.0))
    ]
    
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Journal")
            if not sheet.row_values(1):
                headers = ["Date", "EntryTime", "Symbol", "Ticker", "Qty", "BuyPrice", "ExitPrice", "ExitDate", "ExitTime", "PnL", "Target_Label", "Strategy", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "AI_Confidence"]
                sheet.append_row(headers)
            return True
    except Exception as e: 
        print(f"Journal Log Error: {e}")
        return False
        
def log_ai_veto(trade):
    
    
    # 1. Grab the live system clock
    import datetime
    import pytz
    local_ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(local_ist).strftime("%Y-%m-%d")
    
    # 2. Package the row EXACTLY like your old code, keeping your float() wraps and "Outcome"
    row_data = [
        real_today,  
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
        "⏳ TBD",  # 🟢 THE FIX: Now the labeler will instantly recognize new trades 
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
                if len(row) > 2 and row[0] == real_today and row[2] == symbol:
                    # Duplicate found! Silently block the database write
                    return True 
            
            # 5. If no duplicate is found, proceed with writing the data
            if not all_values:
                # We are just swapping the final item in this list from "Outcome" to "Target_Label"
                headers = ["Date", "Time", "Symbol", "Price", "AI_Confidence", "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity", "Target_Label"]
                sheet.append_row(headers)
            
            sheet.append_row(row_data)
            return True 
    except Exception as e: 
        print(f"Veto Log Error: {e}")
    return False

def log_signal_cloud(symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist, sma20_dist, wick_reject, nifty_5d, price):
    if not st.session_state.get('db_connected', False): return False
    
    import datetime
    import pytz
    local_ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(local_ist).strftime("%Y-%m-%d")

    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("Signal_Log")
            all_values = sheet.get_all_values()
            recent_rows = all_values[-20:] if len(all_values) > 20 else all_values
            
            for row in recent_rows:
                if len(row) > 1 and row[0] == real_today and row[1] == symbol:
                    return True 
            
            if not all_values:
                headers = ["Date", "Symbol", "Time", "Status", "Nifty_Trend", "VIX", "RVol", "RSI", "SMA200_Dist", "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Price"]
                sheet.append_row(headers)
            
            sheet.append_row([real_today, symbol, signal_time, status, nifty_trend, vix, rvol, rsi, sma200_dist, sma20_dist, wick_reject, nifty_5d, price])
            return True 
    except Exception as e: 
        print(f"Cloud Log Error: {e}")
    return False

def load_signals_from_cloud():
    history = {}
    
    import datetime
    import pytz
    local_ist = pytz.timezone('Asia/Kolkata')
    real_today = datetime.datetime.now(local_ist).strftime("%Y-%m-%d")

    try:
        data = fetch_sheet_data("Signal_Log")
        if data:
            df = pd.DataFrame(data)
            if not df.empty and 'Date' in df.columns:
                today_data = df[df['Date'] == real_today]
                for _, row in today_data.iterrows():
                    history[row['Symbol']] = str(row['Time']) # Force string just in case
    except Exception as e: 
        print(f"Error loading history: {e}")
    return history

# 🟢 NEW: V3 Pipeline Data Sync
def sync_ghost_labels_to_cloud(df_vetoes):
    """
    Overwrites the AI_Veto_Log sheet with labeled forward-return data.
    This creates the explicit Target Variables (1 or 0) required for the XGBoost V3 training.
    """
    if not st.session_state.get('db_connected', False): return False
    if df_vetoes.empty: return False
    
    try:
        client = init_google_sheet()
        if client:
            sheet = client.open("Swing_Trading_DB").worksheet("AI_Veto_Log")
            
            # Replace NaN values with empty strings for Google Sheets compatibility
            df_clean = df_vetoes.fillna("")
            
            # Clear the old data and rewrite it with the new V3_Truth_Label column included
            sheet.clear()
            sheet.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())
            return True
    except Exception as e:
        print(f"Ghost Sync Error: {e}")
    return False
