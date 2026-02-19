import streamlit as st
import pandas as pd

def run_advanced_audit(journal_df):
    st.markdown("### 🔬 Advanced System Analytics")
    
    # 1. Clean the Data
    df = journal_df.copy()
    if 'PnL' in df.columns:
        df['PnL'] = df['PnL'].astype(str).str.replace(r'[₹,a-zA-Z\s]', '', regex=True)
        df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce').fillna(0)
    
    # Filter only closed trades
    df['ExitDate'] = pd.to_datetime(df['ExitDate'], errors='coerce')
    closed_trades = df[df['ExitDate'].notnull()]
    
    if closed_trades.empty:
        st.warning("Not enough closed trades to run advanced analytics.")
        return

    # 2. Crunch the Core Metrics
    winning_trades = closed_trades[closed_trades['PnL'] > 0]
    losing_trades = closed_trades[closed_trades['PnL'] < 0]
    
    avg_win = winning_trades['PnL'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['PnL'].mean() if not losing_trades.empty else 0
    
    # Calculate Reward-to-Risk Ratio
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    # 3. Display the "Business Sanity" Metrics
    st.markdown("#### ⚖️ Risk vs. Reward")
    c1, c2, c3 = st.columns(3)
    c1.metric("Average Winner", f"₹{avg_win:,.2f}")
    c2.metric("Average Loser", f"₹{avg_loss:,.2f}")
    c3.metric("Reward-to-Risk Ratio", f"{rr_ratio:.2f} : 1", help="Anything above 1.5 is excellent.")
    
    st.divider()
    
    # 4. Strategy A/B Testing
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
