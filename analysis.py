import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import datetime

def run_advanced_audit(journal_df):
    st.markdown("### 🔬 Advanced System Analytics (Level 2)")
    
    # 1. Clean the Data
    df = journal_df.copy()
    if 'PnL' in df.columns:
        df['PnL'] = df['PnL'].astype(str).str.replace(r'[₹,a-zA-Z\s]', '', regex=True)
        df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce').fillna(0)
    
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['ExitDate'] = pd.to_datetime(df['ExitDate'], errors='coerce')
    
    # Filter only closed trades
    closed_trades = df[df['ExitDate'].notnull() & (df['Result'] != '')].copy()
    
    if closed_trades.empty:
        st.warning("Not enough closed trades to run advanced analytics.")
        return

    # 2. Crunch the Core Metrics (Level 1)
    winning_trades = closed_trades[closed_trades['PnL'] > 0]
    losing_trades = closed_trades[closed_trades['PnL'] <= 0]
    
    avg_win = winning_trades['PnL'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['PnL'].mean() if not losing_trades.empty else 0
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    win_rate = (len(winning_trades) / len(closed_trades)) * 100 if len(closed_trades) > 0 else 0
    
    st.markdown("#### ⚖️ The Business Baseline")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate", f"{win_rate:.1f}%")
    c2.metric("Avg Winner", f"₹{avg_win:,.2f}")
    c3.metric("Avg Loser", f"₹{avg_loss:,.2f}")
    c4.metric("Reward-to-Risk", f"{rr_ratio:.2f} : 1")
    
    st.divider()

    # 2.5 Strategy Showdown (The Restored Feature!)
    st.markdown("#### ⚔️ Strategy Showdown")
    if 'Strategy' in closed_trades.columns:
        strategy_group = closed_trades.groupby('Strategy').agg(
            Total_Trades=('Symbol', 'count'),
            Net_Profit=('PnL', 'sum'),
            Avg_PnL=('PnL', 'mean')
        ).reset_index()
        
        # Format the table for display
        strategy_group['Net_Profit'] = strategy_group['Net_Profit'].apply(lambda x: f"₹{x:,.2f}")
        strategy_group['Avg_PnL'] = strategy_group['Avg_PnL'].apply(lambda x: f"₹{x:,.2f}")
        
        st.dataframe(strategy_group, use_container_width=True, hide_index=True)
    else:
        st.info("No strategy data found in older trades.")

    st.divider()

    # 3. Time-of-Day Optimization
    st.markdown("#### ⏱️ Time-of-Day Optimization")
    if 'EntryTime' in closed_trades.columns:
        closed_trades['EntryHour'] = pd.to_datetime(closed_trades['EntryTime'], format='%H:%M:%S', errors='coerce').dt.hour
        
        def categorize_time(hour):
            if pd.isna(hour): return "Unknown"
            if hour < 11: return "1. Morning (9:15 - 11:00)"
            elif hour < 14: return "2. Midday (11:00 - 14:00)"
            else: return "3. Afternoon (14:00 - 15:30)"
            
        closed_trades['Time_Zone'] = closed_trades['EntryHour'].apply(categorize_time)
        
        time_stats = closed_trades.groupby('Time_Zone').agg(
            Trades=('Symbol', 'count'),
            Win_Rate=('PnL', lambda x: f"{(len(x[x>0])/len(x))*100:.1f}%" if len(x) > 0 else "0.0%"),
            Net_Profit=('PnL', 'sum')
        ).reset_index()
        
        time_stats['Net_Profit'] = time_stats['Net_Profit'].apply(lambda x: f"₹{x:,.2f}")
        st.dataframe(time_stats, use_container_width=True, hide_index=True)
    else:
        st.info("No EntryTime data available for time optimization.")
        
    st.divider()

    # 4. Level 2 Enrichment: MFE & MAE 
    st.markdown("#### 🚀 Level 2 Analytics: Intraday Excursion (MFE / MAE)")
    st.caption("Reverse-engineers historical 1-minute data to see how much heat your trades took (MAE) and how much profit was left on the table (MFE).")
    
    if st.button("🔄 Run Post-Trade Enrichment (Downloads Historical Data)"):
        with st.spinner("Firing up the time machine... Downloading historical 1-minute data..."):
            try:
                tickers = closed_trades['Ticker'].dropna().unique().tolist()
                
                # Download 7 days of 1-minute data 
                hist_data = yf.download(tickers, period="7d", interval="1m", progress=False, threads=True)
                
                enriched_results = []
                
                for _, trade in closed_trades.iterrows():
                    sym = trade['Symbol']
                    tck = trade['Ticker']
                    buy_px = float(trade['BuyPrice'])
                    exit_px = float(trade['ExitPrice'])
                    
                    mfe = buy_px
                    mae = buy_px
                    
                    if not hist_data.empty and tck in hist_data['High'].columns:
                        entry_dt_str = f"{trade['Date']} {trade['EntryTime']}"
                        exit_dt_str = f"{trade['ExitDate']} {trade['ExitTime']}"
                        
                        try:
                            # Convert to timezone aware to match yfinance index
                            entry_dt = pd.to_datetime(entry_dt_str).tz_localize('Asia/Kolkata')
                            exit_dt = pd.to_datetime(exit_dt_str).tz_localize('Asia/Kolkata')
                            
                            ticker_high = hist_data['High'][tck].dropna()
                            ticker_low = hist_data['Low'][tck].dropna()
                            
                            trade_window_high = ticker_high[(ticker_high.index >= entry_dt) & (ticker_high.index <= exit_dt)]
                            trade_window_low = ticker_low[(ticker_low.index >= entry_dt) & (ticker_low.index <= exit_dt)]
                            
                            if not trade_window_high.empty:
                                mfe = trade_window_high.max()
                            if not trade_window_low.empty:
                                mae = trade_window_low.min()
                        except:
                            pass 
                    
                    # Fallback approximations for older trades
                    if mfe == buy_px and exit_px > buy_px: mfe = exit_px
                    if mae == buy_px and exit_px < buy_px: mae = exit_px
                    
                    left_on_table_pct = ((mfe - exit_px) / buy_px) * 100 if mfe > exit_px else 0.0
                    
                    enriched_results.append({
                        "Date": trade['Date'],
                        "Symbol": sym,
                        "Entry": f"₹{buy_px:,.2f}",
                        "Exit": f"₹{exit_px:,.2f}",
                        "Peak Price (MFE)": f"₹{mfe:,.2f}",
                        "Lowest Dip (MAE)": f"₹{mae:,.2f}",
                        "Missed Profit %": f"{max(0, left_on_table_pct):.2f}%"
                    })
                
                en_df = pd.DataFrame(enriched_results)
                st.success("✅ Intraday Enrichment Complete!")
                st.dataframe(en_df, use_container_width=True, hide_index=True)
                
                st.info("💡 **Optimization Insight:** Look at the 'Missed Profit %'. If this number is consistently above 3%, your trailing stop is choking the trades and you are exiting too early. Look at 'Lowest Dip (MAE)' to see if you can safely tighten your initial Stop Loss.")
                
            except Exception as e:
                st.error(f"Enrichment Failed. Ensure Yahoo Finance is accessible. Error: {e}")
