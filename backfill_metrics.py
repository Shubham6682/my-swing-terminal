import pandas as pd
import yfinance as yf
import datetime
import time

# Import your existing database functions
from database import fetch_sheet_data, sync_ghost_labels_to_cloud

def run_historical_backfill():
    print("🚀 Booting Historical Data Backfiller...")
    
    # 1. Fetch the master database
    raw_data = fetch_sheet_data("AI_Veto_Log")
    if not raw_data:
        print("❌ Database connection failed.")
        return

    df = pd.DataFrame(raw_data)

    # 2. Filter for finalized trades that are missing the new metrics
    # We look for 1s and 0s where Max_Profit is either 0.0 or an empty string
    mask_needs_backfill = df['Target_Label'].isin(["1 (Winner)", "0 (Loser)"]) & (df['Max_Profit_%'].astype(str).isin(['0', '0.0', '']))
    df_backfill = df[mask_needs_backfill].copy()

    if df_backfill.empty:
        print("✅ No historical records need backfilling. Your database is fully up to date.")
        return

    print(f"🔍 Found {len(df_backfill)} historical records missing volatility metrics. Processing...")
    df_backfill['Date'] = pd.to_datetime(df_backfill['Date'])
    records_updated = 0

    # 3. Re-simulate the historical trades
    for index, row in df_backfill.iterrows():
        sym = row['Symbol']
        ticker = f"{sym}.NS"
        entry_price = float(row['Price'])
        veto_date = row['Date']
        
        try:
            # Download a 15-day window to ensure we capture the full 8-trading-day lifespan
            end_date = veto_date + datetime.timedelta(days=15)
            stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
            
            if stock_data.empty or 'Close' not in stock_data.columns: continue
                
            post_data = stock_data[stock_data.index.tz_localize(None) >= veto_date]
            if post_data.empty: continue

            # Setup the trackers
            highest_seen = entry_price
            trade_active = True
            max_p = 0.0
            max_d = 0.0
            
            # We must recreate the exact 3-5-3 journey so we stop tracking extremes AFTER the trade would have closed
            for date, price_data in post_data.iterrows():
                if not trade_active: break
                
                # Handle pandas multi-index vs single-index yfinance returns safely
                curr_price = float(price_data['Close'].iloc[0]) if isinstance(price_data['Close'], pd.Series) else float(price_data['Close'])
                daily_high = float(price_data['High'].iloc[0]) if isinstance(price_data['High'], pd.Series) else float(price_data['High'])
                daily_low = float(price_data['Low'].iloc[0]) if isinstance(price_data['Low'], pd.Series) else float(price_data['Low'])

                # Track the highest point seen so far for the trailing stop
                if daily_high > highest_seen: highest_seen = daily_high
                    
                # Calculate the raw extremes for this specific day
                current_peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                current_low_pct = ((daily_low - entry_price) / entry_price) * 100

                # Log the absolute maximums reached during the trade's active lifespan
                if current_peak_pct > max_p: max_p = current_peak_pct
                if current_low_pct < max_d: max_d = current_low_pct
                
                live_pct = ((curr_price - entry_price) / entry_price) * 100

                # 3-5-3 Logic Check (To stop tracking if the trade closed)
                if live_pct <= -3.0 and current_peak_pct < 5.0:
                    trade_active = False # Hard stop hit
                elif current_peak_pct >= 5.0:
                    trailing_sl = highest_seen * 0.97
                    if curr_price <= trailing_sl:
                        trade_active = False # Trailing stop hit

                # 8-Day Time Decay Check
                if (date.tz_localize(None) - veto_date).days >= 8:
                    trade_active = False 

            # Push the final math directly into the master dataframe
            df.at[index, 'Max_Profit_%'] = round(max_p, 2)
            df.at[index, 'Max_Drawdown_%'] = round(max_d, 2)
            records_updated += 1
            
            print(f"   ✔️ BACKFILLED: {sym} | Peak: +{max_p:.2f}% | Drawdown: {max_d:.2f}%")
            time.sleep(0.5) # Prevent Yahoo API ban

        except Exception as e:
            print(f"   ❌ Error evaluating {sym}: {e}")

    # 4. Push updates to the Cloud
    if records_updated > 0:
        print(f"\n🚀 Pushing {records_updated} updated historical records to Google Sheets...")
        if sync_ghost_labels_to_cloud(df):
            print("✅ SUCCESS! Legacy data is fully normalized.")
        else:
            print("❌ FAILED to write to Google Sheets.")

if __name__ == "__main__":
    run_historical_backfill()
