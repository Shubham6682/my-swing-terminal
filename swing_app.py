# --- TAB 2: ACTIVE PORTFOLIO (SMART EXIT ENGINE) ---
with tab2:
    if st.session_state.portfolio:
        # ... (Data fetching remains same) ...
        
        for i, trade in enumerate(st.session_state.portfolio):
            try:
                cv = get_price(trade['Ticker'])
                current_profit_pct = ((cv - trade['BuyPrice']) / trade['BuyPrice']) * 100
                
                # --- AUTO-EXIT INTELLIGENCE ---
                new_sl = trade['StopPrice']
                status_msg = "Holding"
                
                # RULE 1: Breakeven (The Free Ride)
                if current_profit_pct > 3.0 and trade['StopPrice'] < trade['BuyPrice']:
                    new_sl = trade['BuyPrice']
                    st.toast(f"🛡️ {trade['Symbol']} is now Risk-Free!")
                
                # RULE 2: Trailing Stop (The Ladder)
                if current_profit_pct > 5.0:
                    # Trail by 2%
                    trail_price = cv * 0.98
                    if trail_price > new_sl:
                        new_sl = trail_price
                        status_msg = "Trailing Up ⬆️"

                # RULE 3: Hard Stop Hit (The Shield)
                if cv < new_sl:
                    status_msg = "❌ STOP LOSS HIT"
                
                # Update the Portfolio in Memory
                st.session_state.portfolio[i]['StopPrice'] = round(new_sl, 2)
                
                # --- DISPLAY ROW ---
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.write(f"**{trade['Symbol']}**")
                c2.write(f"Entry: {trade['BuyPrice']}")
                
                # Dynamic Coloring for P&L
                pl = (cv - trade['BuyPrice']) * trade['Qty']
                c3.metric("LTP", f"{round(cv, 2)}", f"{current_profit_pct:.2f}%")
                c4.metric("Stop Loss", f"{new_sl}", help="Auto-updates based on trailing logic")
                
                # The Exit Button (Manual Override)
                if c5.button(f"✅ CLOSE ({status_msg})", key=f"close_{i}"):
                    # ... (Save to Journal Logic) ...
                    pass # (Keep your existing close logic here)

            except: continue
