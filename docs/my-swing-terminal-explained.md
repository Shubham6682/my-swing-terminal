# my-swing-terminal — Codebase Explained (Plain English)

## What is this project?

This is an **automated swing-trading system for Indian stocks (NSE)**, built as a
Streamlit web app. It watches ~50-80 stocks all day, looks for technical
breakout patterns, asks two different AI models whether the setup is trustworthy,
and — if everything agrees — can automatically "buy" the stock in a tracked
paper/real portfolio, manage its stop-loss, and sell it later.

On top of the live trading, it runs a **second, invisible experiment**: every
time the AI *rejects* a setup, it quietly keeps tracking that stock anyway, to
see what would have happened. This creates a growing dataset of "the AI was
right" / "the AI was wrong" examples, which is later used to train a smarter
version of the AI. This self-grading loop is the most interesting part of the
whole system.

Everything is stored in a **Google Sheet** acting as the database (no SQL
server — just `gspread` writing rows to tabs like `Portfolio`, `Journal`,
`AI_Veto_Log`, etc).

---

## The Cast of Files

| File | Role |
|---|---|
| `swing_app.py` | The main Streamlit app — the UI, the scanner loop, the "brain" of the whole system |
| `indicators.py` | Small math helpers: RSI and Bollinger Band Width |
| `ai_core.py` | Loads the two AI models and asks them for a verdict |
| `database.py` | All Google Sheets read/write logic |
| `agent_interceptor.py` | The "shadow trading" agent — logs a second opinion and self-grades old trades |
| `vision_analyzer.py` | A simpler "chart pattern" scoring engine, logged separately for future AI training |
| `analysis.py` | Deep performance analytics tab (win rate, MFE/MAE, time-of-day stats) |
| `ghost_dashboard.py` | Shows what happened to stocks the AI *rejected* ("Ghost Portfolio") |
| `background_scanner.py` | A standalone script (meant for GitHub Actions) that scans a wider universe of stocks and logs anomalies even when nobody has the app open |
| `auto_ghost_labeler.py` | Standalone script: grades pending "ghost" trades as Win/Loss once enough time has passed |
| `backfill_metrics.py` | Standalone script: fixes/fills in missing peak-profit and max-drawdown numbers on old records |
| `v3_pipeline.py` | Standalone script: stitches together features + outcome labels into a clean CSV to retrain the V3 AI model |
| `model_v2_macro.pkl` / `v3_xgboost_brain.json` | The two trained AI models (V2 = scikit-learn style, V3 = raw XGBoost) |
| `nifty500_shadow_log.csv` | A big historical CSV of logged technical features, used for training |
| `agent_rules.json` | Simple config: VIX limits, "market bleeding" thresholds, etc. |

---

## 1. The Main App (`swing_app.py`)

This is a single Streamlit page with **3 tabs**: Scanner, Portfolio, and
Performance Audit. Here's the flow, start to finish.

### Startup
- Detects if the Indian market is currently open (9:15 AM–3:30 PM IST, weekdays).
- If open, auto-refreshes the whole page every 5 minutes.
- Loads both AI models into memory (`load_ai_brain()`, `load_v3_brain()`).
- Keeps track of state across refreshes using Streamlit's `session_state`
  (portfolio, trade journal, blacklist, notifications, etc.), and resets the
  daily counters when a new trading day begins.

### Sidebar — Control Panel
- Choose strategy mode: **Swing (Sentinel)** or **Scalp (Sniper)** — two
  different technical setups (explained below).
- Toggle "Auto-Buying" and "Auto-Sell-Off" (the bot only trades automatically
  if these are on **and** the Google Sheet database is connected).
- A risk slider (1–8%) that sets how far below entry the stop-loss sits.
- A notification log of recent bot actions.
- Manual override inputs, in case Yahoo Finance data is stale or broken —
  you can type in Nifty's move by hand to keep the system running.

### Market Health Check ("The Shield")
Before doing anything, the app decides: **is it safe to buy right now?**
- It pulls Nifty 50's price history and checks:
  - Is Nifty above its 20-day moving average? (bullish filter)
  - Is Nifty down more than -0.3% today? (a "bleeding market" veto)
- Only if both checks pass does `is_safe_to_buy = True`. This one flag gates
  almost every buy decision later in the app — it's the master safety switch.

### Tab 1 — Market Scanner
This is where the actual signal-hunting happens, for both:
- A **custom ticker** you type in manually (to test any NSE stock on demand)
- The full watchlist of **Nifty 50 stocks** (looped automatically)

For each stock, it computes a batch of technical numbers:

| Metric | What it means |
|---|---|
| RVol | Today's volume vs. its 20-day average (is trading unusually busy?) |
| RSI | Classic momentum indicator (0–100, overbought/oversold) |
| SMA200 / SMA20 Distance | How far the price is from its 200-day and 20-day averages |
| Wick Rejection | How much of today's candle was "rejected" from the high (a sign of selling pressure) |
| Trap Score | A custom formula combining volume surge + wick rejection, penalized if price is far from its 20-day average — meant to flag "fake breakouts" |
| Momentum Velocity | RSI × Relative Volume — a combined momentum/activity score |
| VIX / Nifty Trend / Nifty 5-Day Trend | Overall market mood context |

**Phase 1 — Rule-based trigger:**
- *Swing mode*: buy if price breaks above its 5-day high **and** its 200-day
  average **and** it's outperforming Nifty over the last 60 days.
- *Scalp mode*: buy on a volume/RSI breakout, but only after first spotting a
  "squeeze" (tight Bollinger Bands = coiled spring waiting to move).

**Phase 2 — AI verdict:**
If the technical rule fires, the numbers above are fed into **both AI
models**:
- `ask_ai_gatekeeper()` → the V2 model, needs ≥70% confidence to approve
- `ask_v3_challenger()` → the V3 model, needs ≥50% confidence to approve

A trade is only auto-executed if it fires in the afternoon window
(1:30–3:30 PM) — this avoids the noisy, unreliable signals right at market
open — **and** either model approves it (`v2_approved or v3_approved`). The
system tags *which* brain(s) agreed (`V2_V3_Agreement`, `V2_Only`, `V3_Only`)
so you can later see which combination performs best.

If a trade is rejected by both models, it's logged to the "AI Veto Log"
instead of being bought — this feeds the Ghost Portfolio (see below).

Two more things quietly happen on every qualifying signal, regardless of
whether it's bought:
- **Shadow Trade Logging** (`agent_interceptor.py`) — a rules-based "second
  opinion" agent independently decides approve/reject and logs its reasoning.
- **Vision Analysis** (`vision_analyzer.py`) — a simpler chart-pattern scorer
  logs its own read of the stock's trend structure.

All of these are separate, parallel opinions being recorded for future
comparison and model training — the system is essentially running multiple
experiments on itself at once.

### Tab 2 — Active Portfolio
Shows every open position with live P&L. Manages exits automatically:
- **The "3-5-3" trailing stop system**: once a trade is up 5%, the stop-loss
  trails 3% below the current price, locking in gains as the stock climbs.
- If price falls to the stop-loss and "Auto-Sell" is on, it closes the
  position automatically and logs it to the trade journal.
- You can also manually close any position with a button.
- Tracks each trade's best-ever profit (MFE) and worst-ever drawdown (MAE)
  while it's open — useful data for later analysis.
- Shows portfolio-wide stats: total capital deployed, floating P&L, today's
  P&L, and win/loss counts.

### Tab 3 — Performance Audit
- **Ghost Portfolio Tracker** — see `ghost_dashboard.py` below.
- **Deep Performance Audit** — see `analysis.py` below.
- **Threshold Optimizer** — a slider lets you simulate: "what if I only took
  trades where the AI was ≥90% confident instead of 70%?" and instantly shows
  what your historical P&L and win rate would have been at that stricter bar.

---

## 2. The AI Brains (`ai_core.py`)

Two independently-trained machine learning models judge every trade setup:

- **V2 ("Champion")** — a scikit-learn-style classifier saved with `joblib`.
  Takes 9 features (RVol, RSI, SMA distances, Wick Reject, Trap Score,
  Momentum Velocity, VIX, Nifty Trend) and outputs a win probability.
  Approval threshold: 70%.
- **V3 ("Challenger")** — a native XGBoost model (loaded via `xgb.Booster`,
  not scikit-learn, for compatibility reasons) trained on a similar but
  slightly expanded feature set (adds `Nifty_5D`, the 5-day Nifty trend).
  Approval threshold: 50%.

Both simply predict: *"based on stocks that looked like this historically,
what fraction of them ended up winners?"* — and the app treats that
probability as a confidence score.

## 3. Technical Math (`indicators.py`)
Just two formulas:
- **RSI** using Wilder's smoothing (the same method TradingView/brokers use,
  more accurate than a simple moving average version).
- **Bollinger Band Width** — measures how "squeezed" or "expanded" a stock's
  recent price range is (narrow = coiled, about to move).

## 4. The Database Layer (`database.py`)
No traditional database — everything lives in a Google Sheet named
`Swing_Trading_DB` with tabs: `Portfolio`, `Journal`, `AI_Veto_Log`,
`Signal_Log`. This file handles:
- Authenticating to Google (tries Streamlit's secrets first, falls back to a
  local `secrets.toml` file for running scripts outside the web app).
- Reading/writing each tab, with duplicate-prevention checks (e.g., won't log
  the same veto for the same stock twice in a day).

## 5. The Shadow Agent (`agent_interceptor.py`)
This runs a second, independent decision process on every technical signal,
using simple hard rules from `agent_rules.json` (max allowed VIX = 18, "market
bleeding" = Nifty down more than -1%, etc.). Its interesting twist is
**"Phantom Trades"**: even when the market is officially "unsafe to buy," if
the stock's technical score is very strong (≥75%), it will still log an
approval as an experiment — to test whether high-conviction setups can
survive a rough macro environment. This file also contains
`auto_grade_shadow_log()`, which runs each morning and automatically stamps
"Win"/"Loss" labels on old shadow trades once 8 trading days have passed,
using the same 5% target / 3% stop rules as the live portfolio.

## 6. The Vision Analyzer (`vision_analyzer.py`)
A lighter-weight, purely chart-based scoring system, run in parallel to the
main AI models. It looks at 6 months of price history and computes:
- **Trend structure**: is the second half of the period stronger than the
  first half? ("Higher Lows" vs "Choppy/Declining")
- **Overhead resistance**: how far away is the nearest historical price
  ceiling?
- **Chaos score**: how volatile are daily returns?
These feed a simple heuristic score (starts at 50, adds points for bullish
structure, clear headroom, and low chaos). This is logged to its own sheet
tab and eventually graded the same way as the shadow log — building yet
another labeled dataset for future model versions.

## 7. Performance Analytics (`analysis.py`)
The "Deep Performance Audit" — turns your closed trade journal into real
business metrics:
- Win rate, average winner/loser, reward-to-risk ratio.
- A strategy showdown table (which brain combo — V2 only, V3 only, both — is
  actually making money).
- Time-of-day breakdown (are morning trades worse than afternoon trades?).
- **MFE/MAE enrichment**: re-downloads minute-by-minute price data for
  closed trades to see how much profit was "left on the table" between your
  actual exit and the best possible exit.
- Auto-generated recommendations in plain English (e.g., "tighten your
  trailing stop" or "avoid trading in this time window") based on the above.

## 8. The Ghost Portfolio (`ghost_dashboard.py`)
This is the system's "what if we hadn't said no?" feature. For every stock the
AI vetoed, it re-simulates a virtual trade going forward using the same
3-5-3 trailing-stop rules, and classifies the outcome as:
- 🚨 **Missed Winner** — the AI wrongly rejected a stock that would have won
- 🛡️ **Dodged Bullet** — the AI correctly rejected a stock that would have lost
- ⏳ **Still Chopping** — too early to tell

This is exactly the labeled data (`1` = should've bought, `0` = correctly
avoided) that gets exported and fed back into training the next AI model.

## 9. Background/Offline Scripts
These aren't run inside the Streamlit app — they're meant to run unattended
(e.g., via GitHub Actions on a schedule):

- **`background_scanner.py`** — scans a much bigger list (~80 stocks) once
  a day, even when nobody has the app open, and logs any stock showing
  unusual RSI/volume behavior straight to the veto log — widening the net of
  training data beyond just the Nifty 50.
- **`auto_ghost_labeler.py`** — automatically grades pending veto-log entries
  once their 8-day window has resolved, and also tracks their peak profit and
  max drawdown along the way (a more precise cousin of the grading logic in
  `agent_interceptor.py`).
- **`backfill_metrics.py`** — a one-time cleanup script to retroactively
  compute peak-profit/drawdown numbers for old records that predate that
  feature being added.
- **`v3_pipeline.py`** — the final assembly step: merges the graded Ghost
  Portfolio outcomes + your real trade journal outcomes with the historical
  feature CSV (`nifty500_shadow_log.csv`) into one clean "gold standard"
  training dataset, ready to train the next XGBoost model.

---

## How It All Connects (the feedback loop)

```
Scanner finds a technical setup
        │
        ▼
Both AI models score it  ──► Approved ──► Bought & tracked in Portfolio
        │                                        │
        ▼                                        ▼
   Rejected by both                     Auto-managed with trailing stop
        │                                        │
        ▼                                        ▼
  Logged to AI_Veto_Log              Closed & logged to Journal (Win/Loss)
        │                                        │
        ▼                                        │
Ghost Portfolio simulates                        │
"what if we'd bought anyway"                      │
        │                                        │
        ▼                                        ▼
   Labeled outcome (Win/Loss)  ──────►  v3_pipeline.py merges everything
                                                  │
                                                  ▼
                                    New training dataset → retrain V3 model
                                                  │
                                                  ▼
                                    Smarter AI gatekeeper next cycle
```

The elegant idea here: the system never throws away information just because
it decided *not* to trade. Every rejection becomes a future lesson.

---

## Setup Notes for a New User
- You'll need a `.streamlit/secrets.toml` (or Streamlit Cloud secrets) with a
  `gcp_service_account` block containing Google service-account credentials
  and a `sheet_id`, plus a Google Sheet named `Swing_Trading_DB` with tabs:
  `Portfolio`, `Journal`, `AI_Veto_Log`, `Signal_Log`, `Agentic_Shadow_Log`,
  `Vision_Shadow_Log`.
- Install dependencies from `requirements.txt` (`pip install -r requirements.txt`).
- Run the app with `streamlit run swing_app.py`.
- Without the Google Sheet connection, the app still runs — it just disables
  actual trading and shows "Offline: Trading Disabled."
