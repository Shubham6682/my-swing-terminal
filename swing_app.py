import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Institutional Swing Terminal", layout="wide")
st_autorefresh(interval=900000, key="datarefresh") # 15 Minute Window

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nifty50_list():
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
        df = pd.read_csv(url)
        return [s + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS']

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, capital, risk_pct):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200: return None
        
        cmp = float(df['Close'].iloc[-1])
        dma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        
        # --- FII SENTIMENT PROXY ---
        # We calculate the volume-weighted price change over the last 5 days 
        # to see if 'Big Money' is accumulating.
        vol_avg = df['Volume'].tail(20).mean()
        curr_vol = df['Volume'].iloc[-1]
        fii_status = "🟢 Accumulating" if (curr_vol > vol_avg and df['Close'].iloc[-1] > df['Open'].iloc[-1]) else "⚪ Neutral"
        
        # --- RISK MATH ---
        stop_loss = round(float(df['Low'].tail(20).min()) * 0.98, 2)
        risk_per_share = cmp - stop_loss
        if risk_per_share <= 0: return None
        
        qty = int((capital * (risk_pct / 100)) // risk_per_share)
        reward_per_share = risk_per_share * 2
        potential_profit = round(qty * reward_per_share, 2)
        
        # --- VERDICT ---
        action = "✅ BUY" if (cmp > dma_200 and 40 < rsi < 65) else "⏳ WAIT"
        
        return {
            "Stock": ticker.replace(".NS", ""),
            "Price": round(cmp, 2),
            "RSI": round(rsi, 1),
            "FII Sentiment": fii_status,
            "Qty": qty,
            "Target (1:2)": round(cmp + reward_per_share, 2),
            "Profit Goal": potential_profit,
            "Action": action
        }
    except:
        return None

# --- UI INTERFACE ---
st.title("🏹 Institutional Swing Terminal")
st.sidebar.header("🛡️ Strategy Settings")
cap = st.sidebar.number_input("Total Capital (₹)", 100000, step=10000)
risk_p = st.sidebar.slider("Risk per trade (%)", 0.5, 2.0, 1.0, 0.5)

# Scanner Logic
tickers = get_nifty50_list()
results = []
with st.spinner("Syncing with NSE..."):
    for t in tickers:
        res = analyze_stock(t, cap, risk_p)
        if res: results.append(res)

if results:
    df = pd.DataFrame(results)
    buy_only_df = df[df['Action'] == "✅ BUY"]
    
    # --- SIDEBAR METRIC ---
    total_potential = buy_only_df['Profit Goal'].sum()
    st.sidebar.markdown("---")
    st.sidebar.metric("💰 Total Profit Potential", f"₹{total_potential:,.2f}", help="Sum of profits if all BUY signals hit 1:2 targets")
    st.sidebar.caption("Based on current active BUY signals")

    # Main View
    show_all = st.checkbox("Show all Nifty 50 stocks", value=False)
    display_df = df if show_all else buy_only_df
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.error("Data fetch failed. Market may be closed or sync is slow.")

st.info(f"💡 Refreshes every 15 mins. Last sync: {datetime.datetime.now().strftime('%H:%M:%S')}")
