import pandas as pd
import yfinance as yf
import datetime
import pytz
import time

# Import your existing database functions
from database import fetch_sheet_data, sync_ghost_labels_to_cloud

# --- CONFIGURATION (Matches your Ghost Dashboard) ---
TARGET_PCT = 5.0
STOP_PCT = -3.0
MAX_DAYS = 8

def run_historical_backfill():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist).replace(tzinfo=None)

    print("📥 Step 1: Fetching historical Veto Log from Google Sheets...")
    raw_veto_data = fetch_sheet_data("AI_Veto_Log")
    
    if not raw_veto_data:
        print("❌ Database is empty or connection failed.")
        return

    df = pd.DataFrame(raw_veto_data)
    
    # Ensure the column exists
    if 'V3_Truth_Label' not in df.columns:
        df['V3_Truth_Label'] = ""

    # Find rows that need processing
    mask_needs_label = df['V3_Truth_Label'].isin(["", "⏳ TBD", None])
    df_unprocessed = df[mask_needs_label].copy()

    if df_unprocessed.empty:
        print("✅ All rows are already fully labeled! Nothing to backfill.")
        return

    print(f"🔍 Found {len(df_unprocessed)} historical vetoes missing V3 Truth Labels.")
    
    # Clean dates for processing
    df_unprocessed['Date'] = pd.to_datetime(df_unprocessed['Date'])
    
    labeled_count = 0

    print("⏳ Step 2: Running the 3-5-3 Time Machine Simulation...")
    for index, row in df_unprocessed.iterrows():
        sym = row['Symbol']
        ticker = f"{sym}.NS"
        entry_price = float(row['Price'])
        veto_date = row['Date']
        
        # Calculate the T+N window
        end_date = veto_date + datetime.timedelta(days=MAX_DAYS + 4) # Buffer for weekends
        
        try:
            # Fetch just the specific window for this stock to save API limits
            stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)['Close']
            
            if stock_data.empty:
                print(f"   ⚠️ No yfinance data found for {sym} around {veto_date.strftime('%Y-%m-%d')}")
                continue
                
            # Drop the actual veto date (we care about forward returns)
            post_veto_data = stock_data[stock_data.index.tz_localize(None) > veto_date]
            
            if post_veto_data.empty:
                continue

            # --- THE TRAILING SIMULATOR ---
            highest_seen = entry_price
            trade_active = True
            truth_label = "⏳ TBD"
            
            for date, price in post_veto_data.items():
                if not trade_active: break
                
                # yfinance returns series, ensure we extract the float
                current_price = float(price.iloc[0]) if isinstance(price, pd.Series) else float(price)
                
                if current_price > highest_seen:
                    highest_seen = current_price
                    
                live_pct = ((current_price - entry_price) / entry_price) * 100
                peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                
                # Condition 1: Hard Stop hit before trailing
                if live_pct <= STOP_PCT and peak_pct < TARGET_PCT:
                    truth_label = "0 (Loser)"
                    trade_active = False
                    
                # Condition 2: Trailing Stop Activation
                elif peak_pct >= TARGET_PCT:
                    trailing_sl_price = highest_seen * (1 - (abs(STOP_PCT)/100))
                    if current_price <= trailing_sl_price:
                        truth_label = "1 (Winner)"
                        trade_active = False

            # If the T+8 window is fully closed and it just chopped sideways without hitting stops
            if trade_active and (now - veto_date).days > MAX_DAYS:
                truth_label = "0 (Loser)" # Sideways chop is a veto success (we didn't tie up capital)
            
            # Apply the label back to the main dataframe
            df.at[index, 'V3_Truth_Label'] = truth_label
            if truth_label != "⏳ TBD":
                labeled_count += 1
                
            print(f"   ✔️ {sym} ({veto_date.strftime('%Y-%m-%d')}): {truth_label}")
            time.sleep(0.5) # API Rate limit protection

        except Exception as e:
            print(f"   ❌ Error processing {sym}: {e}")

    print(f"\n🚀 Step 3: Pushing {labeled_count} new labels to Google Sheets...")
    if sync_ghost_labels_to_cloud(df):
        print("✅ SUCCESS! Your historical database is fully backfilled and ready for V3.")
    else:
        print("❌ FAILED to write to Google Sheets. Check your database.py connection.")

if __name__ == "__main__":
    run_historical_backfill()
