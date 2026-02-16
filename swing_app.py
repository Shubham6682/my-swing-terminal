# --- TAB 3: ANALYSIS CENTER ---
with tab3:
    st.header("📈 Weekly Performance Review")
    
    if st.session_state.journal:
        df_j = pd.DataFrame(st.session_state.journal)
        df_j['ExitDate'] = pd.to_datetime(df_j['ExitDate'])
        
        # 1. VISUALIZE THE WEEK
        st.subheader("1. This Week's P&L Curve")
        # Filter for current week's data only
        current_week = df_j[df_j['ExitDate'] > (pd.Timestamp(now) - pd.Timedelta(days=7))]
        
        if not current_week.empty:
            # Show the Net P&L for this week
            week_pl = current_week['PnL'].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("Week's Net P&L", f"₹{week_pl:.2f}", delta_color="normal")
            col2.metric("Trades Taken", len(current_week))
            col3.metric("Win Rate", f"{(len(current_week[current_week['PnL']>0])/len(current_week)*100):.1f}%")
            
            st.bar_chart(current_week, x='Symbol', y='PnL')
            
            st.divider()
            
            # 2. HEROES & VILLAINS (Best vs Worst)
            st.subheader("2. Stock Performance Attribution")
            c1, c2 = st.columns(2)
            
            with c1:
                st.write("🏆 **Top Profit Makers**")
                winners = current_week[current_week['PnL'] > 0].sort_values("PnL", ascending=False).head(3)
                if not winners.empty:
                    st.dataframe(winners[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.info("No winners this week.")
                
            with c2:
                st.write("⚠️ **Top Loss Makers**")
                losers = current_week[current_week['PnL'] < 0].sort_values("PnL", ascending=True).head(3)
                if not losers.empty:
                    st.dataframe(losers[['Symbol', 'PnL', 'Result']], use_container_width=True, hide_index=True)
                else: st.success("No losers this week! 🎉")

        else:
            st.info("No closed trades yet this week. Close positions in Tab 2 to see the report.")
            
        st.divider()

        # 3. LONG TERM HISTORY
        st.subheader("3. Monthly Ledger")
        monthly = df_j.set_index('ExitDate').resample('ME')['PnL'].sum().reset_index()
        monthly['ExitDate'] = monthly['ExitDate'].dt.strftime('%B %Y')
        st.dataframe(monthly, use_container_width=True)
        
    else:
        st.info("Your Journal is empty. The analysis will start automatically after your first trade.")
