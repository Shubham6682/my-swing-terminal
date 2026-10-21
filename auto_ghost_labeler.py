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
            # 🟢 FIX: Fetch ALL data and flatten MultiIndex columns safely
            stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), progress=False)
            if stock_data.empty: continue
            if isinstance(stock_data.columns, pd.MultiIndex):
                stock_data.columns = stock_data.columns.get_level_values(0)
            if 'Close' not in stock_data.columns: continue
                
            # THE BOUNDARY FIX: Calculate the exact expiration date (T+8)
            expiration_date = veto_date + datetime.timedelta(days=MAX_DAYS)
            
            # THE BOUNDARY FIX: Slice data to STRICTLY exist within the 8-day window
            post_veto_data = stock_data[
                (stock_data.index.tz_localize(None) >= veto_date) & 
                (stock_data.index.tz_localize(None) <= expiration_date)
            ]
            
            # 🟢 DAY 0 CONTAMINATION SHIELD: Strictly begin on T+1
            post_veto_data = post_veto_data[post_veto_data.index.tz_localize(None).normalize() > veto_date.normalize()]
            
            if post_veto_data.empty: continue

            # 🟢 START MFE/MAE INJECTION
            try:
                highest_price_reached = float(post_veto_data['High'].max())
                lowest_price_reached = float(post_veto_data['Low'].min())
                
                df.at[index, 'Max_Profit_%'] = round(((highest_price_reached - entry_price) / entry_price) * 100, 2)
                df.at[index, 'Max_Drawdown_%'] = round(((lowest_price_reached - entry_price) / entry_price) * 100, 2)
            except Exception as e:
                print(f"   ⚠️ Could not calculate extremes for {sym}: {e}")
            # 🟢 END MFE/MAE INJECTION

            # --- THE 3-5-3 TRAILING MATH (UPGRADED: STRICT INTRADAY RISK) ---
            highest_seen = entry_price
            trade_active = True
            trailing_active = False
            truth_label = "⏳ TBD"
            
            for date, daily_data in post_veto_data.iterrows():
                if not trade_active: break
                
                day_high = float(daily_data['High'])
                day_low = float(daily_data['Low'])
                day_close = float(daily_data['Close'])
                
                live_low_pct = ((day_low - entry_price) / entry_price) * 100
                
                # 1. Check Hard Stop FIRST (before updating today's high) if trailing hasn't activated yet
                if not trailing_active and live_low_pct <= STOP_PCT:
                    truth_label = "0 (Loser)"
                    trade_active = False
                    break
                
                # 2. If trailing was already active from a prior day, check if today's low hit the trail
                if trailing_active:
                    if day_high > highest_seen:
                        highest_seen = day_high
                    trailing_sl_price = highest_seen * (1 - (abs(STOP_PCT)/100))
                    if day_low <= trailing_sl_price:
                        truth_label = "1 (Winner)"
                        trade_active = False
                        break
                else:
                    # 3. Check if today's high activates the +5% trailing stop
                    if day_high > highest_seen:
                        highest_seen = day_high
                    peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                    if peak_pct >= TARGET_PCT:
                        trailing_active = True
                        trailing_sl_price = highest_seen * (1 - (abs(STOP_PCT)/100))
                        # On activation day, use Close (not morning Low) to avoid same-candle look-ahead bug
                        if day_close <= trailing_sl_price:
                            truth_label = "1 (Winner)"
                            trade_active = False
                            break

            # Time-Decay Check: Did the 8-day window close?
            if trade_active:
                if (now - veto_date).days >= MAX_DAYS:
                    last_close = float(post_veto_data['Close'].iloc[-1])
                    # 🟢 FIX: If it activated the +5% trail or closed above entry price on Day 8, it's a Winner!
                    if trailing_active or last_close > entry_price:
                        truth_label = "1 (Winner)"
                    else:
                        truth_label = "0 (Loser)"
                else:
                    truth_label = "⏳ TBD"
            
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
