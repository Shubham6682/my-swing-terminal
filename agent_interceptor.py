import json
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def load_agent_rules(filepath="agent_rules.json"):
    """Loads the active macro rules for the week."""
    with open(filepath, "r") as file:
        return json.load(file)

def connect_to_shadow_log(sheet_id):
    """Establishes connection specifically to the Agentic_Shadow_Log tab."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    # Open the workbook and target the specific Shadow Log tab
    return client.open_by_key(sheet_id).worksheet("Agentic_Shadow_Log")

def evaluate_and_log_shadow_trade(ticker, traditional_score, live_vix, nifty_intraday_pct, is_market_halted, sheet_id):
    """
    The core interceptor function. Evaluates the live setup against the weekend rules,
    generates the agent thesis, and logs the parallel decision to Google Sheets.
    """
    rules = load_agent_rules()
    macro = rules["macro_boundaries"]
    logic = rules["override_logic"]
    
    agent_decision = "APPROVE"
    agent_thesis = "Baseline: Math and Macro aligned."
    is_phantom = False

    # Scenario 3: Nifty is bleeding / Market is manually halted
    if is_market_halted or nifty_intraday_pct <= macro["nifty_bleed_threshold_percent"]:
        is_phantom = True
        if macro["phantom_trade_exploration_enabled"]:
            if traditional_score >= logic["min_traditional_score_for_phantom_buy"]:
                agent_decision = "APPROVE"
                agent_thesis = f"Phantom Trade: High conviction capitulation setup ({traditional_score}% score)."
            else:
                agent_decision = "REJECT"
                agent_thesis = f"Phantom Reject: Score ({traditional_score}%) too low during market bleed."
        else:
            agent_decision = "REJECT"
            agent_thesis = "System Halted: Phantom exploration disabled in rules."

    # Scenarios 1 & 2: Market is healthy, checking for Macro Overrides
    else:
        if logic["reject_if_vix_above_max"] and live_vix > macro["max_allowable_vix"]:
            agent_decision = "REJECT"
            agent_thesis = f"Macro Override: Live VIX ({live_vix}) exceeds allowable limit ({macro['max_allowable_vix']})."
        else:
            # If no macro rules are broken, mirror the Traditional AI's mathematical judgment
            if traditional_score >= 75.0: 
                agent_decision = "APPROVE"
                agent_thesis = "Approved: Traditional math strong and macro environment stable."
            else:
                agent_decision = "REJECT"
                agent_thesis = "Rejected: Weak mathematical setup."

    # Construct the exact row to match your Google Sheet schema
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_data = [
        timestamp,
        ticker,
        traditional_score,
        live_vix,
        nifty_intraday_pct,
        str(is_phantom),
        agent_decision,
        agent_thesis,
        "⏳ TBD" # T8_Final_Outcome remains pending
    ]

    # Push to Google Sheets
    try:
        worksheet = connect_to_shadow_log(sheet_id)
        worksheet.append_row(row_data)
        print(f"[AGENTIC LOG] Successfully recorded {ticker} -> {agent_decision}")
    except Exception as e:
        print(f"[AGENT ERROR] Failed to log shadow trade: {e}")

    return agent_decision, agent_thesis
