import pandas as pd

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
