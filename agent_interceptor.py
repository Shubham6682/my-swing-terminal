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
    Autonomously scans the Shadow Log for pending trades, checks market history, 
    and stamps 1 (Win) or 0 (Loss) based on your strict 3-5-3 rules.
    """
    try:
        worksheet = connect_to_shadow_log(sheet_id)
        data = worksheet.get_all_records()
        headers = worksheet.row_values(1)
        
        if "T8_Final_Outcome" not in headers: return
        outcome_col_index = headers.index("T8_Final_Outcome") + 1
        
        updates = []
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.datetime.now(ist).date()
        
        for index, row in enumerate(data):
            if row.get('T8_Final_Outcome') == "⏳ TBD":
                ticker = row['Ticker']
                entry_date_str = str(row['Date_Time']).split(" ")[0]
                entry_date = datetime.datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                entry_price = float(row.get('Entry_Price', 0))
                
                if entry_price == 0: continue
                
                days_passed = (today - entry_date).days
                
                # Ensure the ticker has the .NS suffix for Yahoo Finance India
                yf_ticker = f"{ticker}.NS" if not str(ticker).endswith(".NS") else ticker
                df = yf.download(yf_ticker, start=entry_date_str, threads=False, progress=False)
                if df.empty: continue
                
                max_high = float(df['High'].max())
                min_low = float(df['Low'].min())
                last_close = float(df['Close'].iloc[-1])
                
                outcome = "⏳ TBD"
                
                # The Autonomous 3-5-3 Evaluator
                if max_high >= entry_price * 1.05: outcome = "1"       # Hit 5% Target
                elif min_low <= entry_price * 0.97: outcome = "0"      # Hit 3% Stop Loss
                elif days_passed >= 8:                                 # Time Decay (8 Days)
                    outcome = "1" if last_close > entry_price else "0"
                        
                if outcome != "⏳ TBD":
                    row_number = index + 2 # +2 because lists are 0-indexed and Sheet row 1 is headers
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_number, outcome_col_index), 'values': [[outcome]]})
                    
        # Batch update all graded rows at once to save Google API limits
        if updates:
            worksheet.batch_update(updates)
            print(f"[AGENT AUDIT] Automatically graded {len(updates)} shadow trades.")
            
    except Exception as e:
        print(f"[AGENT AUDIT ERROR]: {e}")
