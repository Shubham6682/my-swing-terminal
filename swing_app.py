import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
WATCHLIST = ['SBIN.NS', 'HINDALCO.NS', 'BEL.NS', 'NTPC.NS', 'ASHOKLEY.NS', 
             'ADANIPORTS.NS', 'GAIL.NS', 'ONGC.NS', 'M&M.NS', 'IDFCFIRSTB.NS', 'ANANTRAJ.NS']

# Set page config
st.set_page_config(page_title="Swing Master Terminal", layout="wide")

# Auto-refresh every 5 minutes (300,000 milliseconds)
st_autorefresh(interval=300000, key="datarefresh")

# --- CORE FUNCTIONS ---
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_status():
    now = datetime.datetime.now()
    if now.weekday() > 4: return "🔴 CLOSED (Weekend)"
    start = now.replace(hour=9, minute=15, second=0)
    end = now.replace(hour=15, minute=30, second=0)
    if start <= now <= end: return "🟢 LIVE"
    return "🟡 CLOSED (After Hours)"

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty: return None
        
        # Calculate Indicators
        df['200_DMA'] = df['Close'].rolling(window=200).mean()
        df['RSI'] = calculate_rsi(df)
        
        cmp = round(df['Close'].iloc[-1], 2)
        dma_200 = round(df['200_DMA'].iloc[-1], 2)
        rsi = round(df['RSI'].iloc[-1], 2)
        
        # Logic: Swing Parameters
        is_healthy = cmp > dma_200
        rsi_status = "HOT" if rsi > 70 else ("COLD" if rsi < 40 else "SAFE")
        
        # Risk/Reward Calculation (Hypothetical Entry at CMP)
        # We use the recent 20-day low as a dynamic Stop Loss
        stop_loss = round(df['Close'].tail(20).min() * 0.98, 2)
        risk = cmp - stop_loss
        target = round(cmp + (risk * 2), 2)
        
        buy_zone = "YES" if (is_healthy and rsi_status != "HOT" and cmp > stop_loss) else "WAIT"

        return {
            "Ticker": ticker.replace(".NS", ""),
            "Price": cmp,
            "200 DMA": dma_200,
            "Trend": "Bullish" if is_healthy else "Sick",
            "RSI": rsi,
            "RSI Status": rsi_status,
            "Stop Loss": stop_loss,
            "Target (1:2)": target,
            "Action": buy_zone
        }
    except Exception as e:
        return None

# --- UI LAYOUT ---
st.title("🚀 Professional Swing Trading Terminal")
st.subheader(f"Market Status: {get_market_status()} | Last Update: {datetime.datetime.now().strftime('%H:%M:%S')}")

with st.spinner('Fetching live NSE data...'):
    results = []
    for stock in WATCHLIST:
        data = analyze_stock(stock)
        if data: results.append(data)

df_display = pd.DataFrame(results)

# Formatting for the table
def highlight_buy(val):
    color = '#2ecc71' if val == 'YES' else '#e74c3c'
    return f'background-color: {color}; color: white; font-weight: bold'

st.table(df_display.style.applymap(highlight_buy, subset=['Action']))

st.info("💡 **Entry Rule:** Only enter if 'Action' is YES and a 15-minute candle closes above the Entry Price.")