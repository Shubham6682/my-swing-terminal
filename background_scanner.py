import yfinance as yf
import pandas as pd
import datetime
import pytz
import os

# --- 1. SYSTEM BOOT ---
ist = pytz.timezone('Asia/Kolkata')
now = datetime.datetime.now(ist)
today_str = now.strftime("%Y-%m-%d")
current_time_str = now.strftime("%H:%M")

print(f"🤖 Shadow Node Booting Up: {today_str} at {current_time_str} IST")

# --- 2. THE BROAD MARKET UNIVERSE ---
# Using the top ~150 high-liquidity F&O and Midcap stocks to avoid Yahoo API bans while getting 10x the data
ticker_string = "RELIANCE,TCS,HDFCBANK,ICICIBANK,BHARTIARTL,SBIN,INFY,LICI,ITC,HINDUNILVR,LT,BAJFINANCE,HCLTECH,MARUTI,SUNPHARMA,TATAMOTORS,M&M,ULTRACEMCO,NTPC,POWERGRID,ASIANPAINT,COALINDIA,ONGC,BAJAJFINSV,ADANIENT,HAL,KOTAKBANK,TITAN,ADANIPORTS,WIPRO,JSWSTEEL,SIEMENS,TATASTEEL,IRFC,LTIM,ZOMATO,IOC,BAJAJ-AUTO,GRASIM,TECHM,BEL,HINDZINC,TRENT,CHOLAFIN,VEDL,DLF,INDUSINDBK,PFC,SBILIFE,RECLTD,HINDALCO,GODREJCP,EICHERMOT,DRREDDY,TVSMOTOR,CIPLA,DIVISLAB,GAIL,INDIGO,APOLLOHOSP,BPCL,BRITANNIA,BOSCHLTD,CUMMINSIND,PIDILITIND,SHRIRAMFIN,TORNTPHARM,HEROMOTOCO,MANAPPURAM,LUPIN,JINDALSTEL,CGPOWER,POLYCAB,BHEL,NHPC,YESBANK,IDFCFIRSTB,SUZLON,RVNL,IREDA,JIOFIN,PAYTM,NYKAA,POLICYBZR"
tickers = [f"{t}.NS" for t in ticker_string.split(",")]
all_symbols = tickers + ["^NSEI", "^INDIAVIX"]

# --- 3. BULK DOWNLOAD (API Shield) ---
print("Downloading Market Data...")
try:
    data = yf.download(all_symbols, period="1y", interval="1d", threads=True, progress=False)
    closes, volumes, highs = data['Close'], data['Volume'], data['High']
except Exception as e:
    print(f"API Error: {e}")
    exit()

# Extract Market Context
nifty_trend, vix = 0.0, 15.0
try:
    nifty_closes = closes['^NSEI'].dropna()
    nifty_trend = round(((nifty_closes.iloc[-1] - nifty_closes.iloc[-2]) / nifty_closes.iloc[-2]) * 100, 2)
    vix = round(float(closes['^INDIAVIX'].dropna().iloc[-1]), 2)
except: pass

# --- 4. THE QUANT ENGINE ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
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

        if len(c_series) < 200: continue

        curr_price = float(c_series.iloc[-1])
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
        wick_reject = round(((daily_high - curr_price) / daily_high) * 100, 2) if daily_high > 0 else 0.0

        # 🟢 AI FILTER: Only log "Interesting" anomalies. Ignore boring, flat stocks.
        if c_rvol > 1.2 or c_rsi > 60 or c_rsi < 40 or sma20_dist < -5:
            symbol = ticker.replace(".NS", "")
            results.append({
                "Date": today_str, "Time": current_time_str, "Symbol": symbol,
                "Nifty_Trend": nifty_trend, "VIX": vix, "RVol": c_rvol, "RSI": c_rsi,
                "SMA200_Dist": sma200_dist, "SMA20_Dist": sma20_dist, 
                "Wick_Reject": wick_reject, "Price": round(curr_price, 2)
            })
    except: continue

# --- 5. SECURE DATA TO CSV ---
if results:
    df_results = pd.DataFrame(results)
    file_name = "nifty500_shadow_log.csv"
    
    if os.path.exists(file_name):
        df_results.to_csv(file_name, mode='a', header=False, index=False)
    else:
        df_results.to_csv(file_name, mode='w', header=True, index=False)
    print(f"✅ Success! Logged {len(results)} anomalies to {file_name}.")
else:
    print("⚪ Market is quiet. No anomalies detected.")
