import streamlit as st
import joblib
import pandas as pd

# 🟢 FIX 1: Enforce the EXACT column order your model was trained on. 
# (Verify this matches the exact order in your V2 training CSV)
EXPECTED_FEATURES = [
    'RVol', 'RSI', 'SMA200_Dist', 'SMA20_Dist', 'Wick_Reject',
    'Trap_Score', 'Momentum_Velocity', 'VIX', 'Nifty_Trend'
]

@st.cache_resource
def load_ai_brain():
    try:
        model = joblib.load('model_v2_macro.pkl')
        return model
    except Exception as e:
        st.error(f"⚠️ Neural Link Failed: Could not load the AI Brain. {e}")
        return None

# 🟢 FIX 2: Added threshold as an adjustable parameter (defaults to 0.70)
def ask_ai_gatekeeper(ai_model, stock_data, macro_data, threshold=0.70):
    if ai_model is None:
        return False, 0.0

    try:
        # 🟢 FIX 3: Strict float casting with safe defaults if the API passes garbage
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

        # 🟢 FIX 1 (Continued): Build the DataFrame forcing the strict column order
        features = pd.DataFrame([raw_features])[EXPECTED_FEATURES]

        win_probability = ai_model.predict_proba(features)[0][1] 

        confidence_pct = round(win_probability * 100, 2)
        is_approved = win_probability >= threshold
        
        return is_approved, confidence_pct

    except Exception as e:
        # Fail closed on any mathematical or casting errors
        print(f"AI Gatekeeper Inference Error: {e}")
        return False, 0.0
