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

# Market Hours: 9:15 AM - 3:30 PM
is_open = (now.weekday() < 5) and (9 <= now.hour < 16)
if (now.hour == 9 and now.minute < 15) or (now.hour == 15 and now.minute > 30):
    is_open = False

st_autorefresh(interval=15000 if is_open else 60000, key="elite_sync")

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

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("🛡️ Strategy Settings")
    cap = st.number_input("Total Capital", value=50000)
    risk_p = st.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)
    st.info("Hover over table headers for parameter explanations.")

# --- 4. DATA ENGINE ---
NIFTY_50 = ["ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"]

@st.cache_data(ttl=30)
def get_elite_data():
    h = yf.download(NIFTY_50 + ["^NSEI"], period="1y", interval="1d", progress=False)
    l = yf.download(NIFTY_50, period="1d", interval="1m", progress=False)
    return h, l

try:
    with st.spinner("Analyzing Elite Setups..."):
        h_data, l_data = get_elite_data()
    
    n_perf = (h_data['Close']['^NSEI'].iloc[-1] / h_data['Close']['^NSEI'].iloc[-63]) - 1
    results = []

    for t in NIFTY_50:
        try:
            hc, lc = h_data['Close'][t].dropna(), l_data['Close'][t].dropna()
            price = float(lc.iloc[-1]) if not lc.empty else float(hc.iloc[-1])
            
            dma200 = hc.rolling(200).mean().iloc[-1]
            delta = hc.diff()
            rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
            adr = ((h_data['High'][t] - h_data['Low'][t]) / h_data['Low'][t]).tail(20).mean() * 100
            tightness = ((hc.tail(5).max() - hc.tail(5).min()) / hc.tail(5).min()) * 100
            vol_m = h_data['Volume'][t].iloc[-1] / h_data['Volume'][t].tail(20).mean()
            rs_b = (hc.iloc[-1] / hc.iloc[-63]) - 1 > n_perf

            is_buy = (price > dma200 and 40 < rsi < 65)
            grade = "WAIT"
            if is_buy:
                grade = "C (Basic)"
                if rs_b and vol_m > 1.1: grade = "B (Strong)"
                if tightness < 4.0 and adr > 2.0: grade = "A (Elite)"

            stop = float(h_data['Low'][t].tail(20).min()) * 0.985
            risk_ps = price - stop
            qty = int((cap * (risk_p / 100)) // risk_ps) if risk_ps > 0 else 0
            if qty == 0 and cap >= price: qty = 1
            profit = round(qty * (risk_ps * 2), 2)

            results.append({
                "Stock": t.replace(".NS", ""),
                "Signal": grade,
                "Price": round(price, 2),
                "StopLoss": round(stop, 2),
                "Profit": profit,
                "ADR%": round(adr, 2),
                "Tight%": round(tightness, 2),
                "Vol": f"{vol_m:.1f}x"
            })
        except: continue

    df = pd.DataFrame(results)
    grade_map = {"A (Elite)": 0, "B (Strong)": 1, "C (Basic)": 2, "WAIT": 3}
    df['sort'] = df['Signal'].map(grade_map)
    df = df.sort_values('sort').drop(columns=['sort'])
    
    # --- SMART INFO TOOLTIPS ---
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True, 
        height=600,
        column_config={
            "Signal": st.column_config.TextColumn("Signal", help="Grade A: Institutional buy + Tight Base. Grade B: Strong RS. Grade C: Basic trend."),
            "StopLoss": st.column_config.NumberColumn("StopLoss", help="Exit point based on 20-day low. Protects your capital."),
            "Profit": st.column_config.NumberColumn("Profit", help="Calculated for 1:2 Risk-Reward based on your capital and risk settings."),
            "ADR%": st.column_config.NumberColumn("ADR%", help="Average Daily Range. High ADR (>2.5%) means high speed/volatility."),
            "Tight%": st.column_config.NumberColumn("Tight%", help="VCP Check. Below 4% means the price is consolidating and ready to explode."),
            "Vol": st.column_config.TextColumn("Vol", help="Institutional Volume. Shows if today's volume is greater than the 20-day average.")
        }
    )

except Exception as e:
    st.error(f"Syncing... {e}")
