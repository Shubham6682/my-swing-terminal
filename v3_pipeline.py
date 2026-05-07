import pandas as pd
import glob
import os
from database import fetch_sheet_data  # Reusing your existing DB connection!

def build_v3_dataset():
    print("--- 🚀 PHASE 1: Assembling the Answer Key ---")
    
    # 1. LOAD THE GHOST PORTFOLIO (The AI's Mistakes & Correct Vetoes)
    # This automatically finds the latest CSV you downloaded from Tab 3!
    ghost_files = glob.glob("ai_v3_training_data_*.csv")
    if not ghost_files:
        print("❌ ERROR: No Ghost Portfolio export found.")
        print("Please go to Tab 3, wait for trades to complete, and click 'Download Cleaned V3 Training Data'.")
        return None
    
    latest_ghost_file = max(ghost_files, key=os.path.getctime)
    df_ghost = pd.read_csv(latest_ghost_file)
    
    # Clean the Ghost labels: Convert "1 (Winner)" into just the integer 1
    df_ghost['Target_Label'] = df_ghost['V3_Truth_Label'].astype(str).str[0].astype(int)
    
    # Rename 'Date Vetoed' to 'Date' so it perfectly matches our Shadow CSV later
    df_ghost = df_ghost.rename(columns={'Date Vetoed': 'Date'})
    df_ghost_clean = df_ghost[['Date', 'Symbol', 'Target_Label']].copy()
    print(f"✅ Loaded {len(df_ghost_clean)} fully resolved Ghost setups.")

    # 2. LOAD THE LIVE JOURNAL (The AI's Live Trades)
    print("Fetching Live Journal from Cloud Database...")
    # NOTE: Change "Live_Journal" if your Google Sheet tab has a different exact name
    journal_data = fetch_sheet_data("Live_Journal") 
    
    if not journal_data:
        print("⚠️ Warning: No Live Journal data found. Using only Ghost data.")
        df_j_clean = pd.DataFrame(columns=['Date', 'Symbol', 'Target_Label'])
    else:
        df_j = pd.DataFrame(journal_data)
        
        # Clean the PnL and create binary labels (Win = 1, Loss = 0)
        df_j['PnL'] = df_j['PnL'].astype(str).str.replace(r'[₹,a-zA-Z\s]', '', regex=True)
        df_j['PnL'] = pd.to_numeric(df_j['PnL'], errors='coerce').fillna(0)
        df_j['Target_Label'] = df_j['PnL'].apply(lambda x: 1 if x > 0 else 0)
        
        df_j_clean = df_j[['Date', 'Symbol', 'Target_Label']].copy()
        print(f"✅ Loaded {len(df_j_clean)} live executed trades.")

    # 3. CONCATENATE THE UNIVERSES
    # We now have one master list of exactly what the AI got right and wrong
    master_labels = pd.concat([df_ghost_clean, df_j_clean], ignore_index=True)
    
    # Force Date formats to be identical to prevent merge failures
    master_labels['Date'] = pd.to_datetime(master_labels['Date']).dt.strftime('%Y-%m-%d')
    print(f"🔗 Master Answer Key created with {len(master_labels)} total labeled rows.")

    print("\n--- 🚀 PHASE 2: The Grand Merge (Features + Labels) ---")
    
    # 4. LOAD THE SHADOW CSV (The Raw Technical Features)
    # NOTE: Ensure this matches the exact name of your GitHub Actions CSV
    shadow_filename = "nifty500_shadow_log.csv" 
    if not os.path.exists(shadow_filename):
        print(f"❌ ERROR: Cannot find '{shadow_filename}' in the folder.")
        return None
        
    df_shadow = pd.read_csv(shadow_filename)
    df_shadow['Date'] = pd.to_datetime(df_shadow['Date']).dt.strftime('%Y-%m-%d')
    print(f"✅ Loaded Shadow CSV with {len(df_shadow)} historical feature rows.")

    # 5. THE INNER JOIN
    # This mathematically maps the 1s and 0s back to their exact RSI, Volume, etc.
    v3_dataset = pd.merge(df_shadow, master_labels, on=['Date', 'Symbol'], how='inner')
    
    # Drop duplicates just in case a stock triggered twice on the same day
    v3_dataset = v3_dataset.drop_duplicates(subset=['Date', 'Symbol'])
    
    print(f"🎯 MERGE COMPLETE: {len(v3_dataset)} perfect Feature-Label matches found!")
    
    # 6. EXPORT THE GOLD STANDARD DATASET
    export_name = "v3_gold_standard_dataset.csv"
    v3_dataset.to_csv(export_name, index=False)
    print(f"💾 Success! Saved as '{export_name}'. The data is ready for Machine Learning.")
    
    return v3_dataset

if __name__ == "__main__":
    build_v3_dataset()
