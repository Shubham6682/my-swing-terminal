import json
import datetime
import gspread
import streamlit as st
import yfinance as yf
import pytz
from oauth2client.service_account import ServiceAccountCredentials

def load_agent_rules(filepath="agent_rules.json"):
    with open(filepath, "r") as file:
        return json.load(file)

def connect_to_shadow_log(sheet_id):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).worksheet("Agentic_Shadow_Log")

def fetch_todays_shadow_log(sheet_id):
    """Reads the Google Sheet to restore the engine's memory of what it already logged today."""
    try:
        worksheet = connect_to_shadow_log(sheet_id)
        data = worksheet.get_all_records()
        ist = pytz.timezone('Asia/Kolkata')
        today_str = datetime.datetime.now(ist).strftime("%Y-%m-%d")
        
        # Pulls the tickers from the sheet if the timestamp matches today's date
        return [row['Ticker'] for row in data if str(row.get('Date_Time', '')).startswith(today_str)]
    except Exception as e:
        print(f"[AGENT MEMORY ERROR] Failed to fetch memory: {e}")
        return []

def evaluate_and_log_shadow_trade(ticker, entry_price, traditional_score, live_vix, nifty_intraday_pct, is_market_halted, sheet_id):
    rules = load_agent_rules()
    macro = rules["macro_boundaries"]
    logic = rules["override_logic"]
    
    agent_decision, agent_thesis, is_phantom = "APPROVE", "Baseline: Math and Macro aligned.", False

    if is_market_halted or nifty_intraday_pct <= macro["nifty_bleed_threshold_percent"]:
        is_phantom = True
        if macro["phantom_trade_exploration_enabled"]:
            if traditional_score >= logic["min_traditional_score_for_phantom_buy"]:
                agent_decision, agent_thesis = "APPROVE", f"Phantom Trade: High conviction capitulation setup ({traditional_score}% score)."
            else:
                agent_decision, agent_thesis = "REJECT", f"Phantom Reject: Score ({traditional_score}%) too low during market bleed."
        else:
            agent_decision, agent_thesis = "REJECT", "System Halted: Phantom exploration disabled."
    else:
        if logic["reject_if_vix_above_max"] and live_vix > macro["max_allowable_vix"]:
            agent_decision, agent_thesis = "REJECT", f"Macro Override: Live VIX ({live_vix}) exceeds allowable limit ({macro['max_allowable_vix']})."
        else:
            if traditional_score >= 75.0: 
                agent_decision, agent_thesis = "APPROVE", "Approved: Traditional math strong and macro environment stable."
            else:
                agent_decision, agent_thesis = "REJECT", "Rejected: Weak mathematical setup."

    ist = pytz.timezone('Asia/Kolkata')
    timestamp = datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    row_data = [
        timestamp, ticker, traditional_score, live_vix, nifty_intraday_pct, 
        str(is_phantom), agent_decision, agent_thesis, entry_price, "⏳ TBD"
    ]

    try:
        worksheet = connect_to_shadow_log(sheet_id)
        worksheet.append_row(row_data)
        print(f"[AGENTIC LOG] Recorded {ticker} -> {agent_decision}")
    except Exception as e:
        print(f"[AGENT ERROR] Failed to log: {e}")

    return agent_decision, agent_thesis

def auto_grade_shadow_log(sheet_id):
    """
    Autonomously scans BOTH Shadow Logs (Agentic and Vision), pulls bulk market history, 
    and stamps 1 (Win) or 0 (Loss) based on your strict 3-5-3 rules inside a T+8 window.
    """
    import pandas as pd
    import streamlit as st
    import datetime
    import pytz
    import gspread
    
    try:
        # 1. Connect using your existing function
        base_worksheet = connect_to_shadow_log(sheet_id)
        
        # 2. 🟢 THE UPGRADE: Grab the parent spreadsheet so we can access ANY tab
        spreadsheet = base_worksheet.spreadsheet
        
        # 3. 🟢 THE LOOP: Define the exact names of your two shadow logs
        tabs_to_grade = ["Agentic_Shadow_Log", "Vision_Shadow_Log"]
        
        for tab_name in tabs_to_grade:
            try:
                worksheet = spreadsheet.worksheet(tab_name)
            except gspread.exceptions.WorksheetNotFound:
                st.error(f"🚨 Missing tab in Google Sheets: '{tab_name}'")
                continue # Skip to the next tab if one is missing
                
            data = worksheet.get_all_records()
            raw_headers = worksheet.row_values(1)
            
            headers = [str(h).strip() for h in raw_headers]
            
            if "T8_Final_Outcome" not in headers or "Entry_Price" not in headers: 
                st.error(f"🚨 {tab_name} ERROR: Missing 'T8_Final_Outcome' or 'Entry_Price' columns.")
                continue
                
            outcome_col_index = headers.index("T8_Final_Outcome") + 1
            
            ist = pytz.timezone('Asia/Kolkata')
            today = datetime.datetime.now(ist).date()
            updates = []
            
            pending_rows = []
            unique_tickers = set()
            skipped_dates = 0 
            
            for index, row in enumerate(data):
                clean_row = {str(k).strip(): v for k, v in row.items()}
                current_outcome = str(clean_row.get('T8_Final_Outcome', '')).strip()
                
                if "TBD" in current_outcome or current_outcome == "":
                    raw_price = str(clean_row.get('Entry_Price', '0')).replace(',', '').replace('₹', '').strip()
                    try:
                        entry_price = float(raw_price)
                    except ValueError:
                        continue 
                        
                    if entry_price == 0: continue
                    
                    ticker = str(clean_row.get('Ticker', '')).strip()
                    if not ticker: continue
                    
                    yf_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                    unique_tickers.add(yf_ticker)
                    pending_rows.append((index, clean_row, yf_ticker, entry_price))
                    
            if not pending_rows: 
                st.info(f"ℹ️ {tab_name}: No pending trades found (or headers couldn't be parsed).")
                continue # Skip to the next tab
            
            st.toast(f"🔄 {tab_name}: Analyzing {len(pending_rows)} pending trades...", icon="⏳")
            
            live_data = yf.download(list(unique_tickers), period="3mo", threads=False, progress=False)
            
            for index, clean_row, yf_ticker, entry_price in pending_rows:
                raw_date = str(clean_row.get('Date_Time', clean_row.get('Date', ''))).split(" ")[0].strip()
                entry_date = None
                
                for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        entry_date = datetime.datetime.strptime(raw_date, fmt).date()
                        break 
                    except ValueError:
                        pass
                
                if not entry_date:
                    skipped_dates += 1
                    continue 
                    
                days_passed = (today - entry_date).days
                
                try:
                    if len(unique_tickers) == 1:
                        stock_df = live_data.copy()
                    else:
                        if 'Close' not in live_data.columns or yf_ticker not in live_data['Close']: continue
                        stock_df = pd.DataFrame({
                            'High': live_data['High'][yf_ticker],
                            'Low': live_data['Low'][yf_ticker],
                            'Close': live_data['Close'][yf_ticker]
                        }).dropna()
                except Exception:
                    continue
                    
                if stock_df.empty: continue
                
                expiration_date = entry_date + datetime.timedelta(days=8)
                stock_dates = pd.to_datetime(stock_df.index).date 
                
                t8_window = stock_df[(stock_dates > entry_date) & (stock_dates <= expiration_date)]
                
                if t8_window.empty: continue
                
                max_high = float(t8_window['High'].max())
                min_low = float(t8_window['Low'].min())
                last_close = float(t8_window['Close'].iloc[-1])
                
                outcome = "⏳ TBD"
                
                if max_high >= entry_price * 1.05: outcome = "1"
                elif min_low <= entry_price * 0.97: outcome = "0"
                elif days_passed >= 8: outcome = "1" if last_close > entry_price else "0"
                        
                if outcome != "⏳ TBD":
                    row_number = index + 2 
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_number, outcome_col_index), 'values': [[outcome]]})
                    
            if updates:
                worksheet.batch_update(updates)
                st.success(f"🤖 {tab_name} COMPLETE: Graded {len(updates)} trades!")
            elif skipped_dates > 0:
                st.warning(f"⚠️ {tab_name}: Couldn't read the date format for {skipped_dates} rows.")
            else:
                st.info(f"ℹ️ {tab_name}: Trades analyzed, but none have hit targets or expired yet.")
                
    except Exception as e:
        st.error(f"🚨 MASTER AUDIT CRASHED: {str(e)}")
