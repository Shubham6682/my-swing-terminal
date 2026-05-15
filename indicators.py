import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    """
    Calculates the Relative Strength Index (RSI) using Wilder's Smoothing (EMA).
    This exactly matches TradingView and standard broker mathematics.
    """
    delta = series.diff()
    
    # 🟢 FIX 1: Use Wilder's Exponential Smoothing instead of a Simple Moving Average
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    
    # 🟢 FIX 2: Prevent Division by Zero if a stock goes up 'period' days in a row
    loss = loss.replace(0, 1e-10)
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_bollinger_width(series, period=20):
    """
    Calculates the Bollinger Band Width percentage.
    Optimized mathematically: (Upper - Lower) / SMA  =>  (4 * STD) / SMA
    """
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    
    # 🟢 FIX 3: Computationally optimized math with a zero-division failsafe
    sma = sma.replace(0, 1e-10) 
    bb_width = (4 * std) / sma
    
    return bb_widthimport pandas as pd

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_width(series, period=20):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return ((sma + (2 * std)) - (sma - (2 * std))) / sma
