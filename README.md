# 🚀 Elite Quant Swing Trading Terminal

An AI-powered, full-stack swing trading automation system for Indian stock markets (NIFTY 500). This system uses dual machine learning models, real-time technical analysis, and cloud-based portfolio tracking to execute intelligent trading strategies with risk management and performance analytics.

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [ML Models](#ml-models)
- [Trading Strategy](#trading-strategy)
- [Database & Cloud Integration](#database--cloud-integration)
- [Performance Analytics](#performance-analytics)
- [Development](#development)

---

## 🎯 Overview

The **Elite Quant Terminal** is an institutional-grade swing trading system that:

- **Dual AI Brain**: Employs V2 (traditional macro features) and V3 (XGBoost ensemble) models for signal generation
- **Real-time Execution**: Streamlit-based dashboard for live trading with auto-refresh during market hours
- **Risk Management**: Built-in position sizing, stop-loss automation, and portfolio veto mechanisms
- **Cloud-Based**: Google Sheets integration for portfolio tracking and trade journaling
- **Self-Learning**: Ghost portfolio system learns from past trades to improve future predictions
- **Vision AI**: Advanced chart pattern recognition for trade validation
- **Performance Analytics**: Multi-dimensional trade analysis and strategy optimization

**Target Market**: Indian equity markets (NSE NIFTY 500)  
**Operating Hours**: 9:15 AM - 3:30 PM IST (Monday-Friday)  
**Risk Profile**: Swing trading (multi-day to multi-week holds)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Web Interface                   │
│              (swing_app.py - Elite Quant Terminal)            │
└──────────┬──────────────────────────────────────────────────┘
           │
     ┌─────┼─────────────────────────┬──────────────────┐
     │     │                         │                  │
┌────▼──┐┌─────────────────┐ ┌─────────────────┐ ┌────▼──────┐
│ AI    ││ Technical       │ │  Cloud Database │ │  Vision   │
│ Core  ││ Indicators      │ │  (Google Sheets)│ │  Analyzer │
│ (V2/3)││ (indicators.py) │ │ (database.py)   │ │           │
└────┬──┘└────────┬────────┘ └────────┬────────┘ └────┬──────┘
     │            │                   │               │
     └────────────┼───────────────────┼───────────────┘
                  │                   │
          ┌───────▼──────────────┬────▼─────────────┐
          │ Analysis Engine      │ Agent Interceptor│
          │ (analysis.py)        │ (agent_        │
          │ - Win Rate           │  interceptor.py)│
          │ - Strategy Showdown   │ - Trade Logging │
          │ - Risk Metrics        │ - Performance   │
          └──────────────────────┴──────────────────┘
                       │
          ┌────────────▼────────────────┐
          │  XGBoost Training Pipeline  │
          │  (v3_pipeline.py)           │
          │  - Feature Engineering      │
          │  - Label Generation         │
          │  - Model Retraining         │
          └─────────────────────────────┘
```

---

## 🧩 Core Components

### 1. **swing_app.py** - Main Application

The heart of the system. A Streamlit-based interactive dashboard.

**Key Features:**

- Dual strategy modes: **🛡️ Swing (Sentinel)** and **🎯 Scalp (Sniper)**
- Real-time market status display (open/closed)
- Control panel for:
  - AI auto-buying toggle
  - Auto-sell-off at stop-loss
  - Risk per trade (1-8%)
- Session state management for portfolios, journals, and blacklists
- Live notification log with recent trading activity
- Auto-refresh during market hours (5-minute intervals)

**Session State Tracking:**

- `portfolio` - Holdings and positions
- `journal` - Executed trades with P&L
- `blacklist` - Stocks to avoid trading
- `vetoed_today` - Trades rejected by AI today
- `shadow_logged_today` - Shadow trades logged for training
- `vision_logged_today` - Vision-validated trades

---

### 2. **ai_core.py** - Dual ML Models

#### **V2 Model (Traditional Macro Features)**

- **Type**: Scikit-Learn classifier
- **File**: `model_v2_macro.pkl`
- **Expected Features**:
  ```
  RVol, RSI, SMA200_Dist, SMA20_Dist, Wick_Reject,
  Trap_Score, Momentum_Velocity, VIX, Nifty_Trend
  ```
- **Function**: `ask_ai_gatekeeper()`
- **Default Threshold**: 70% confidence
- **Output**: Binary approval (Win probability ≥ 0.70)

#### **V3 Model (XGBoost Challenger)**

- **Type**: XGBoost Booster (native format)
- **File**: `v3_xgboost_brain.json`
- **Expected Features**:
  ```
  VIX, Nifty_Trend, RVol, RSI, SMA200_Dist,
  SMA20_Dist, Wick_Reject, Nifty_5D, Trap_Score, Momentum_Velocity
  ```
- **Function**: `ask_v3_challenger()`
- **Default Threshold**: 50% confidence
- **Output**: Binary approval with probability score

**Model Loading:**

```python
ai_model = load_ai_brain()      # V2 (joblib)
v3_model = load_v3_brain()      # V3 (XGBoost native)
```

**Inference:**

```python
# V2 Gatekeeper
is_approved_v2, confidence_v2 = ask_ai_gatekeeper(
    ai_model, stock_data, macro_data, threshold=0.70
)

# V3 Challenger
is_approved_v3, confidence_v3 = ask_v3_challenger(
    v3_model, stock_data, macro_data, threshold=0.50
)
```

---

### 3. **indicators.py** - Technical Analysis

#### **RSI (Relative Strength Index)**

```python
calculate_rsi(series, period=14)
```

- Uses Wilder's Exponential Smoothing (matching TradingView)
- Calculates gain/loss momentum
- **Output**: RSI values (0-100)

#### **Bollinger Band Width**

```python
calculate_bollinger_width(series, period=20)
```

- Optimized formula: `(4 × STD) / SMA`
- Measures volatility contraction
- **Output**: BB Width percentage

---

### 4. **v3_pipeline.py** - ML Training Pipeline

Builds the V3 XGBoost dataset from real trading history.

**Three-Phase Process:**

1. **Phase 1: Answer Key Assembly**
   - Loads ghost portfolio (resolved trades)
   - Loads live journal (executed trades)
   - Creates binary labels: Win (1) / Loss (0)
   - Merges into master truth labels

2. **Phase 2: Feature Merge**
   - Loads shadow log CSV (`nifty500_shadow_log.csv`)
   - Inner join with master labels on [Date, Symbol]
   - Drops duplicates (same stock, same day)
   - Creates feature-label pairs

3. **Phase 3: Export**
   - Saves gold-standard dataset: `v3_gold_standard_dataset.csv`
   - Ready for XGBoost training

**Data Flow:**

```
Ghost Portfolio CSV        Live Journal (Cloud)
        │                         │
        └─────────────┬───────────┘
                      │
            (Master Labels: Win/Loss)
                      │
          ┌───────────┴───────────┐
          │                       │
    Shadow Log CSV         Inner Join
   (Technical Features)           │
          │                       │
          └───────────┬───────────┘
                      │
            V3 Gold Standard Dataset
```

**Usage:**

```bash
python v3_pipeline.py
# Outputs: v3_gold_standard_dataset.csv
```

---

### 5. **analysis.py** - Advanced Trade Analytics

Provides Level 2 analytics on trading performance.

**Metrics Calculated:**

- **Win Rate**: % of profitable trades
- **Average Winner**: Mean profit on winning trades
- **Average Loser**: Mean loss on losing trades
- **Reward-to-Risk Ratio**: Risk-adjusted return metric
- **Strategy Showdown**: Per-strategy performance breakdown
- **Time-of-Day Optimization**: Hourly performance analysis

**UI Components:**

- Timeframe filter: All Time / Last 7 Days / Last 30 Days
- Timezone handling (IST)
- Closed trades filter (only trades with exit dates)
- Data cleanup (PnL parsing, date conversion)

**Usage:**

```python
from analysis import run_advanced_audit
run_advanced_audit(journal_dataframe)
```

---

### 6. **database.py** - Cloud Integration (Google Sheets)

Manages all persistence with Google Sheets (via OAuth2).

**Key Functions:**

- `init_google_sheet()` - Initialize connection
- `fetch_sheet_data(sheet_name)` - Retrieve data
- `save_portfolio_cloud()` - Save holdings
- `log_trade_journal()` - Record executed trades
- `log_ai_veto()` - Log rejected signals
- `log_signal_cloud()` - Track all signals
- `load_signals_from_cloud()` - Retrieve historical signals
- `sync_ghost_labels_to_cloud()` - Sync training labels

**Sheet Structure:**

- `Portfolio` - Current holdings
- `Journal` - Trade execution log with Entry/Exit/PnL
- `Signals` - All generated signals (approved/rejected)
- `Ghost Portfolio` - Resolved trades for model training
- `Agentic Log` - Shadow trades and their outcomes

---

### 7. **agent_interceptor.py** - Trade Logging & Evaluation

Captures and evaluates all trading activity.

**Key Functions:**

- `evaluate_and_log_shadow_trade()` - Log shadow (paper) trades
- `auto_grade_shadow_log()` - Score past shadow trades
- `fetch_todays_shadow_log()` - Retrieve today's trades

**Purpose:**

- Creates paper trading log for backtesting
- Generates training data for model retraining
- Tracks AI decision accuracy
- Enables ghost portfolio labeling

---

### 8. **vision_analyzer.py** - Chart Pattern Recognition

Advanced vision-based trade validation.

**Function:**

```python
evaluate_and_log_vision_trade()
```

**Purpose:**

- Analyzes chart patterns (candlesticks, support/resistance)
- Validates signals with visual confirmation
- Logs vision-approved trades separately
- Syncs with main trading logic

---

### 9. **ghost_dashboard.py** - Portfolio Simulation

Simulates portfolio performance against actual trades.

**Function:**

```python
render_ghost_portfolio()
```

**Purpose:**

- Shows hypothetical performance without real capital
- Tests strategy effectiveness
- Tracks ghost P&L vs actual P&L
- Identifies missed opportunities

---

### 10. **background_scanner.py** - Market Scanning

Continuous background monitoring of NIFTY 500.

**Functionality:**

- Scans all 500 stocks in real-time
- Calculates technical indicators
- Identifies setup opportunities
- Feeds signals to main system
- Runs async during market hours

---

### 11. **auto_ghost_labeler.py** - Automated Training Labels

Automatically labels resolved trades for ML training.

**Process:**

- Monitors closed trades in journal
- Determines win/loss outcome
- Creates binary labels (1 = win, 0 = loss)
- Syncs to Google Sheets
- Feeds into v3_pipeline.py

---

### 12. **backfill_metrics.py** - Historical Data Processing

Backfills missing historical metrics.

**Purpose:**

- Processes past data for incomplete records
- Calculates missing technical indicators
- Ensures data consistency
- Prepares data for analysis

---

### 13. **agent_rules.json** - System Configuration

Centralized configuration for trading rules.

```json
{
  "system_status": "active",
  "last_updated": "2026-06-12",
  "macro_boundaries": {
    "max_allowable_vix": 18.0,
    "nifty_bleed_threshold_percent": -1.0,
    "phantom_trade_exploration_enabled": true
  },
  "override_logic": {
    "reject_if_vix_above_max": true,
    "halt_live_buying_on_nifty_bleed": true,
    "min_traditional_score_for_phantom_buy": 75.0
  }
}
```

**Configuration Options:**

- `max_allowable_vix` - Maximum VIX for trading (market volatility gate)
- `nifty_bleed_threshold_percent` - Max NIFTY decline to pause trades
- `phantom_trade_exploration_enabled` - Enable paper trading mode
- `reject_if_vix_above_max` - Hard stop above VIX limit
- `halt_live_buying_on_nifty_bleed` - Stop trades on market decline
- `min_traditional_score_for_phantom_buy` - Minimum V2 score for shadow trades

---

## ✨ Features

### 🤖 Automated Trading

- **Auto-Buy**: Automatically opens positions on AI approval
- **Auto-Sell**: Closes positions at stop-loss levels
- **Position Sizing**: Risk-based position sizing (1-8% per trade)
- **Blacklist**: Avoid trading specific stocks
- **Veto System**: Double-check signals before execution

### 📊 Dual AI Models

- **V2 Gatekeeper**: Conservative traditional model (70% threshold)
- **V3 Challenger**: Aggressive XGBoost model (50% threshold)
- **Ensemble Logic**: Combined voting for robust decisions
- **Self-Learning**: Models retrain on actual trade outcomes

### 💾 Cloud Persistence

- **Google Sheets Integration**: Central repository for all data
- **Portfolio Sync**: Real-time holdings update
- **Trade Journal**: Complete audit trail of executions
- **Signal History**: All generated signals stored

### 📈 Advanced Analytics

- **Win Rate**: Success percentage
- **Reward-to-Risk**: R:R ratio optimization
- **Strategy Comparison**: Per-strategy performance
- **Time-of-Day Analysis**: Best trading hours
- **Drawdown Tracking**: Peak-to-trough losses

### 🎭 Paper Trading (Ghost Mode)

- **Shadow Log**: Paper trades for testing
- **Auto-Grading**: Automatic win/loss evaluation
- **Training Data**: Generates data for model retraining
- **Risk-Free Testing**: Test strategies without real capital

### 👁️ Vision AI

- **Chart Analysis**: Pattern recognition on price charts
- **Confirmation Logic**: Visual validation of signals
- **Wick Rejection**: Identify false breakouts
- **Trap Detection**: Spot market traps

### ⚡ Market-Aware Gating

- **VIX Monitoring**: Pause trading in high volatility (VIX > 18)
- **Market Bleed Protection**: Stop trades on NIFTY decline
- **Phantom Mode**: Automated paper trading exploration
- **Risk Thresholds**: Configurable safety limits

---

## 📦 Installation

### Prerequisites

- Python 3.8+
- Google Cloud credentials (for Google Sheets API)
- NSE/BSE market data access (via yfinance)

### Setup Steps

1. **Clone Repository**

   ```bash
   git clone <repository-url>
   cd my-swing-terminal
   ```

2. **Create Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Google Sheets Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project
   - Enable Google Sheets API
   - Create a Service Account key (JSON)
   - Place JSON in `.streamlit/secrets.toml`:

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "..."
   private_key = "..."
   client_email = "..."
   client_id = "..."
   auth_uri = "..."
   token_uri = "..."
   auth_provider_x509_cert_url = "..."
   client_x509_cert_url = "..."
   sheet_id = "your-sheet-id"
   ```

5. **Create Google Sheet**
   - Create tabs: `Portfolio`, `Journal`, `Signals`, `Ghost Portfolio`, `Agentic Log`
   - Share with service account email
   - Copy sheet ID to `secrets.toml`

6. **Run Application**
   ```bash
   streamlit run swing_app.py
   ```

---

## ⚙️ Configuration

### agent_rules.json

Edit `agent_rules.json` to customize trading rules:

```json
{
  "system_status": "active",
  "macro_boundaries": {
    "max_allowable_vix": 18.0, // Stop trading above this VIX
    "nifty_bleed_threshold_percent": -1.0, // Stop if NIFTY down 1%
    "phantom_trade_exploration_enabled": true // Enable paper trading
  },
  "override_logic": {
    "reject_if_vix_above_max": true, // Hard VIX gate
    "halt_live_buying_on_nifty_bleed": true, // Market decline stop
    "min_traditional_score_for_phantom_buy": 75.0 // Min V2 score
  }
}
```

### Model Thresholds

Adjust confidence thresholds in `ai_core.py`:

- **V2 (Gatekeeper)**: Default 70% (line ~65)
- **V3 (Challenger)**: Default 50% (line ~75)

### Risk Management

In `swing_app.py` sidebar (line ~60):

```python
risk_per_trade = st.slider("Swing Risk (%)", 1.0, 8.0, 3.0)
```

---

## 🚀 Usage

### Starting a Trading Session

1. **Launch App**

   ```bash
   streamlit run swing_app.py
   ```

2. **Check System Status**
   - Sidebar shows market open/closed
   - Cloud connection status
   - Notifications log

3. **Enable Auto-Trading**
   - Toggle "Enable Auto-Buying" in sidebar
   - Toggle "Enable Auto-Sell-Off" for automatic stop-loss
   - Set risk per trade (1-8%)

4. **Monitor Dashboard**
   - View real-time portfolio holdings
   - Check trade journal
   - Monitor notification log
   - Review generated signals

5. **Access Analytics**
   - Click "Level 2 Analytics" tab
   - Select timeframe (All Time, 7D, 30D)
   - View performance metrics
   - Analyze strategy breakdown

### Training V3 Model

1. **Prepare Data**
   - Ensure at least 100 resolved trades in journal
   - Export "cleaned training data" from Tab 3

2. **Build Dataset**

   ```bash
   python v3_pipeline.py
   ```

   - Outputs: `v3_gold_standard_dataset.csv`

3. **Train XGBoost**

   ```bash
   # Use your ML pipeline to train on the gold standard dataset
   # Model should be saved as v3_xgboost_brain.json
   ```

4. **Reload App**
   - Clear Streamlit cache
   - Restart `swing_app.py`
   - New model loads automatically

### Paper Trading (Ghost Mode)

1. **Enable Phantom Mode**
   - Set `phantom_trade_exploration_enabled: true` in `agent_rules.json`

2. **Trade Normally**
   - All trades logged as "shadow" (paper)
   - No real capital at risk

3. **Grade Performance**
   - System auto-grades at next day's open
   - Trades marked as Win/Loss

4. **Generate Training Data**
   - Ghost trades automatically feed into `v3_pipeline.py`
   - Improves model over time

---

## 🧠 ML Models

### V2 Model (model_v2_macro.pkl)

**Architecture**: Scikit-Learn Classifier (Random Forest/XGBoost)

**Input Features** (9 total):

- `RVol` - Realized volatility
- `RSI` - Relative strength index
- `SMA200_Dist` - Distance from 200-day SMA
- `SMA20_Dist` - Distance from 20-day SMA
- `Wick_Reject` - Wick rejection pattern strength
- `Trap_Score` - Bull/bear trap probability
- `Momentum_Velocity` - Price momentum
- `VIX` - Market volatility index
- `Nifty_Trend` - NIFTY 50 trend direction

**Output**: Win probability (0-1) → Binary approval if ≥ 0.70

**Use Case**: Conservative filter, high precision

---

### V3 Model (v3_xgboost_brain.json)

**Architecture**: XGBoost Booster (10 trees, native JSON format)

**Input Features** (10 total):
All V2 features PLUS:

- `Nifty_5D` - 5-day NIFTY performance

**Output**: Win probability (0-1) → Binary approval if ≥ 0.50

**Use Case**: Aggressive challenger, higher recall

**Training Pipeline**:

```
Ghost Portfolio (Resolved Trades)
        +
Live Journal (Executed Trades)
        ↓
Master Labels (Win/Loss)
        +
Shadow Log (Technical Features)
        ↓
v3_gold_standard_dataset.csv
        ↓
XGBoost Trainer
        ↓
v3_xgboost_brain.json
```

---

## 💹 Trading Strategy

### Signal Generation

```
Market Data (Stock Price, Indicators)
        ↓
├─ Calculate Technical Indicators (RSI, BB, SMA)
├─ Fetch Macro Data (VIX, NIFTY Trend)
└─ Generate Features (RVol, Trap_Score, etc.)
        ↓
┌─────────────────┬──────────────────┐
│                 │                  │
V2 Gatekeeper  V3 Challenger    VIX Gate Check
(70% threshold)  (50% threshold)  (Max 18)
│                 │                  │
└─────────────────┼──────────────────┘
                  ↓
         ✅ Approval? YES/NO
                  ↓
         ✅ Execute Trade
         (if Auto-Buy enabled)
```

### Entry Logic

1. **Technical Setup**: Identify reversal/trend continuation
2. **Indicator Confirmation**: RSI + Bollinger Bands alignment
3. **AI Approval**: Both V2 and V3 agree
4. **Macro Gate**: VIX < 18 and NIFTY trend acceptable
5. **Position Size**: Risk × Account = Position Size
6. **Execute**: Place market order (via broker API)

### Exit Logic

1. **Profit Target**: Hit predetermined R:R level
2. **Stop Loss**: Breach of support/recent swing low
3. **Time Exit**: Hold duration exceeded
4. **System Halt**: VIX spike or market bleed
5. **Record**: Log to journal with P&L

### Risk Management

- **Max Risk per Trade**: 1-8% (configurable)
- **Position Sizing**: Fixed R model
- **Stop Loss**: Technical support or ATR-based
- **Take Profit**: 1:2 R:R minimum
- **Portfolio Stop**: Circuit breaker on daily loss
- **Blacklist**: Avoid stocks with poor performance

---

## 🗄️ Database & Cloud Integration

### Google Sheets Architecture

#### Portfolio Sheet

| Symbol | Quantity | Entry Price | Current Price | Stop Loss | Target | Entry Date |
| ------ | -------- | ----------- | ------------- | --------- | ------ | ---------- |
| INFY   | 10       | 1800        | 1850          | 1780      | 1950   | 2026-08-13 |

#### Journal Sheet

| Date       | Symbol | Entry Price | Exit Price | Quantity | PnL  | Strategy | Entry Time | Exit Time | Target_Label |
| ---------- | ------ | ----------- | ---------- | -------- | ---- | -------- | ---------- | --------- | ------------ |
| 2026-08-13 | INFY   | 1800        | 1850       | 10       | ₹500 | Sentinel | 10:30      | 14:45     | 1            |

#### Signals Sheet

| Date       | Time  | Symbol | Signal Type | Price | AI Confidence | Status   | V2 Score | V3 Score |
| ---------- | ----- | ------ | ----------- | ----- | ------------- | -------- | -------- | -------- |
| 2026-08-13 | 10:15 | INFY   | BUY         | 1800  | 75%           | APPROVED | 72       | 68       |

#### Ghost Portfolio Sheet

| Date       | Symbol | Entry Price | Exit Price | Target_Label | V3_Truth_Label | Notes        |
| ---------- | ------ | ----------- | ---------- | ------------ | -------------- | ------------ |
| 2026-08-10 | TCS    | 3500        | 3650       | 1            | 1 (Winner)     | Correct call |

#### Agentic Log Sheet

| Date       | Symbol | Shadow_Price | Shadow_Exit | Actual_Result | Grade |
| ---------- | ------ | ------------ | ----------- | ------------- | ----- |
| 2026-08-13 | INFY   | 1800         | 1850        | Win           | A+    |

### Data Flow

```
Streamlit App (swing_app.py)
        ↓
Google Sheets API (database.py)
        ├─ Read: Portfolio, Journal, Signals
        ├─ Write: New trades, vetos, signals
        └─ Sync: Ghost labels, grades
        ↓
Training Pipeline (v3_pipeline.py)
        ├─ Read: Ghost Portfolio + Journal
        ├─ Merge: With Shadow Log
        └─ Output: v3_gold_standard_dataset.csv
        ↓
XGBoost Training
        └─ Save: v3_xgboost_brain.json
```

---

## 📊 Performance Analytics

### Metrics Dashboard

#### Business Baseline

- **Win Rate**: (Winning Trades / Total Trades) × 100
- **Avg Winner**: Mean P&L of profitable trades
- **Avg Loser**: Mean P&L of losing trades
- **Reward-to-Risk**: Avg Winner / |Avg Loser|

#### Strategy Showdown

Per-strategy analysis:

- Total Trades
- Net Profit
- Average P&L

#### Time-of-Day Analysis

Hourly breakdown:

- Trades per hour
- Win rate by hour
- Best performing hours

#### Timeframe Filters

- **All Time**: Entire trading history
- **Last 7 Days**: Recent performance
- **Last 30 Days**: Monthly trends

### Key Formulas

**Win Rate**:

```
Win Rate = (Count of Profitable Trades) / (Total Closed Trades) × 100
```

**Profit Factor**:

```
Profit Factor = Total Wins / |Total Losses|
```

**Sharpe Ratio** (approximated):

```
Sharpe = (Average Trade P&L) / (Std Dev of P&L)
```

**Drawdown**:

```
Drawdown = (Peak Equity - Trough Equity) / Peak Equity
```

---

## 🔧 Development

### Project Structure

```
my-swing-terminal/
├── swing_app.py                 # Main Streamlit app
├── ai_core.py                   # V2 & V3 model loading/inference
├── indicators.py                # Technical indicators (RSI, BB)
├── analysis.py                  # Trade analytics UI
├── v3_pipeline.py               # ML dataset building
├── database.py                  # Google Sheets integration
├── agent_interceptor.py         # Trade logging & grading
├── vision_analyzer.py           # Chart pattern recognition
├── ghost_dashboard.py           # Portfolio simulation
├── background_scanner.py        # Async market scanning
├── auto_ghost_labeler.py        # Automatic trade labeling
├── backfill_metrics.py          # Historical data processing
├── agent_rules.json             # System configuration
├── requirements.txt             # Python dependencies
├── model_v2_macro.pkl           # V2 trained model
├── v3_xgboost_brain.json        # V3 trained model
├── nifty500_shadow_log.csv      # Shadow trading log
├── model_v2_macro.pkl           # V2 model backup
└── README.md                    # This file
```

### Adding New Features

#### 1. New Technical Indicator

Add to `indicators.py`:

```python
def calculate_new_indicator(series, period=14):
    # Your calculation
    return indicator_values
```

#### 2. New AI Model

Save model as `<name>.json` or `.pkl` and add to `ai_core.py`:

```python
@st.cache_resource
def load_new_model():
    model = joblib.load('new_model.pkl')
    return model

def ask_new_model(model, stock_data, macro_data):
    # Your inference logic
    return decision, confidence
```

#### 3. New Analytics Metric

Add to `analysis.py` in `run_advanced_audit()`:

```python
st.markdown("#### 📊 New Metric")
new_metric = df['Column'].apply(your_function)
st.metric("New Metric", f"{new_metric:.2f}")
```

### Testing

Run unit tests:

```bash
pytest tests/
```

Test pipeline:

```bash
python -m pytest v3_pipeline.py::test_build_dataset
```

### Debugging

Enable debug mode:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check Streamlit logs:

```bash
streamlit run swing_app.py --logger.level=debug
```

---

## 🚨 Troubleshooting

### Model Loading Failed

**Issue**: V2/V3 brain won't load
**Solution**:

1. Check file exists: `model_v2_macro.pkl` and `v3_xgboost_brain.json`
2. Verify file paths in `ai_core.py` (line 15, 25)
3. Clear Streamlit cache: `streamlit cache clear`

### Google Sheets Connection Error

**Issue**: Can't connect to Google Sheets
**Solution**:

1. Verify `.streamlit/secrets.toml` has all required fields
2. Check service account email is added as editor to sheet
3. Verify `sheet_id` is correct (from URL)
4. Test: `python -c "from database import init_google_sheet; init_google_sheet()"`

### No Market Data

**Issue**: yfinance can't fetch stock data
**Solution**:

1. Check internet connection
2. Verify ticker symbols are valid (e.g., "INFY.NS" for NSE)
3. Check market hours (9:15 - 15:30 IST, Mon-Fri)
4. yfinance may have rate limits; add delays between requests

### Model Training Issues

**Issue**: `v3_pipeline.py` fails
**Solution**:

1. Ensure at least 50 labeled trades in journal
2. Check shadow log exists: `nifty500_shadow_log.csv`
3. Verify date formats match (YYYY-MM-DD)
4. Drop duplicate rows: `df.drop_duplicates(['Date', 'Symbol'])`

### Auto-Refresh Not Working

**Issue**: Dashboard doesn't refresh during market hours
**Solution**:

1. Check `is_market_active` logic (line 20)
2. Verify current time is between 9:15 - 15:30 IST
3. Check day is not weekend
4. Restart app: `streamlit run swing_app.py`

---

## 📝 License

[Specify your license here]

---

## 👥 Contributing

Contributions welcome! Please:

1. Fork repository
2. Create feature branch (`git checkout -b feature/your-feature`)
3. Commit changes (`git commit -am 'Add feature'`)
4. Push to branch (`git push origin feature/your-feature`)
5. Create Pull Request

---

## 📧 Support

For issues, questions, or suggestions:

- Open an issue on GitHub
- Contact the development team
- Check documentation and examples

---

## 🎓 Learning Resources

- **Technical Analysis**: [TradingView School](https://www.tradingview.com/school/)
- **XGBoost**: [XGBoost Documentation](https://xgboost.readthedocs.io/)
- **Streamlit**: [Streamlit Docs](https://docs.streamlit.io/)
- **NIFTY 500**: [NSE NIFTY 500 Index](https://www.nseindia.com/)
- **yfinance**: [yfinance GitHub](https://github.com/ranaroussi/yfinance)

---

**Last Updated**: 2026-08-13  
**Version**: 3.0 (Dual AI, V3 XGBoost, Cloud-Integrated)  
**Status**: Active Development

---

_Built with ❤️ for quantitative swing traders_
