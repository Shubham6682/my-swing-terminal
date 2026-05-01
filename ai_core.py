import streamlit as st
import joblib
import pandas as pd

@st.cache_resource
def load_ai_brain():
    try:
        model = joblib.load('model_v2_macro.pkl')
        return model
    except Exception as e:
        st.error(f"⚠️ Neural Link Failed: Could not load the AI Brain. {e}")
        return None

def ask_ai_gatekeeper(ai_model, stock_data, macro_data):
    if ai_model is None:
        return False, 0.0

    features = pd.DataFrame([{
        'RVol': stock_data['RVol'],
        'RSI': stock_data['RSI'],
        'SMA200_Dist': stock_data['SMA200_Dist'],
        'SMA20_Dist': stock_data['SMA20_Dist'],
        'Wick_Reject': stock_data['Wick_Reject'],
        'Trap_Score': stock_data['Trap_Score'],
        'Momentum_Velocity': stock_data['Momentum_Velocity'],
        'VIX': macro_data['VIX'],
        'Nifty_Trend': macro_data['Nifty_Trend']
    }])

    win_probability = ai_model.predict_proba(features)[0][1] 

    if win_probability >= 0.70:
        return True, round(win_probability * 100, 2)
    else:
        return False, round(win_probability * 100, 2)
