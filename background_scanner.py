import yfinance as yf
import pandas as pd
import datetime
import pytz
import os
import sys

# 🟢 ADD THIS LINE TO IMPORT THE CLOUD FUNCTION
from database import log_ai_veto

# --- 1. SYSTEM BOOT ---
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")
current_time_str = now.strftime("%H:%M")

print(f"🤖 Shadow Node Booting Up: {today_str} at {current_time_str} IST")

# --- 2. HOLIDAY SENSOR (Safety Lock) ---
print("Checking Market Status...")
nifty_check = yf.download("RELIANCE.NS", period="1d", progress=False)

if nifty_check.empty:
    print("Market Closed/Holiday Detected (No Data). Shutting down harvester.")
    sys.exit()

latest_date_in_data = nifty_check.index[-1].strftime("%Y-%m-%d")

if latest_date_in_data != today_str:
    print(f"Market Closed/Holiday Detected. Data is from {latest_date_in_data}, not {today_str}. Shutting down.")
    sys.exit()

print("Market is active. Proceeding with data harvest...")

# --- 3. THE BROAD MARKET UNIVERSE ---
ticker_string = "RELIANCE,TCS,HDFCBANK,ICICIBANK,BHARTIARTL,SBIN,INFY,LICI,ITC,HINDUNILVR,LT,BAJFINANCE,HCLTECH,MARUTI,SUNPHARMA,TATAMOTORS,M&M,ULTRACEMCO,NTPC,POWERGRID,ASIANPAINT,COALINDIA,ONGC,BAJAJFINSV,ADANIENT,HAL,KOTAKBANK,TITAN,ADANIPORTS,WIPRO,JSWSTEEL,SIEMENS,TATASTEEL,IRFC,LTIM,ZOMATO,IOC,BAJAJ-AUTO,GRASIM,TECHM,BEL,HINDZINC,TRENT,CHOLAFIN,VEDL,DLF,INDUSINDBK,PFC,SBILIFE,RECLTD,HINDALCO,GODREJCP,EICHERMOT,DRREDDY,TVSMOTOR,CIPLA,DIVISLAB,GAIL,INDIGO,APOLLOHOSP,BPCL,BRITANNIA,BOSCHLTD,CUMMINSIND,PIDILITIND,SHRIRAMFIN,TORNTPHARM,HEROMOTOCO,MANAPPURAM,LUPIN,JINDALSTEL,CGPOWER,POLYCAB,BHEL,NHPC,YESBANK,IDFCFIRSTB,SUZLON,RVNL,IREDA,JIOFIN,PAYTM,NYKAA,POLICYBZR"
tickers = [f"{t}.NS" for t in ticker_string.split(",")]
all_symbols = tickers + ["^NSEI", "^INDIAVIX"]

# --- 4. BULK DOWNLOAD (API Shield) ---
print("Downloading Market Data...")
try:
    data = yf.download(all_symbols, period="1y", interval="1d", threads=True, progress=False)
    closes, volumes, highs, opens = data['Close'], data['Volume'], data['High'], data['Open']
except Exception as e:
    print(f"API Error: {e}")
    sys.exit()

# Extract Market Context (Added Nifty_5D)
nifty_trend, nifty_5d, vix = 0.0, 0.0, 15.0
try:
    nifty_closes = closes['^NSEI'].dropna()
    nifty_trend = round(((nifty_closes.iloc[-1] - nifty_closes.iloc[-2]) / nifty_closes.iloc[-2]) * 100, 2)
    if len(nifty_closes) >= 6:
        nifty_5d = round(((nifty_closes.iloc[-1] - nifty_closes.iloc[-6]) / nifty_closes.iloc[-6]) * 100, 2)
    vix = round(float(closes['^INDIAVIX'].dropna().iloc[-1]), 2)
except: pass

# --- 5. THE QUANT ENGINE (Upgraded Math) ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    # 🟢 FIX 1: Wilder's Exponential Smoothing
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = loss.replace(0, 1e-10)
    rs = gain / loss
    return 100 - (100 / (1 + rs))

results = []
print("Crunching Quantitative Metrics...")

for ticker in tickers:
    try:
        if ticker not in closes.columns: continue
        c_series = closes[ticker].dropna()
        v_series = volumes[ticker].dropna()
        h_series = highs[ticker].dropna()
        o_series = opens[ticker].dropna()

        if len(c_series) < 200: continue

        curr_price = float(c_series.iloc[-1])
        curr_open = float(o_series.iloc[-1]) 
        curr_vol = float(v_series.iloc[-1])
        vol_sma20 = float(v_series.rolling(20).mean().iloc[-1])

        if vol_sma20 == 0: continue

        c_rvol = round(curr_vol / vol_sma20, 2)
        c_rsi = round(float(calculate_rsi(c_series).iloc[-1]), 2)

        sma200 = float(c_series.rolling(200).mean().iloc[-1])
        sma200_dist = round(((curr_price - sma200) / sma200) * 100, 2)

        sma20 = float(c_series.rolling(20).mean().iloc[-1])
        sma20_dist = round(((curr_price - sma20) / sma20) * 100, 2)

        daily_high = float(h_series.iloc[-1])
        candle_top = max(curr_price, curr_open)
        wick_reject = round(((daily_high - candle_top) / daily_high) * 100, 2) if daily_high > 0 else 0.0

        # 🟢 FIX 2: Added Composite Features
        c_trap_score = round((c_rvol * wick_reject) / (1 + abs(sma20_dist)), 2)
        c_mom_vel = round(c_rsi * c_rvol, 2)

        # AI FILTER
        if c_rvol > 1.2 or c_rsi > 60 or c_rsi < 40 or sma20_dist < -5:
            symbol = ticker.replace(".NS", "")
            results.append({
                "Date": today_str, "Time": current_time_str, "Symbol": symbol,
                "Nifty_Trend": nifty_trend, "VIX": vix, "RVol": c_rvol, "RSI": c_rsi,
                "SMA200_Dist": sma200_dist, "SMA20_Dist": sma20_dist, 
                "Wick_Reject": wick_reject, "Nifty_5D": nifty_5d, 
                "Trap_Score": c_trap_score, "Momentum_Velocity": c_mom_vel, 
                "Price": round(curr_price, 2)
            })
    except: continue

# --- 6. SECURE DATA TO CLOUD ---
if results:
    print(f"✅ Success! Found {len(results)} anomalies. Pushing directly to the Cloud Vault...")
    
    # Push directly to Google Sheets for V3 Training
    cloud_success = 0
    for trade in results:
        # The AI didn't explicitly veto these (they are background anomalies), 
        # so we pass a neutral 50.0% confidence score for the database structure.
        trade['AI_Confidence'] = 50.0 
        
        if log_ai_veto(trade):
            cloud_success += 1
            
    print(f"☁️ Synced {cloud_success}/{len(results)} anomalies to the Cloud Database.")

else:
    print("⚪ Market is quiet. No anomalies detected.")
