import os
import streamlit as st
import pandas as pd
import xgboost as xgb

# V3 FEATURES (Must exactly match your CSV generation script)
V3_EXPECTED_FEATURES = [
    "VIX", "Nifty_Trend", "RVol", "RSI", "SMA200_Dist", 
    "SMA20_Dist", "Wick_Reject", "Nifty_5D", "Trap_Score", "Momentum_Velocity"
]

@st.cache_resource
def load_v3_brain():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, "v3_xgboost_brain.json")
        
        if not os.path.exists(model_path):
            st.error(f"🚨 V3 File Missing: Could not find 'v3_xgboost_brain.json' at {model_path}")
            return None
            
        model = xgb.Booster()
        model.load_model(model_path)
        return model
    except Exception as e:
        st.error(f"⚠️ V3 Brain Load Error: {e}")
        return None

def ask_v3_challenger(v3_model, stock_data, macro_data, threshold=0.60):
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
        
        dmatrix = xgb.DMatrix(features)
        win_probability = float(v3_model.predict(dmatrix)[0])
        
        confidence_pct = round(win_probability * 100, 2)
        is_approved = win_probability >= threshold
        
        return is_approved, confidence_pct
    except Exception as e:
        st.error(f"🚨 V3 Inference Error: {e}")
        return False, 0.0
