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
    
    # --- TIMEFRAME FILTER ---
    st.markdown("#### 📅 Select Timeframe")
    time_filter = st.radio("Analyze Data For:", ["All Time", "Last 7 Days", "Last 30 Days"], horizontal=True)
    
    # Wipe the cached Action Plan if the timeframe changes to prevent desync
    if 'current_filter' not in st.session_state or st.session_state.current_filter != time_filter:
        st.session_state.enrichment_run = False
        st.session_state.enrichment_data = pd.DataFrame()
        st.session_state.current_filter = time_filter

    now = pd.Timestamp.now()
    if time_filter == "Last 7 Days":
        df = df[df['ExitDate'] >= (now - pd.Timedelta(days=7))]
    elif time_filter == "Last 30 Days":
        df = df[df['ExitDate'] >= (now - pd.Timedelta(days=30))]
    
    # Filter only closed trades
    closed_trades = df[df['ExitDate'].notnull() & (df['Result'] != '')].copy()
    
    if closed_trades.empty:
        st.warning(f"Not enough closed trades in the '{time_filter}' timeframe to run advanced analytics.")
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

    # 2.5 Strategy Showdown
    st.markdown("#### ⚔️ Strategy Showdown")
    if 'Strategy' in closed_trades.columns:
        strategy_group = closed_trades.groupby('Strategy').agg(
            Total_Trades=('Symbol', 'count'),
            Net_Profit=('PnL', 'sum'),
            Avg_PnL=('PnL', 'mean')
        ).reset_index()
        
        strategy_group['Net_Profit'] = strategy_group['Net_Profit'].apply(lambda x: f"₹{x:,.2f}")
        strategy_group['Avg_PnL'] = strategy_group['Avg_PnL'].apply(lambda x: f"₹{x:,.2f}")
        st.dataframe(strategy_group, use_container_width=True, hide_index=True)

    st.divider()

    # 3. Time-of-Day Optimization (Filtered for "Unknown" trades)
    st.markdown("#### ⏱️ Time-of-Day Optimization")
    time_data = closed_trades[closed_trades['EntryTime'].notnull() & (closed_trades['EntryTime'] != '')].copy()
    
    if not time_data.empty:
        time_data['EntryHour'] = pd.to_datetime(time_data['EntryTime'], format='%H:%M:%S', errors='coerce').dt.hour
        
        def categorize_time(hour):
            if pd.isna(hour): return None
            if hour < 11: return "1. Morning (9:15 - 11:00)"
            elif hour < 14: return "2. Midday (11:00 - 14:00)"
            else: return "3. Afternoon (14:00 - 15:30)"
            
        time_data['Time_Zone'] = time_data['EntryHour'].apply(categorize_time)
        time_data = time_data.dropna(subset=['Time_Zone'])
        
        time_stats = time_data.groupby('Time_Zone').agg(
            Trades=('Symbol', 'count'),
            Win_Rate=('PnL', lambda x: f"{(len(x[x>0])/len(x))*100:.1f}%" if len(x) > 0 else "0.0%"),
            Net_Profit=('PnL', 'sum')
        ).reset_index()
        
        time_stats['Net_Profit'] = time_stats['Net_Profit'].apply(lambda x: f"₹{x:,.2f}")
        st.dataframe(time_stats, use_container_width=True, hide_index=True)
    else:
        st.info("No trades with valid timestamps found for time optimization.")
        
    st.divider()

    # 4. Level 2 Enrichment: MFE & MAE
    st.markdown("#### 🚀 Level 2 Analytics: Intraday Excursion (MFE / MAE)")
    st.caption("Reverse-engineers historical 1-minute data (Last 7 days only) to analyze efficiency.")
    
    if 'enrichment_run' not in st.session_state:
        st.session_state.enrichment_run = False
        st.session_state.enrichment_data = pd.DataFrame()

    c1, c2 = st.columns([1, 1])
    
    if c1.button("🔄 Run/Refresh Post-Trade Enrichment"):
        st.session_state.enrichment_run = True
        with st.spinner("Firing up the time machine..."):
            try:
                tickers = closed_trades['Ticker'].dropna().unique().tolist()
                hist_data = yf.download(tickers, period="7d", interval="1m", progress=False, threads=True)
                
                enriched_results = []
                for _, trade in closed_trades.iterrows():
                    sym, tck = trade['Symbol'], trade['Ticker']
                    buy_px, exit_px = float(trade['BuyPrice']), float(trade['ExitPrice'])
                    mfe, mae = buy_px, buy_px
                    
                    if not hist_data.empty and tck in hist_data['High'].columns:
                        try:
                            entry_dt = pd.to_datetime(f"{trade['Date']} {trade['EntryTime']}").tz_localize(None)
                            exit_dt = pd.to_datetime(f"{trade['ExitDate']} {trade['ExitTime']}").tz_localize(None)
                            
                            t_high = hist_data['High'][tck].dropna()
                            t_low = hist_data['Low'][tck].dropna()
                            t_high.index = t_high.index.tz_localize(None)
                            t_low.index = t_low.index.tz_localize(None)
                            
                            window_h = t_high[(t_high.index >= entry_dt) & (t_high.index <= exit_dt)]
                            window_l = t_low[(t_low.index >= entry_dt) & (t_low.index <= exit_dt)]
                            
                            if not window_h.empty: mfe = window_h.max()
                            if not window_l.empty: mae = window_l.min()
                        except: pass 
                    
                    if mfe == buy_px and exit_px > buy_px: mfe = exit_px
                    if mae == buy_px and exit_px < buy_px: mae = exit_px
                    
                    left_pct = ((mfe - exit_px) / buy_px) * 100 if mfe > exit_px else 0.0
                    
                    enriched_results.append({
                        "Date": trade['Date'], "Symbol": sym, "Entry": f"₹{buy_px:,.2f}",
                        "Exit": f"₹{exit_px:,.2f}", "Peak Price (MFE)": f"₹{mfe:,.2f}",
                        "Lowest Dip (MAE)": f"₹{mae:,.2f}", "Missed Profit %": f"{max(0, left_pct):.2f}%"
                    })
                st.session_state.enrichment_data = pd.DataFrame(enriched_results)
            except Exception as e:
                st.error(f"Enrichment Failed: {e}")

    if c2.button("❌ Close Enrichment Table"):
        st.session_state.enrichment_run = False
        st.session_state.enrichment_data = pd.DataFrame()
        st.rerun()

    if st.session_state.enrichment_run and not st.session_state.enrichment_data.empty:
        st.success("✅ Intraday Enrichment Complete! (Data Cached)")
        st.dataframe(st.session_state.enrichment_data, use_container_width=True, hide_index=True)
        
        # --- 5. AUTOMATED AI CONCLUSION & ACTION PLAN ---
        st.divider()
        st.markdown("### 🧠 Automated Quant Conclusion & Action Plan")
        
        en_df = st.session_state.enrichment_data.copy()
        en_df['Missed_Float'] = en_df['Missed Profit %'].str.replace('%', '').astype(float)
        avg_missed = en_df['Missed_Float'].mean()
        
        recs = []
        if avg_missed > 2.5:
            recs.append(f"🔴 **TIGHTEN TRAILING STOP:** You are leaving **{avg_missed:.2f}%** on the table. Consider lowering the 6.0% threshold.")
        elif avg_missed < 1.0:
            recs.append(f"🟢 **TRAILING STOP HEALTHY:** You are catching peaks perfectly ({avg_missed:.2f}% missed).")
        
        if 'time_stats' in locals() and not time_stats.empty:
            time_stats['WF'] = time_stats['Win_Rate'].str.replace('%', '').astype(float)
            worst = time_stats.loc[time_stats['WF'].idxmin()]
            if worst['WF'] < 35.0 and worst['Trades'] >= 3:
                recs.append(f"🔴 **IMPLEMENT TIME LOCK:** The **{worst['Time_Zone']}** session is underperforming ({worst['Win_Rate']}).")

        if win_rate < 40.0 and rr_ratio < 1.2:
            recs.append("🔴 **SYSTEM BLEED:** High churn, low reward. Widen initial stop or tighten entry criteria.")
        elif win_rate >= 50.0:
            recs.append("🟢 **SYSTEM HEALTHY:** Math is currently in your favor.")

        for r in recs:
            st.markdown(r)
        if not recs:
            st.info("More closed trades required for meaningful analysis.")
