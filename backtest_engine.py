# backtest_engine.py
import pandas as pd
from backtesting import Backtest, Strategy
from data_processing import get_or_update_data   # reuse your own loader
from config import BUY_SIGNAL, SELL_SIGNAL, COEF_BOLLINGER, RSI_OVERSOLD, COEF_RSI,COEF_MACD,COEF_ADX_SMA,COEF_STOCH,COEF_VOLUME,RSI_OVERBOUGHT,STOCH_OVERBOUGHT,STOCH_OVERSOLD,ADX_TREND_THRESHOLD,VOLUME_SMA_MULTIPLIER,BUY_SELL_THRESHOLD,OBSERVE_SIGNAL,HOLD_SIGNAL


class MyStrategy(Strategy):
    def init(self):
        pass
    def next(self):
        # self.data.rec is the column we will inject later
        if self.data.rec[-1] == BUY_SIGNAL and not self.position:
            self.buy()
        elif self.data.rec[-1] == SELL_SIGNAL and self.position:
            self.position.close()

def run_backtest(ticker: str, start: str, end: str, interval: str, cfg_hash: str = "",config=None):
    """
    start/end: 'YYYY-MM-DD'
    returns dict with keys:
        profit_pct, trades, money_spent, money_retrieved,
        shares_left, open_positions, closed_trades_df
    """
    if config is None:
        from config_editor import get_dict
        config = get_dict()
    # 1. Load daily data (longer horizon)
    rec, analyst, df, _, _, _, _ = get_or_update_data(
        ticker, period="max", interval=interval
    )
    if df is None or df.empty:
        return None  # Return None if data is not found

    # 2. Compute your indicator columns
    df = df.copy()
    df = df.loc[start:end]
    df['prev_MACD']   = df['MACD'].shift(1)
    df['prev_Signal'] = df['Signal'].shift(1)
    df['prev_Close']  = df['Close'].shift(1)

    # 3. Compute the *same* recommendation column you use live
    df["rec"] = df.apply(lambda row: _compute_signal_row(row, config), axis=1)

    # 4. Run backtest
    if df.empty:
        return None  # Return None if the dataframe is empty after applying the date filter

    bt = Backtest(df, MyStrategy, cash=100_000, commission=0.000)
    stats = bt.run()

    # 5. Assemble results
    closed_trades_df = stats["_trades"]            # pandas DataFrame
    trades_df = closed_trades_df                   # convenient alias

    # --- Safe extraction of scalar metrics ---
    profit_pct   = float(stats.get("Return [%]", 0))
    trades       = int(stats.get("# Trades", 0))

    # Money spent / retrieved
    if trades_df.empty:
        money_spent = money_retrieved = 0.0
    else:
        money_spent  = float((trades_df["Size"].abs() * trades_df["EntryPrice"]).sum())
        money_retrieved = float((trades_df["Size"] * trades_df["ExitPrice"]).sum())

    # Shares still open (backtesting < 0.3.0 vs ≥ 0.3.0)
    shares_left = float(stats.get("Position", stats.get("# Shares", 0)))
    # ---  convert the DataFrame to serialisable dict ---
    trades_dict = trades_df.to_dict("records")   # list of dicts

    return dict(
        profit_pct    = round(profit_pct, 2),
        trades        = trades,
        money_spent   = round(money_spent, 2),
        money_retrieved= round(money_retrieved, 2),
        shares_left   = shares_left,
        closed_trades = trades_dict   # <-- plain list
    )

def _compute_signal_row(row: pd.Series, config: dict) -> str:
    """
    Returns BUY / SELL / OBSERVE / HOLD based on the exact same rules
    used by get_or_update_data in data_processing.py
    """
    buy_score  = 0.0
    sell_score = 0.0

    # Use config values, fallback to global if missing
    COEF_BOLLINGER = config.get("COEF_BOLLINGER", 0.8)
    COEF_RSI = config.get("COEF_RSI", 2.4)
    COEF_MACD = config.get("COEF_MACD", 1.55)
    COEF_STOCH = config.get("COEF_STOCH", 2)
    COEF_ADX_SMA = config.get("COEF_ADX_SMA", 0.75)
    COEF_VOLUME = config.get("COEF_VOLUME", 0.8)
    RSI_OVERSOLD = config.get("RSI_OVERSOLD", 30)
    RSI_OVERBOUGHT = config.get("RSI_OVERBOUGHT", 70)
    STOCH_OVERSOLD = config.get("STOCH_OVERSOLD", 20)
    STOCH_OVERBOUGHT = config.get("STOCH_OVERBOUGHT", 80)
    ADX_TREND_THRESHOLD = config.get("ADX_TREND_THRESHOLD", 25)
    VOLUME_SMA_MULTIPLIER = config.get("VOLUME_SMA_MULTIPLIER", 1.5)
    BUY_SELL_THRESHOLD = config.get("BUY_SELL_THRESHOLD", 1.4)
    BUY_SIGNAL = config.get("BUY_SIGNAL", "📈 Comprar")
    SELL_SIGNAL = config.get("SELL_SIGNAL", "📉 Vender")
    OBSERVE_SIGNAL = config.get("OBSERVE_SIGNAL", "👀 Observar")
    HOLD_SIGNAL = config.get("HOLD_SIGNAL", "⏸️ Mantener")

    # 1. Bollinger Bands
    if row['Close'] < row['Lower']:
        buy_score += COEF_BOLLINGER
    if row['Close'] > row['Upper']:
        sell_score += COEF_BOLLINGER

    # 2. RSI
    if row['RSI'] < RSI_OVERSOLD:
        buy_score += COEF_RSI
    elif row['RSI'] > RSI_OVERBOUGHT:
        sell_score += COEF_RSI

    # 3. MACD crossover (require 2 rows)
    #    (row is already the last row, so we look at the previous index)
    #    We’ll skip if we don’t have enough history
    if 'prev_MACD' in row and 'prev_Signal' in row:
        if row['MACD'] > row['Signal'] and row['prev_MACD'] <= row['prev_Signal']:
            buy_score += COEF_MACD
        elif row['MACD'] < row['Signal'] and row['prev_MACD'] >= row['prev_Signal']:
            sell_score += COEF_MACD

    # 4. Stochastic
    if row['Stoch_K'] < STOCH_OVERSOLD and row['Stoch_D'] < STOCH_OVERSOLD:
        buy_score += COEF_STOCH
    elif row['Stoch_K'] > STOCH_OVERBOUGHT and row['Stoch_D'] > STOCH_OVERBOUGHT:
        sell_score += COEF_STOCH

    # 5. ADX + SMA20 trend
    if row['ADX'] > ADX_TREND_THRESHOLD:
        if row['Close'] > row['SMA20']:
            buy_score += COEF_ADX_SMA
        else:
            sell_score += COEF_ADX_SMA

    # 6. Volume spike
    if row['Volume'] > (VOLUME_SMA_MULTIPLIER * row['Volume_SMA']):
        if row['Close'] > row.get('prev_Close', row['Close']):
            buy_score += COEF_VOLUME
        elif row['Close'] < row.get('prev_Close', row['Close']):
            sell_score += COEF_VOLUME

    # --- Threshold logic ---
    if buy_score > sell_score + BUY_SELL_THRESHOLD:
        return BUY_SIGNAL
    elif sell_score > buy_score + BUY_SELL_THRESHOLD:
        return SELL_SIGNAL
    elif buy_score > 0 or sell_score > 0:
        return OBSERVE_SIGNAL
    else:
        return HOLD_SIGNAL