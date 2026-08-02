import os
import streamlit as st
import joblib
import pandas as pd
import xgboost as xgb

# V2 FEATURES
EXPECTED_FEATURES = [
    'RVol', 'RSI', 'SMA200_Dist', 'SMA20_Dist', 'Wick_Reject',
    'Trap_Score', 'Momentum_Velocity', 'VIX', 'Nifty_Trend'
]

# V3 FEATURES
V3_EXPECTED_FEATURES = [
    "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", 
    "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity"
]

@st.cache_resource
def load_ai_brain():
    try:
        model = joblib.load('model_v2_macro.pkl')
        return model
    except Exception as e:
        print(f"⚠️ V2 Brain Failed to Load: {e}")
        return None

@st.cache_resource
def load_v3_brain():
    try:
        # 🟢 ABSOLUTE PATH FIX: Guarantees Streamlit Cloud locates the file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, "v3_xgboost_brain.json")
        
        if not os.path.exists(model_path):
            st.error(f"🚨 V3 File Missing: Could not find 'v3_xgboost_brain.json' at {model_path}")
            return None
            
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        return model
    except Exception as e:
        st.error(f"⚠️ V3 Brain Load Error: {e}")
        return None

def ask_ai_gatekeeper(ai_model, stock_data, macro_data, threshold=0.70):
    if ai_model is None: 
        return False, 0.0
    try:
        raw_features = {
            'RVol': float(stock_data.get('RVol', 1.0)),
            'RSI': float(stock_data.get('RSI', 50.0)),
            'SMA200_Dist': float(stock_data.get('SMA200_Dist', 0.0)),
            'SMA20_Dist': float(stock_data.get('SMA20_Dist', 0.0)),
            'Wick_Reject': float(stock_data.get('Wick_Reject', 0.0)),
            'Trap_Score': float(stock_data.get('Trap_Score', 0.0)),
            'Momentum_Velocity': float(stock_data.get('Momentum_Velocity', 0.0)),
            'VIX': float(macro_data.get('VIX', 15.0)),
            'Nifty_Trend': float(macro_data.get('Nifty_Trend', 0.0))
        }
        features = pd.DataFrame([raw_features])[EXPECTED_FEATURES]
        win_probability = ai_model.predict_proba(features)[0][1] 
        confidence_pct = round(win_probability * 100, 2)
        is_approved = win_probability >= threshold
        return is_approved, confidence_pct
    except Exception as e:
        print(f"V2 Inference Error: {e}")
        return False, 0.0

def ask_v3_challenger(v3_model, stock_data, macro_data, threshold=0.50):
    if v3_model is None: 
        return False, 0.0
    try:
        raw_features = {
            "VIX": float(macro_data.get('VIX', 15.0)),
            "Nifty_Trend": float(macro_data.get('Nifty_Trend', 0.0)),
            "RVol": float(stock_data.get('RVol', 1.0)),
            "RSI": float(stock_data.get('RSI', 50.0)),
            "SMA200_Dist": float(stock_data.get('SMA200_Dist', 0.0)),
            "SMA20_Dist": float(stock_data.get('SMA20_Dist', 0.0)),
            "Wick_Reject": float(stock_data.get('Wick_Reject', 0.0)),
            "Nifty_5D": float(macro_data.get('Nifty_5D', 0.0)),
            "Trap_Score": float(stock_data.get('Trap_Score', 0.0)),
            "Momentum_Velocity": float(stock_data.get('Momentum_Velocity', 0.0))
        }
        features = pd.DataFrame([raw_features])[V3_EXPECTED_FEATURES]
        
        win_probability = v3_model.predict_proba(features)[0][1]
        confidence_pct = round(win_probability * 100, 2)
        is_approved = win_probability >= threshold
        
        return is_approved, confidence_pct
    except Exception as e:
        # 🟢 PRINT INFERENCE ERRORS TO TERMINAL LOGS
        print(f"🚨 V3 Inference Error: {e}")
        return False, 0.0
