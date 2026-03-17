import time
import pandas as pd
import os
from datetime import datetime

# We start with a small test list. Later we swap this for NIFTY_500.
TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HAL.NS"] 
LOG_FILE = "signal_logs.csv"

def fetch_and_analyze(ticker):
    """Your actual swing trading indicator logic will go here."""
    time.sleep(1) # Paces the requests so Yahoo/API doesn't ban you
    
    # Placeholder logic just to test if the pipeline works
    if ticker == "HAL.NS": 
        return "BUY"
    return "NO_SIGNAL"

def main():
    print(f"Starting background scan at {datetime.now()}...")
    new_signals = []
    
    for ticker in TICKERS:
        try:
            signal = fetch_and_analyze(ticker)
            if signal in ["BUY", "SELL"]:
                new_signals.append({
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Ticker": ticker,
                    "Signal": signal,
                    "Notes": "Automated cloud scan"
                })
        except Exception as e:
            print(f"Error on {ticker}: {e}")

    # Append new signals to the CSV file
    if new_signals:
        df_new = pd.DataFrame(new_signals)
        if os.path.exists(LOG_FILE):
            df_new.to_csv(LOG_FILE, mode='a', header=False, index=False)
        else:
            df_new.to_csv(LOG_FILE, mode='w', header=True, index=False)
        print(f"Success: Saved {len(new_signals)} new signals to {LOG_FILE}.")
    else:
        print("Scan complete: 0 signals found.")

if __name__ == "__main__":
    main()
