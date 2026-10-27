import pandas as pd
import yfinance as yf
import datetime
import time
import streamlit as st

# Import your existing database functions
from database import fetch_sheet_data, sync_ghost_labels_to_cloud

def run_historical_backfill():
    ui_container = st.empty()
    with ui_container.container():
        st.write("🚀 **Booting Historical Data Backfiller...**")
        
        # 1. Fetch the master database
        raw_data = fetch_sheet_data("AI_Veto_Log")
        if not raw_data:
            st.error("❌ Database connection failed or sheet is empty.")
            return

        df = pd.DataFrame(raw_data)

        # Ensure columns exist safely
        if 'Max_Profit_%' not in df.columns: df['Max_Profit_%'] = ""
        if 'Max_Drawdown_%' not in df.columns: df['Max_Drawdown_%'] = ""
        if 'Target_Label' not in df.columns: df['Target_Label'] = ""

        # 2. Filter for finalized trades missing metrics (Robust String Cleaning)
        df['Clean_Label'] = df['Target_Label'].astype(str).str.strip()
        df['Clean_Max'] = df['Max_Profit_%'].astype(str).str.strip().str.lower()
        
        # Finds any label containing 1, 0, Winner, or Loser
        mask_label = df['Clean_Label'].str.contains("1|0|Winner|Loser", case=False, regex=True)
        # Finds missing metrics (blank, zero, or NaN)
        mask_missing = df['Clean_Max'].isin(['0', '0.0', '', 'nan', 'none'])
        
        df_backfill = df[mask_label & mask_missing].copy()

        if df_backfill.empty:
            st.success("✅ No historical records need backfilling. Your database is fully up to date.")
            return

        st.info(f"🔍 Found **{len(df_backfill)}** legacy records missing excursion metrics. Processing...")
        df_backfill['Date'] = pd.to_datetime(df_backfill['Date'])
        records_updated = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 3. Re-simulate the historical trades
        for i, (index, row) in enumerate(df_backfill.iterrows()):
            sym = row['Symbol']
            ticker = f"{sym}.NS"
            entry_price = float(row['Price'])
            veto_date = row['Date']
            
            status_text.text(f"⏳ Simulating {sym}...")
            
            try:
                end_date = veto_date + datetime.timedelta(days=15)
                stock_data = yf.download(ticker, start=veto_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
                
                if stock_data.empty: continue
                
                # 🟢 FIX: Flatten MultiIndex columns from newer yfinance versions
                if isinstance(stock_data.columns, pd.MultiIndex):
                    stock_data.columns = stock_data.columns.get_level_values(0)
                    
                if 'Close' not in stock_data.columns: continue
                    
                post_data = stock_data[stock_data.index.tz_localize(None) >= veto_date]
                if post_data.empty: continue

                highest_seen = entry_price
                trade_active = True
                max_p = 0.0
                max_d = 0.0
                
                for date, price_data in post_data.iterrows():
                    if not trade_active: break
                    
                    curr_price = float(price_data['Close'])
                    daily_high = float(price_data['High'])
                    daily_low = float(price_data['Low'])

                    if daily_high > highest_seen: highest_seen = daily_high
                        
                    current_peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                    current_low_pct = ((daily_low - entry_price) / entry_price) * 100

                    if current_peak_pct > max_p: max_p = current_peak_pct
                    if current_low_pct < max_d: max_d = current_low_pct
                    
                    live_pct = ((curr_price - entry_price) / entry_price) * 100

                    if live_pct <= -3.0 and current_peak_pct < 5.0:
                        trade_active = False 
                    elif current_peak_pct >= 5.0:
                        trailing_sl = highest_seen * 0.97
                        if curr_price <= trailing_sl:
                            trade_active = False 

                    if (date.tz_localize(None) - veto_date).days >= 8:
                        trade_active = False 

                df.at[index, 'Max_Profit_%'] = round(max_p, 2)
                df.at[index, 'Max_Drawdown_%'] = round(max_d, 2)
                records_updated += 1
                
                # Output exactly what it found to the UI!
                st.write(f"✔️ **{sym}** Backfilled: Peak `+{max_p:.2f}%` | Drawdown `{max_d:.2f}%`")
                time.sleep(0.5) 

            except Exception as e:
                st.error(f"❌ Error evaluating {sym}: {e}")
            
            progress_bar.progress((i + 1) / len(df_backfill))

        # 4. Push updates to the Cloud
        if records_updated > 0:
            status_text.text(f"🚀 Pushing {records_updated} updated records to Google Sheets...")
            
            # Clean up the temporary masking columns before pushing to Google Sheets
            df = df.drop(columns=['Clean_Label', 'Clean_Max'])
            
            if sync_ghost_labels_to_cloud(df):
                st.success("✅ **SUCCESS!** Legacy data is fully normalized and saved to the cloud.")
            else:
                st.error("❌ FAILED to write to Google Sheets.")
        else:
            status_text.text("⚠️ No records were successfully updated.")
