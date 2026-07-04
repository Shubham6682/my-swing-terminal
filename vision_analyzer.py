import numpy as np
import pandas as pd
import datetime
import pytz
import gspread
import streamlit as st
import yfinance as yf
from oauth2client.service_account import ServiceAccountCredentials

def connect_to_vision_log():
    """Establishes an isolated connection to the Vision Shadow Log tab."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet_id = st.secrets["gcp_service_account"]["sheet_id"]
    return client.open_by_key(sheet_id).worksheet("Vision_Shadow_Log")

def extract_chart_topography(df, window=5):
    """
    Analyzes the last 6 months of data to extract chart geometry:
    1. Trend Structure (Bullish base vs Downward/Chop)
    2. Overhead Resistance (Distance to the nearest historical major ceiling)
    3. Chaos Score (Standard deviation of daily returns)
    """
    if len(df) < 40:
        return "Unknown", 0.0, 50.0

    # Ensure columns are flat (handles yfinance multi-index variations)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    closes = df['Close'].dropna()
    highs = df['High'].dropna()
    
    current_price = float(closes.iloc[-1])
    
    # 1. Peak Detection (Find historical Swing Highs over the last 120 trading days)
    recent_highs = highs.tail(120)
    peaks = []
    for i in range(window, len(recent_highs) - window):
        sub_sequence = recent_highs.iloc[i - window : i + window + 1]
        if recent_highs.iloc[i] == sub_sequence.max():
            peaks.append(float(recent_highs.iloc[i]))
            
    # 2. Calculate Distance to Nearest Overhead Resistance
    higher_peaks = [p for p in peaks if p > current_price]
    if higher_peaks:
        nearest_resistance = min(higher_peaks)
        overhead_resistance_pct = round(((nearest_resistance - current_price) / current_price) * 100, 2)
    else:
        # If no higher historical peaks exist in 6 months, the sky is clear (defaulting to a safe 20% room)
        overhead_resistance_pct = 20.0
        
    # 3. Assess Foundation Trend Structure
    halfway_mark = len(closes) // 2
    first_half_avg = closes.iloc[:halfway_mark].mean()
    second_half_avg = closes.iloc[halfway_mark:].mean()
    
    if second_half_avg > first_half_avg:
        structure = "Higher_Lows (Bullish Base)"
    else:
        structure = "Choppy/Declining"
        
    # 4. Calculate Chaos Score (Daily volatility standard deviation)
    daily_returns = closes.pct_change().dropna()
    chaos_score = round(float(daily_returns.std() * 100), 2)
    
    return structure, overhead_resistance_pct, chaos_score

def evaluate_and_log_vision_trade(ticker, df):
    """Calculates chart health metrics and pushes them cleanly to the cloud sheet."""
    # Removed the internal try/except so swing_app.py can catch and display errors
    structure, overhead_pct, chaos = extract_chart_topography(df)
    current_price = float(df['Close'].iloc[-1])
    
    # Heuristic scoring engine for the initial data tracking phase
    base_score = 50.0
    if structure == "Higher_Lows (Bullish Base)": 
        base_score += 20
    if overhead_pct >= 5.0: 
        base_score += 15
    if chaos < 1.6: 
        base_score += 10
        
    vision_confidence = min(base_score, 99.0)
    
    ist = pytz.timezone('Asia/Kolkata')
    timestamp = datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    
    row_data = [
        timestamp, ticker, current_price, structure, 
        overhead_pct, chaos, vision_confidence, "⏳ TBD"
    ]
    
    worksheet = connect_to_vision_log()
    worksheet.append_row(row_data)
    print(f"[VISION LAB SUCCESS] Chart metrics archived for {ticker}")
