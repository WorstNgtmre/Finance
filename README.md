# 📈 Day-Trading Simulator & Strategy Optimizer

A **Dash-based desktop application** that lets you **paper-trade**, **back-test**, and **auto-optimize** technical-analysis strategies with a genetic algorithm.

---

## 🚀 Quick Start

python -m app.py

Browser opens at `http://127.0.0.1:8050`.

---

## 📂 Structure

```
app.py                 # Launch Dash server & browser
backtest_engine.py     # Back-testing core (Backtesting.py)
callbacks.py           # Dash callbacks (UI ↔ logic)
config.py              # Live config (auto-generated)
config_editor.py       # Read/Write/Reset config from UI
constants.py           # Tickers, descriptions, etc.
data_processing.py     # yfinance loader + indicators
layout.py              # HTML layout components
optimizer.py           # Genetic algorithm (DEAP)
state_management.py    # Paper-trade portfolio + JSON persistence
portfolio_data.json    # Current cash/positions/trades
optimizer_state.json   # GA history & best genome
assets\dark-theme.css         # Dark-mode overrides
```

---

## ⚙️ Features

| Feature | Purpose |
|---------|---------|
| Live Charts | Candlestick, RSI, MACD, ADX, Stochastic, Volume |
| Paper Trading | Manual buy/sell + auto-trading toggle |
| Backtesting | Pick ticker, date range, interval → PnL & trade log |
| Optimizer | GA tunes 13+ params to maximize risk-adjusted return |
| Config Editor | Real-time sliders for every coefficient |
| Persistence | Portfolio & best GA genome survive restarts |

---

## 🧪 Typical Workflow

1. **Manual Trade**  
   Enter `NVDA`, buy 10 shares, watch live P&L.

2. **Backtest**  
   **Backtest** tab → `TSLA`, `2024-01-01` → `2024-06-01`, `15 m` → **Run**.  
   Output: Net profit %, # trades, money spent/retrieved, closed-trade table.

3. **Optimize**  
   **Optimizer** tab → population 20, generations 50 → **Start**.  
   When finished, **Apply Best Config** to trade with tuned parameters.

---

## 🔧 Key Parameters (editable in Config tab)

| Param | Meaning | Default |
|-------|---------|---------|
| `COEF_RSI` | RSI signal weight | 1.16 |
| `BUY_SELL_THRESHOLD` | Score diff to trigger trade | 2.51 |
| `VOLUME_SMA_MULTIPLIER` | Volume spike filter | 1.81 |
| … | 10 more coefficients | … |

---

## 🧬 GA Details

- **Engine** DEAP  
- **Genome** 13 floats (config params)  
- **Fitness** `avg_profit – 0·loss + 0.1·trades`  
- **Per run** 3 random popular tickers, 5 m bars, 60 days  

---

## 📦 Requirements

```txt
dash==2.17.1
dash-bootstrap-components==1.6.0
yfinance==0.2.28
ta==0.10.2
backtesting==0.3.3
deap==1.4.1
pandas
plotly
```

---

## 🎨 Dark Theme

All components use CSS variables in `dark-theme.css`; tweak once, change everywhere.

---

## 📁 Persisted Files

| File | Content |
|------|---------|
| `portfolio_data.json` | Cash, open positions, closed trades |
| `optimizer_state.json` | GA progress, best genome |

Delete to reset.

---

## 🙋 FAQ

**Add an indicator?**  
Edit `data_processing.py → calculate_indicators()` and `_compute_signal_row`.

**Real money?**  
**No.** 100 % simulation.

**Intraday?**  
Yes—`1 m`, `5 m`, `15 m`, `1 h` intervals supported.

---

## 📄 License

MIT — fork, hack, enjoy!

---
Happy (paper) trading!
```
