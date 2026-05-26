import pandas as pd
import yfinance as yf
import datetime
import pytz
import time

# Import your existing database functions
from database import fetch_sheet_data, sync_ghost_labels_to_cloud

# --- THE 3-5-3 SYSTEM PARAMETERS ---
TARGET_PCT = 5.0
STOP_PCT = -3.0
MAX_DAYS = 8

def run_automated_labeling():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist).replace(tzinfo=None)

    print(f"🤖 [AUTO-LABELER] Booting up at {now.strftime('%H:%M:%S')} IST...")
    
    # 1. Fetch Cloud Data
    raw_veto_data = fetch_sheet_data("AI_Veto_Log")
    if not raw_veto_data:
        print("❌ Database connection failed or empty.")
        return

    df = pd.DataFrame(raw_veto_data)
    if 'V3_Truth_Label' not in df.columns:
        df['V3_Truth_Label'] = "⏳ TBD"

    # 2. Isolate only the setups that are still chopping
    mask_pending = df['V3_Truth_Label'].isin(["", "⏳ TBD", None])
    df_pending = df[mask_pending].copy()

    if df_pending.empty:
        print("✅ [AUTO-LABELER] All setups are finalized. No pending vetoes to process.")
        return

    print(f"🔍 Found {len(df_pending)} pending setups. Running 3-5-3 simulation...")
    df_pending['Date'] = pd.to_datetime(df_pending['Date'])
    labels_updated = 0

    # 3. Process each pending setup
    for index, row in df_pending.iterrows():
        sym = row['Symbol']
        ticker = f"{sym}.NS"
        entry_price = float(row['Price'])
        veto_date = row['Date']
        
        try:
            # Fetch data from the veto date to today
            stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), progress=False)['Close']
            if stock_data.empty: continue
                
            post_veto_data = stock_data[stock_data.index.tz_localize(None) >= veto_date]
            if post_veto_data.empty: continue

            # --- THE 3-5-3 TRAILING MATH ---
            highest_seen = entry_price
            trade_active = True
            truth_label = "⏳ TBD"
            
            for date, price in post_veto_data.items():
                if not trade_active: break
                
                current_price = float(price.iloc[0]) if isinstance(price, pd.Series) else float(price)
                if current_price > highest_seen: highest_seen = current_price
                    
                live_pct = ((current_price - entry_price) / entry_price) * 100
                peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                
                # Hard Stop hit before trailing
                if live_pct <= STOP_PCT and peak_pct < TARGET_PCT:
                    truth_label = "0 (Loser)"
                    trade_active = False
                    
                # Trailing Stop Activation (+5%)
                elif peak_pct >= TARGET_PCT:
                    trailing_sl_price = highest_seen * (1 - (abs(STOP_PCT)/100))
                    if current_price <= trailing_sl_price:
                        truth_label = "1 (Winner)"
                        trade_active = False

            # Time-Decay: If T+8 expires without hitting targets, it's a safe veto (Loser)
            if trade_active and (now - veto_date).days >= MAX_DAYS:
                truth_label = "0 (Loser)" 
            
            # Apply update if the label changed from TBD
            if truth_label != "⏳ TBD":
                df.at[index, 'V3_Truth_Label'] = truth_label
                labels_updated += 1
                print(f"   ✔️ FINALIZED: {sym} -> {truth_label}")

            time.sleep(0.5) # Prevent Yahoo API ban

        except Exception as e:
            print(f"   ❌ Error evaluating {sym}: {e}")

    # 4. Push updates to Cloud ONLY if changes were made
    if labels_updated > 0:
        print(f"\n🚀 Step 3: Pushing {labels_updated} finalized labels to Google Sheets...")
        if sync_ghost_labels_to_cloud(df):
            print("✅ SUCCESS! Cloud database updated.")
        else:
            print("❌ FAILED to write to Google Sheets.")
    else:
        print("⏳ All pending setups are still chopping. No cloud updates required.")

if __name__ == "__main__":
    run_automated_labeling()
