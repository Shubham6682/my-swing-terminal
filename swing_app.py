import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Elite Swing Terminal", layout="wide")

ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)

is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

# Initialize Virtual Portfolio in Session State
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 2. INDEX HEADER ---
st.title("🏹 Elite Momentum Terminal")
indices = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
idx_cols = st.columns(len(indices) + 1)

for i, (name, ticker) in enumerate(indices.items()):
    try:
        t_obj = yf.Ticker(ticker)
        df_live = t_obj.history(period="1d", interval="1m")
        df_hist = t_obj.history(period="2d")
        if not df_live.empty and not df_hist.empty:
            curr, prev = df_live['Close'].iloc[-1], df_hist['Close'].iloc[0]
            change = curr - prev
            idx_cols[i].metric(name, f"{curr:,.2f}", f"{change:+.2f} ({(change/prev)*100:+.2f}%)")
    except: idx_cols[i].metric(name, "N/A")

idx_cols[-1].write(f"**{'🟢 OPEN' if is_open else '⚪ CLOSED'}**")
idx_cols[-1].write(f"{now.strftime('%H:%M:%S')} IST")
st.divider()

# --- 3. VIRTUAL PORTFOLIO (PAPER TRADING) ---
st.subheader("🚀 Virtual Portfolio (Practice Mode)")
p_col1, p_col2, p_col3, p_col4 = st.columns([2, 1, 1, 1])

with p_col1: v_ticker = st.text_input("Stock Name:", placeholder="e.g. RELIANCE").upper()
with p_col2: v_qty = st.number_input("Quantity:", min_value=1, value=1)
with p_col3: v_price = st.number_input("Entry Price (₹):", min_value=0.1, value=100.0)
with p_col4: 
    st.write("##")
    if st.button("➕ Execute Virtual Order"):
        if v_ticker:
            st.session_state.portfolio.append({
                "Ticker": f"{v_ticker}.NS",
                "Symbol": v_ticker,
                "Qty": v_qty,
                "BuyPrice": v_price,
                "Date": now.strftime("%Y-%m-%d %H:%M")
            })
            st.toast(f"Virtual Order Placed: {v_ticker}")

if st.session_state.portfolio:
    portfolio_results = []
    total_unrealized_pnl = 0.0
    
    # Fetch current prices for portfolio
    p_tickers = [item['Ticker'] for item in st.session_state.portfolio]
    p_data = yf.download(p_tickers, period="1d", interval="1m", progress=False)['Close']
    
    for item in st.session_state.portfolio:
        try:
            # Handle both single and multiple ticker dataframe structures
            if len(p_tickers) > 1:
                curr_price = p_data[item['Ticker']].dropna().iloc[-1]
            else:
                curr_price = p_data.dropna().iloc[-1]
                
            pnl = (curr_price - item['BuyPrice']) * item['Qty']
            pnl_pct = ((curr_price - item['BuyPrice']) / item['BuyPrice']) * 100
            total_unrealized_pnl += pnl
            
            portfolio_results.append({
                "Stock": item['Symbol'],
                "Qty": item['Qty'],
                "Buy Price": f"₹{item['BuyPrice']:,.2f}",
                "Current": f"₹{curr_price:,.2f}",
                "P&L (₹)": round(pnl, 2),
                "Change %": f"{pnl_pct:+.2f}%",
                "Value": f"₹{curr_price * item['Qty']:,.2f}"
            })
        except: continue
    
    st.dataframe(pd.DataFrame(portfolio_results), use_container_width=True, hide_index=True)
    
    # Summary Metrics
    s_col1, s_col2 = st.columns(2)
    pnl_color = "normal" if total_unrealized_pnl >= 0 else "inverse"
    s_col1.metric("Total Unrealized P&L", f"₹{total_unrealized_pnl:,.2f}", delta=f"{total_unrealized_pnl:,.2f}", delta_color=pnl_color)
    if st.button("Clear Portfolio"):
        st.session_state.portfolio = []
        st.rerun()

st.divider()

# --- 4. DATA ENGINE & MAIN SCANNER ---
# (Rest of the Nifty 50 logic remains the same below for your reference)
