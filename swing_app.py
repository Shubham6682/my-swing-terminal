# ... (Existing indicator math) ...

            is_buy = (price > dma200_v and 40 < rsi_v < 65) # Simplified for explanation
            
            # Risk calculation
            stop_price = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_per_share = price - stop_price
            
            qty = 0
            profit = 0.0
            target_price = 0.0

            if is_buy:
                # Calculate Target (1:2)
                target_price = round(price + (risk_per_share * 2), 2)
                
                # Logic: Ensure we can afford at least 1 share
                if risk_per_share > 0:
                    qty = int((cap * (risk_p / 100)) // risk_per_share)
                    
                    # If Qty is 0 but price is within capital, show 1 share as reference
                    if qty == 0 and cap >= price:
                        qty = 1
                    
                    profit = round(qty * (risk_per_share * 2), 2)

            results.append({
                "Stock": t.replace(".NS", ""),
                "Action": "✅ BUY" if is_buy else "⏳ WAIT",
                "Price": round(price, 2),
                "Stop Loss": round(stop_price, 2),
                "Target": target_price,
                "Qty": qty,
                "Profit": profit,
                "RSI": round(rsi_v, 1)
            })
