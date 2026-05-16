import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

# Added the new sync function to the imports
from database import fetch_sheet_data, sync_ghost_labels_to_cloud

def render_ghost_portfolio():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)

    st.markdown("### 👻 The Ghost Portfolio (Forward-Return Tracker)")
    st.caption("Tracks vetoed setups to see what the AI missed, creating a labeled feedback loop for V3 training.")
    
    with st.expander("⚙️ Ghost Tracker Parameters (T+N Rules)", expanded=False):
        c1, c2, c3 = st.columns(3)
        target_pct = c1.slider("Target Profit (%)", 2.0, 10.0, 5.0, step=0.5)
        stop_pct = c2.slider("Stop Loss (%)", -1.0, -5.0, -3.0, step=0.5)
        max_days = c3.slider("Max Lifespan (T+N Days)", 3, 15, 8)

    # --- 1. LOAD THE VETO DATA ---
    with st.spinner("Loading AI Vetoes from Cloud..."):
        raw_veto_data = fetch_sheet_data("AI_Veto_Log")

    if not raw_veto_data:
        st.info("Ghost Portfolio is empty. No vetoes logged yet.")
        return

    df = pd.DataFrame(raw_veto_data)
    
    df['Date'] = pd.to_datetime(df['Date'])
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    
    # We copy the full dataframe (no filtering out old trades) so we can evaluate them for Time Decay
    df_active = df.copy()

    # --- 2. FETCH LIVE MARKET DATA ---
    unique_tickers = [f"{sym}.NS" for sym in df_active['Symbol'].unique()]
    
    with st.spinner(f"Syncing live market data for {len(unique_tickers)} vetoed stocks..."):
        try:
            live_data = yf.download(unique_tickers, period="1mo", progress=False)['Close']
        except Exception as e:
            st.error(f"Market Data Error: {e}")
            live_data = pd.DataFrame()

    # --- 3. THE AI LABELING ENGINE ---
    results = []
    missed_winners = 0
    dodged_bullets = 0
    in_progress = 0
    
    # Trailing Activation Target linked to your Streamlit slider
    trail_activation_pct = target_pct  
    
    for index, row in df_active.iterrows():
        sym = row['Symbol']
        ticker = f"{sym}.NS"
        entry_price = row['Price']
        veto_date = row['Date'].strftime("%Y-%m-%d")
        
        current_price = entry_price
        
        if not live_data.empty:
            if len(unique_tickers) == 1:
                stock_series = live_data.dropna()
            else:
                stock_series = live_data[ticker].dropna() if ticker in live_data.columns else pd.Series()
            
            if not stock_series.empty:
                post_veto_data = stock_series[stock_series.index.tz_localize(None) >= row['Date']]
                
                if not post_veto_data.empty:
                    current_price = float(post_veto_data.iloc[-1])
                    
                    # Chronological Trailing Simulator Initial State
                    highest_seen = entry_price
                    trade_active = True
                    final_exit_price = current_price
                    status = "In Progress"
                    truth_label = "⏳ TBD"
                    current_active_sl = entry_price * (1 - (abs(stop_pct)/100))
                    
                    # Track days elapsed for the Time Decay check
                    days_elapsed = (now.replace(tzinfo=None) - row['Date']).days

                    for date, price in post_veto_data.items():
                        if not trade_active: break
                        
                        if price > highest_seen:
                            highest_seen = price
                            
                        live_pct = ((price - entry_price) / entry_price) * 100
                        peak_pct = ((highest_seen - entry_price) / entry_price) * 100
                        
                        # Condition 1: Hard Stop Loss Hit BEFORE trailing activates
                        if live_pct <= stop_pct and peak_pct < trail_activation_pct:
                            final_exit_price = price
                            trade_active = False
                            status = "🛡️ Dodged Bullet (Stop Hit)"
                            truth_label = "0 (Loser)"
                            dodged_bullets += 1
                            
                        # Condition 2: Trailing Stop Logic (Activated at target_pct)
                        elif peak_pct >= trail_activation_pct:
                            # The stop trails behind the highest peak by the SL percentage
                            trailing_sl_price = highest_seen * (1 - (abs(stop_pct)/100))
                            current_active_sl = trailing_sl_price
                            
                            if price <= trailing_sl_price:
                                final_exit_price = price
                                trade_active = False
                                status = "🚨 Missed Winner (Trailed Out)"
                                truth_label = "1 (Winner)"
                                missed_winners += 1

                    # 🟢 Reality Check 2: Expiration Logic (Time Decay)
                    if trade_active:
                        if days_elapsed >= max_days:
                            final_exit_price = current_price
                            status = "🛡️ Dodged Bullet (Time Decay)"
                            truth_label = "0 (Loser)"
                            dodged_bullets += 1
                        else:
                            in_progress += 1

                    # Calculate final simulated metrics
                    simulated_pnl = ((final_exit_price - entry_price) / entry_price) * 100
                    max_gain = ((highest_seen - entry_price) / entry_price) * 100
                    
                    results.append({
                        "Date Vetoed": veto_date,
                        "Symbol": sym,
                        "Veto Price": round(entry_price, 2),
                        "Simulated Exit": round(final_exit_price, 2),
                        "Current SL Price": round(current_active_sl, 2),
                        "Ghost PnL (%)": round(simulated_pnl, 2),
                        "Peak Reached (%)": round(max_gain, 2),
                        "Status": status,
                        "AI_Confidence": row.get('AI_Confidence', 0),
                        "V3_Truth_Label": truth_label
                    })

    df_results = pd.DataFrame(results)
    
    # --- 4. RENDER UI DASHBOARD ---
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("🚨 Missed Winners (AI was wrong)", missed_winners)
    c2.metric("🛡️ Dodged Bullets (AI was right)", dodged_bullets)
    c3.metric("⏳ Still Chopping", in_progress)
    
    def highlight_status(s):
        if 'Missed Winner' in str(s.get('Status', '')): return ['background-color: #f8d7da; color: #721c24'] * len(s)
        elif 'Dodged Bullet' in str(s.get('Status', '')): return ['background-color: #d4edda; color: #155724'] * len(s)
        else: return [''] * len(s)

    if not df_results.empty:
        st.dataframe(df_results.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)

    # --- 5. CLOUD SYNC LOGIC FOR V3 PIPELINE ---
    if not df_results.empty:
        completed_trades = df_results[df_results['V3_Truth_Label'] != "⏳ TBD"]
        if not completed_trades.empty:
            st.divider()
            st.markdown("### 💾 V3 Training Pipeline")
            st.caption(f"✅ The AI has {len(completed_trades)} definitive labels ready for V3 training.")
            
            df_original = pd.DataFrame(raw_veto_data).copy()
            label_mapping = dict(zip(df_results['Symbol'] + df_results['Date Vetoed'], df_results['V3_Truth_Label']))
            
            raw_dates = pd.to_datetime(df_original['Date']).dt.strftime("%Y-%m-%d")
            df_original['V3_Truth_Label'] = (df_original['Symbol'] + raw_dates).map(label_mapping)
            df_original['V3_Truth_Label'] = df_original['V3_Truth_Label'].fillna("⏳ TBD")
            
            c1, c2 = st.columns([1, 3])
            if c1.button("🔄 Sync Labels to Cloud DB", use_container_width=True):
                with st.spinner("Writing truth labels back to Google Sheets..."):
                    if sync_ghost_labels_to_cloud(df_original):
                        st.success("✅ Training data permanently locked in the Cloud!")
                    else:
                        st.error("❌ Failed to sync to Google Sheets.")
                        
            csv = completed_trades.to_csv(index=False).encode('utf-8')
            c2.download_button(
                label="⬇️ Download Backup CSV",
                data=csv,
                file_name=f"ai_v3_training_data_{now.strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
