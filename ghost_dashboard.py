import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz
from database import fetch_sheet_data

def render_ghost_portfolio():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)

    st.markdown("### 👻 The Ghost Portfolio (Forward-Return Tracker)")
    st.caption("Tracks vetoed setups to see what the AI missed, creating a labeled feedback loop for V3 training.")
    
    # Settings tucked into an expander to keep Tab 3 clean
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
    
    # Clean the dataframe
    df['Date'] = pd.to_datetime(df['Date'])
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    
    # Filter for stocks within our T+N Lifespan
    cutoff_date = now - datetime.timedelta(days=max_days)
    cutoff_date = cutoff_date.replace(tzinfo=None)
    
    df_active = df[df['Date'] >= cutoff_date].copy()

    if df_active.empty:
        st.warning(f"No recent vetoes found within the last {max_days} days.")
        return

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
    
    for index, row in df_active.iterrows():
        sym = row['Symbol']
        ticker = f"{sym}.NS"
        entry_price = row['Price']
        veto_date = row['Date'].strftime("%Y-%m-%d")
        
        current_price = entry_price
        high_since_veto = entry_price
        low_since_veto = entry_price
        
        if not live_data.empty:
            if len(unique_tickers) == 1:
                stock_series = live_data.dropna()
            else:
                stock_series = live_data[ticker].dropna() if ticker in live_data.columns else pd.Series()
            
            if not stock_series.empty:
                post_veto_data = stock_series[stock_series.index.tz_localize(None) >= row['Date']]
                if not post_veto_data.empty:
                    current_price = float(post_veto_data.iloc[-1])
                    high_since_veto = float(post_veto_data.max())
                    low_since_veto = float(post_veto_data.min())

        # Calculate PnL Logic
        max_gain = ((high_since_veto - entry_price) / entry_price) * 100
        max_drawdown = ((low_since_veto - entry_price) / entry_price) * 100
        current_pnl = ((current_price - entry_price) / entry_price) * 100
        
        # Determine Truth Label
        truth_label = "⏳ TBD"
        status = "In Progress"
        
        if max_gain >= target_pct:
            truth_label = "1 (Winner)"
            status = "🚨 Missed Winner"
            missed_winners += 1
        elif max_drawdown <= stop_pct:
            truth_label = "0 (Loser)"
            status = "🛡️ Dodged Bullet"
            dodged_bullets += 1
        else:
            in_progress += 1

        results.append({
            "Date Vetoed": veto_date,
            "Symbol": sym,
            "Veto Price": round(entry_price, 2),
            "Current Price": round(current_price, 2),
            "Live PnL (%)": round(current_pnl, 2),
            "Max Gain (%)": round(max_gain, 2),
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
        if s['Status'] == '🚨 Missed Winner': return ['background-color: #f8d7da; color: #721c24'] * len(s)
        elif s['Status'] == '🛡️ Dodged Bullet': return ['background-color: #d4edda; color: #155724'] * len(s)
        else: return [''] * len(s)

    st.dataframe(df_results.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)

    # Export Logic
    completed_trades = df_results[df_results['V3_Truth_Label'] != "⏳ TBD"]
    if not completed_trades.empty:
        st.caption("✅ The AI has definitive feedback data ready for V3 training.")
        csv = completed_trades.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Cleaned V3 Training Data (CSV)",
            data=csv,
            file_name=f"ai_v3_training_data_{now.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
