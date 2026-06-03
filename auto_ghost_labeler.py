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
    
    # 🟢 ALIGNED WITH NEW DATABASE SCHEMA
    if 'Target_Label' not in df.columns: df['Target_Label'] = "⏳ TBD"
    if 'Max_Profit_%' not in df.columns: df['Max_Profit_%'] = 0.0
    if 'Max_Drawdown_%' not in df.columns: df['Max_Drawdown_%'] = 0.0

    # 2. Isolate only the setups that are still chopping
    mask_pending = df['Target_Label'].isin(["", "⏳ TBD", None])
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
            # 🟢 FIX: Fetch ALL data so we get 'High' and 'Low', not just 'Close'
            stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), progress=False)
            if stock_data.empty or 'Close' not in stock_data.columns: continue
                
            # THE BOUNDARY FIX: Calculate the exact expiration date (T+8)
            expiration_date = veto_date + datetime.timedelta(days=MAX_DAYS)
            
            # THE BOUNDARY FIX: Slice data to STRICTLY exist within the 8-day window
            post_veto_data = stock_data[
                (stock_data.index.tz_localize(None) >= veto_date) & 
                (stock_data.index.tz_localize(None) <= expiration_date)
            ]
            
            # 🟢 DAY 0 CONTAMINATION SHIELD: 
            # Strip out the exact veto date from the OHLC evaluation loop. 
            # The stock's future simulation must strictly begin on T+1.
            post_veto_data = post_veto_data[post_veto_data.index.tz_localize(None).normalize() > veto_date.normalize()]
            
            if post_veto_data.empty: continue
            # 🟢 START MFE/MAE INJECTION
            try:
                # Calculate absolute extremes across the simulation window
                highest_price_reached = float(post_veto_data['High'].max())
                lowest_price_reached = float(post_veto_data['Low'].min())
                
                # Push the math directly into your dataframe
                df.at[index, 'Max_Profit_%'] = round(((highest_price_reached - entry_price) / entry_price) * 100, 2)
                df.at[index, 'Max_Drawdown_%'] = round(((lowest_price_reached - entry_price) / entry_price) * 100, 2)
            except Exception as e:
                print(f"   ⚠️ Could not calculate extremes for {sym}: {e}")
            # 🟢 END MFE/MAE INJECTION

            # --- THE 3-5-3 TRAILING MATH (UPGRADED: STRICT INTRADAY RISK) ---
            highest_seen = entry_price
            trade_active = True
            truth_label = "⏳ TBD"
            
            # 🟢 UPGRADE: We iterate through the whole daily row to check Highs and Lows
            for date, daily_data in post_veto_data.iterrows():
                if not trade_active: break
                
                day_high = float(daily_data['High'])
                day_low = float(daily_data['Low'])
                
                # 1. Update the highest peak seen so far (for trailing activation)
                if day_high > highest_seen: 
                    highest_seen = day_high
                    
                peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                live_low_pct = ((day_low - entry_price) / entry_price) * 100
                
                # 2. Strict Hard Stop: Did the intraday LOW crash through the -3% floor?
                if live_low_pct <= STOP_PCT and peak_pct < TARGET_PCT:
                    truth_label = "0 (Loser)"
                    trade_active = False
                    
                # 3. Trailing Stop Activation (+5% Target Hit)
                elif peak_pct >= TARGET_PCT:
                    trailing_sl_price = highest_seen * (1 - (abs(STOP_PCT)/100))
                    # If the stock hits the target, but the intraday low drops below the trail, we exit.
                    if day_low <= trailing_sl_price:
                        truth_label = "1 (Winner)"
                        trade_active = False

            # Time-Decay Check: Did the simulation window actually close?
            if trade_active:
                if (now - veto_date).days >= MAX_DAYS:
                    truth_label = "0 (Loser)"  # Window closed, stock chopped. Mark Loser.
                else:
                    truth_label = "⏳ TBD"      # Real life time hasn't reached Day 8 yet. 
            
            # Apply update if the label changed from TBD
            if truth_label != "⏳ TBD":
                df.at[index, 'Target_Label'] = truth_label
                labels_updated += 1
                print(f"   ✔️ FINALIZED: {sym} -> {truth_label}")

            time.sleep(0.5) # Prevent Yahoo API ban

        except Exception as e:
            print(f"   ❌ Error evaluating {sym}: {e}")

    # 4. Push updates to Cloud ONLY if changes were made
    # 🟢 UPGRADED: Force sync if any pending trades exist so rolling extremes update live
    if labels_updated > 0 or not df_pending.empty:
        print(f"\n🚀 Step 3: Pushing updated matrix to Google Sheets...")
        if sync_ghost_labels_to_cloud(df):
            print("✅ SUCCESS! Cloud database updated with latest rolling metrics.")
        else:
            print("❌ FAILED to write to Google Sheets.")
    else:
        print("⏳ Vault is entirely clean. No cloud updates required.")

if __name__ == "__main__":
    run_automated_labeling()
