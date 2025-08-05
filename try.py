import json
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
# import time # No longer needed for static plot

## VALORES
stock1 = "MSFT"


def get_stock_data(ticker: str):
    """Fetches general stock information."""
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.info.get('currentPrice', 'N/A')
        print(f"\nCurrent Price: {current_price}\n")
        return stock.info
    except Exception as e:
        print(f"Could not fetch data for {ticker}. Error: {e}")
        return None

def get_stock_history(ticker: str, period="5d", interval="15m"):
    """Fetches historical data for a given period and interval."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        # Print tail here as requested
        print(f"--- Datos recientes para {ticker} ---")
        print(hist.tail())
        return hist
    except Exception as e:
        print(f"Could not get data from {ticker}. Error: {e}")
        return pd.DataFrame()

# ------------------- Indicadores -------------------

def calculate_rsi(series, period=14):
    """Calculates the Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=1).mean()
    
    # Handle division by zero for rs
    rs = gain / (loss.replace(0, np.nan).fillna(1e-10)) # Add epsilon to prevent div by zero
    
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculates the Moving Average Convergence Divergence (MACD)."""
    ema_fast = series.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = series.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return macd, signal_line

def calculate_bollinger_bands(series, period=20, num_std=2):
    """Calculates Bollinger Bands."""
    sma = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, sma, lower

def calculate_stochastic(high, low, close, period=14, smoothing=3):
    """Calculates the Stochastic Oscillator (%K and %D lines)."""
    lowest_low = low.rolling(window=period, min_periods=1).min()
    highest_high = high.rolling(window=period, min_periods=1).max()
    
    # Handle division by zero for k_line
    range_hl = highest_high - lowest_low
    k_line = 100 * ((close - lowest_low) / (range_hl.replace(0, np.nan).fillna(1e-10)))
    
    d_line = k_line.rolling(window=smoothing, min_periods=1).mean()
    return k_line, d_line

def calculate_adx(high, low, close, period=14):
    """Calculates the Average Directional Index (ADX, +DI, -DI)."""
    df = pd.DataFrame({'High': high, 'Low': low, 'Close': close})
    
    # Calculate Directional Movement
    df['up_move'] = df['High'].diff()
    df['down_move'] = df['Low'].diff() * -1
    
    df['+DM'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-DM'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    # Calculate True Range (TR)
    range1 = df['High'] - df['Low']
    range2 = abs(df['High'] - df['Close'].shift(1))
    range3 = abs(df['Low'] - df['Close'].shift(1))
    
    df['TR'] = pd.concat([range1, range2, range3], axis=1).max(axis=1)
    
    # Smooth the indicators using Wilder's smoothing method
    def wilder_smoothing(series, period):
        # Use min_periods to ensure enough data for initial calculation
        return series.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

    smoothed_tr = wilder_smoothing(df['TR'], period)
    smoothed_pdm = wilder_smoothing(df['+DM'], period)
    smoothed_ndm = wilder_smoothing(df['-DM'], period) 
    
    # Add a small epsilon to smoothed_tr to avoid division by zero
    epsilon = 1e-10
    df['+DI'] = 100 * (smoothed_pdm / (smoothed_tr + epsilon))
    df['-DI'] = 100 * (smoothed_ndm / (smoothed_tr + epsilon))
    
    # Calculate DX
    # Ensure the denominator is not zero
    sum_di = df['+DI'] + df['-DI'] 
    df['DX'] = 100 * (abs(df['+DI'] - df['-DI']) / (sum_di.replace(0, np.nan).fillna(epsilon)))
    
    # Calculate ADX
    adx = wilder_smoothing(df['DX'], period)
    
    return adx, df['+DI'], df['-DI']


# ------------------- Análisis Mejorado -------------------

def analyse_stock_data(data: dict, history: pd.DataFrame):
    """Analyzes stock data with a more refined scoring system."""
    try:
        analist_recomendation = data.get("recommendationKey", "N/A")
        current_price = data.get("currentPrice", 0)
        fifty_day_average = data.get('fiftyDayAverage', 0)
        volume = data.get('volume', 0)
        average_volume_10_days = data.get('averageVolume10days', 0)

        # Coefficients for a more nuanced scoring system
        COEF_LONG_TERM = 1.5
        COEF_VOLUME = 1.0
        COEF_INTRADAY_TREND = 1.2
        COEF_RSI = 1.5
        COEF_MACD = 1.8
        COEF_BOLLINGER = 1.2
        COEF_STOCHASTIC = 1.5
        COEF_ADX = 1.8

        buy_score = 0.0
        sell_score = 0.0

        # --- Análisis Fundamental y de Volumen ---
        if current_price and fifty_day_average:
            if current_price > fifty_day_average:
                buy_score += COEF_LONG_TERM
            elif current_price < fifty_day_average:
                sell_score += COEF_LONG_TERM

        if volume and average_volume_10_days:
            if volume > 1.5 * average_volume_10_days:
                buy_score += COEF_VOLUME
            elif volume < 0.5 * average_volume_10_days:
                sell_score += COEF_VOLUME

        # Ensure history is not empty and clean NaNs before proceeding
        if history is None or history.empty:
            print("Historical data is empty, cannot perform analysis.")
            return "Error", pd.DataFrame() # Return empty DataFrame on error
        
        # Drop rows with NaN values that might arise from initial periods of indicator calculations
        # This is crucial for ensuring that .iloc[-1] and .iloc[-2] always return valid numbers.
        history_cleaned = history.dropna().copy() # Explicitly copy after dropna()

        # Check if there's enough valid data after cleaning for the longest period needed (MACD slow=26)
        if history_cleaned.empty or len(history_cleaned) < 26:
            print("Not enough valid historical data after cleaning for a complete analysis. Minimum 26 periods required.")
            return "Observar", history_cleaned # Return cleaned history even if insufficient for full analysis

        close = history_cleaned['Close']
        high = history_cleaned['High']
        low = history_cleaned['Low']
            
        # --- Análisis de Tendencia a Corto Plazo ---
        # Calculate SMA_10 directly on history_cleaned
        history_cleaned.loc[:, 'SMA_10'] = history_cleaned['Close'].rolling(window=10, min_periods=1).mean()
        last_close = close.iloc[-1]
        last_sma = history_cleaned['SMA_10'].iloc[-1]
        if last_close > last_sma:
            buy_score += COEF_INTRADAY_TREND
        elif last_close < last_sma:
            sell_score += COEF_INTRADAY_TREND

        # --- Análisis de Indicadores ---
        
        # RSI
        rsi_series = calculate_rsi(close)
        last_rsi = rsi_series.iloc[-1]
        if last_rsi < 25:
            buy_score += COEF_RSI * 1.5
        elif last_rsi < 30:
            buy_score += COEF_RSI
        elif last_rsi > 75:
            sell_score += COEF_RSI * 1.5
        elif last_rsi > 70:
            sell_score += COEF_RSI

        # MACD
        macd, signal = calculate_macd(close)
        # Ensure there are enough values for previous periods after MACD calculation
        if len(macd) >= 2:
            last_macd = macd.iloc[-1]
            last_signal = signal.iloc[-1]
            prev_macd = macd.iloc[-2]
            prev_signal = signal.iloc[-2]
            
            if last_macd > last_signal and prev_macd <= prev_signal:
                buy_score += COEF_MACD
            elif last_macd < last_signal and prev_macd >= prev_signal:
                sell_score += COEF_MACD
        else:
            print("Not enough data for MACD crossover analysis.")
        
        # Bollinger Bands
        upper, mid, lower = calculate_bollinger_bands(close)
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]

        if last_close < last_lower:
            buy_score += COEF_BOLLINGER
        elif last_close > last_upper:
            sell_score += COEF_BOLLINGER

        # Stochastic Oscillator
        k_line, d_line = calculate_stochastic(high, low, close)
        # Ensure there are enough values for previous periods after Stochastic calculation
        if len(k_line) >= 2:
            last_k = k_line.iloc[-1]
            last_d = d_line.iloc[-1]
            prev_k = k_line.iloc[-2]
            prev_d = d_line.iloc[-2]

            if last_k < 20 and last_d < 20:
                buy_score += COEF_STOCHASTIC
            elif last_k > 80 and last_d > 80:
                sell_score += COEF_STOCHASTIC
            if last_k > last_d and prev_k <= prev_d:
                buy_score += COEF_STOCHASTIC * 0.5
            elif last_k < last_d and prev_k >= prev_d:
                sell_score += COEF_STOCHASTIC * 0.5
        else:
            print("Not enough data for Stochastic crossover analysis.")
                
        # ADX
        adx, plus_di, minus_di = calculate_adx(high, low, close)
        # Ensure there are enough values for ADX
        if not adx.empty:
            last_adx = adx.iloc[-1]
            last_plus_di = plus_di.iloc[-1]
            last_minus_di = minus_di.iloc[-1]
            
            if last_adx > 25:
                if last_plus_di > last_minus_di:
                    buy_score += COEF_ADX
                elif last_minus_di > last_plus_di:
                    sell_score += COEF_ADX
        else:
            print("ADX could not be calculated due to insufficient data.")


        # --- Decisión Final ---
        final_recommendation = "Mantener"
        if buy_score > sell_score + 2:
            final_recommendation = "Comprar"
        elif sell_score > buy_score + 2:
            final_recommendation = "Vender"
        elif abs(buy_score - sell_score) < 2 and (buy_score > 0 or sell_score > 0):
             final_recommendation = "Observar"
        
        print("\n--- Resultados del Análisis Avanzado ---")
        print(f"Recomendación del analista (Yahoo Finance): {analist_recomendation}")
        print(f"Puntuación de compra: {buy_score:.2f}")
        print(f"Puntuación de venta: {sell_score:.2f}")
        print("----------------------------")
        print(f"Recomendación final: {final_recommendation}")

        return final_recommendation, history_cleaned # Return history_cleaned for plotting

    except Exception as e:
        print(f"Error al analizar los datos: {e}")
        return "Error", pd.DataFrame() # Return empty DataFrame on error

# ------------------- Función de Visualización -------------------

def plot_stock_analysis(ticker: str, history_cleaned: pd.DataFrame, final_recommendation: str):
    """
    Creates multiple plots to visualize stock price, volume, and technical indicators.
    """
    if history_cleaned.empty:
        print("No historical data to plot.")
        return

    # Set up the plot style for a cleaner look
    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams.update({
        'font.size': 10,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.titlesize': 16
    })

    # Adjusted figsize for smaller graphs and two columns
    fig, axes = plt.subplots(3, 2, figsize=(14, 12), sharex=True, # 3 rows, 2 columns, wider figure
                                                    gridspec_kw={'height_ratios': [3, 1.5, 1.5]}) # Adjusted height ratios
    fig.suptitle(f'Análisis de Acciones para {ticker}', y=0.99)

    # Flatten the axes array for easier iteration
    all_axes = axes.flatten()

    # --- Plot 1: Price, SMA, Bollinger Bands (Top-Left) ---
    ax1 = axes[0, 0]
    ax1.plot(history_cleaned.index, history_cleaned['Close'], label='Precio de Cierre', color='#1f77b4', linewidth=1.8) # Blue
    
    # Calculate SMA_10 (already done in analyse_stock_data, but recalculate for plotting clarity)
    # Use .loc to avoid SettingWithCopyWarning
    history_cleaned.loc[:, 'SMA_10'] = history_cleaned['Close'].rolling(window=10, min_periods=1).mean()
    ax1.plot(history_cleaned.index, history_cleaned['SMA_10'], label='SMA (10)', color='#ff7f0e', linestyle='--', linewidth=1.2) # Orange

    # Calculate Bollinger Bands
    upper_band, mid_band, lower_band = calculate_bollinger_bands(history_cleaned['Close'])
    ax1.plot(history_cleaned.index, upper_band, label='Banda Superior Bollinger', color='#2ca02c', linestyle=':', linewidth=1) # Green
    ax1.plot(history_cleaned.index, mid_band, label='Banda Media Bollinger', color='#9467bd', linestyle=':', linewidth=1) # Purple
    ax1.plot(history_cleaned.index, lower_band, label='Banda Inferior Bollinger', color='#d62728', linestyle=':', linewidth=1) # Red
    
    ax1.set_ylabel('Precio')
    ax1.legend(loc='upper left')
    ax1.set_title('Precio de Cierre, SMA y Bandas de Bollinger')

    # Add final recommendation marker
    last_date = history_cleaned.index[-1]
    last_close_price = history_cleaned['Close'].iloc[-1]
    
    marker_color = 'gray'
    marker_symbol = 'o'
    if final_recommendation == "Comprar":
        marker_color = 'green'
        marker_symbol = '^'  # Up arrow
    elif final_recommendation == "Vender":
        marker_color = 'red'
        marker_symbol = 'v'  # Down arrow
    elif final_recommendation == "Observar":
        marker_color = 'orange'
        marker_symbol = 's' # Square

    # Adjust text position slightly to avoid overlap with marker
    ax1.scatter(last_date, last_close_price, color=marker_color, marker=marker_symbol, s=200, 
                label=f'Recomendación: {final_recommendation}', zorder=5, edgecolor='black', linewidth=0.8)
    ax1.text(last_date + pd.Timedelta(minutes=15), last_close_price, f' {final_recommendation}', # Offset by 15 minutes
             color=marker_color, ha='left', va='center', fontsize=10, weight='bold')
    ax1.legend(loc='upper left')


    # --- Plot 2: Volume (Top-Right) ---
    ax2 = axes[0, 1]
    # Single solid blue color for volume bars and reduced width
    volume_color = '#1f77b4' # Blue color
    # Use a width that is a fraction of the interval (e.g., 10 minutes for a 15-minute interval)
    ax2.bar(history_cleaned.index, history_cleaned['Volume'], color=volume_color, alpha=1.0, label='Volumen', width=pd.Timedelta(minutes=10)) 
    ax2.set_ylabel('Volumen')
    ax2.legend(loc='upper left')
    ax2.set_title('Volumen de Negociación')

    # --- Plot 3: RSI (Middle-Left) ---
    ax3 = axes[1, 0]
    rsi_series = calculate_rsi(history_cleaned['Close'])
    ax3.plot(history_cleaned.index, rsi_series, label='RSI (14)', color='#8c564b', linewidth=1.5) # Brown
    ax3.axhline(70, color='#d62728', linestyle='--', alpha=0.7, label='Sobrecompra (70)') # Red
    ax3.axhline(30, color='#2ca02c', linestyle='--', alpha=0.7, label='Sobrevendido (30)') # Green
    ax3.set_ylabel('RSI')
    ax3.set_ylim(0, 100)
    ax3.legend(loc='upper left')
    ax3.set_title('Índice de Fuerza Relativa (RSI)')

    # --- Plot 4: MACD (Middle-Right) ---
    ax4 = axes[1, 1]
    macd, signal = calculate_macd(history_cleaned['Close'])
    macd_histogram = macd - signal
    ax4.plot(history_cleaned.index, macd, label='MACD (12,26)', color='#1f77b4', linewidth=1.5) # Blue
    ax4.plot(history_cleaned.index, signal, label='Línea de Señal (9)', color='#d62728', linestyle='--', linewidth=1) # Red
    # Use different colors for positive/negative histogram bars
    ax4.bar(history_cleaned.index, macd_histogram, label='Histograma MACD', 
            color=np.where(macd_histogram > 0, '#2ca02c', '#d62728'), alpha=0.6) # Green for positive, red for negative
    ax4.axhline(0, color='black', linestyle='-', linewidth=0.5)
    ax4.set_ylabel('MACD')
    ax4.legend(loc='upper left')
    ax4.set_title('Convergencia/Divergencia de Medias Móviles (MACD)')

    # --- Plot 5: Stochastic Oscillator (Bottom-Left) ---
    ax5 = axes[2, 0]
    k_line, d_line = calculate_stochastic(history_cleaned['High'], history_cleaned['Low'], history_cleaned['Close'])
    ax5.plot(history_cleaned.index, k_line, label='%K (14)', color='#1f77b4', linewidth=1.5) # Blue
    ax5.plot(history_cleaned.index, d_line, label='%D (3)', color='#d62728', linestyle='--', linewidth=1) # Red
    ax5.axhline(80, color='#d62728', linestyle='--', alpha=0.7, label='Sobrecompra (80)') # Red
    ax5.axhline(20, color='#2ca02c', linestyle='--', alpha=0.7, label='Sobrevendido (20)') # Green
    ax5.set_ylabel('Estocástico')
    ax5.set_ylim(0, 100)
    ax5.legend(loc='upper left')
    ax5.set_title('Oscilador Estocástico')

    # --- Plot 6: ADX (Bottom-Right) ---
    ax6 = axes[2, 1]
    adx, plus_di, minus_di = calculate_adx(history_cleaned['High'], history_cleaned['Low'], history_cleaned['Close'])
    ax6.plot(history_cleaned.index, adx, label='ADX (14)', color='#1f77b4', linewidth=1.5) # Blue
    ax6.plot(history_cleaned.index, plus_di, label='+DI (14)', color='#2ca02c', linestyle='--', linewidth=1) # Green
    ax6.plot(history_cleaned.index, minus_di, label='-DI (14)', color='#d62728', linestyle='--', linewidth=1) # Red
    ax6.axhline(25, color='gray', linestyle=':', alpha=0.7, label='Umbral de Tendencia (25)')
    ax6.set_ylabel('ADX')
    ax6.set_ylim(0, 100)
    ax6.legend(loc='upper left')
    ax6.set_title('Índice Direccional Promedio (ADX)')
    ax6.set_xlabel('Fecha')

    # Format x-axis for dates on the bottom row
    for ax in [axes[2, 0], axes[2, 1]]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    fig.autofmt_xdate()
    
    # Add black border to each subplot
    for ax in all_axes:
        for spine in ax.spines.values():
            spine.set_edgecolor('black')
            spine.set_linewidth(1.5) # Adjust linewidth as desired

    plt.tight_layout(rect=[0, 0.03, 1, 0.96]) # Adjust layout to prevent suptitle overlap
    
    # Show the plot and block execution until it's closed
    plt.show(block=True)


# ------------------- Funciones de Transacciones -------------------

def load_transactions(filename: str) -> list:
    """Loads transaction history from a JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return [] # Return empty list if file doesn't exist yet
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from {filename}. Starting with empty history.")
        return []

def save_transaction(filename: str, transaction: dict):
    """Saves a single transaction to the JSON file."""
    transactions = load_transactions(filename)
    transactions.append(transaction)
    with open(filename, 'w') as f:
        json.dump(transactions, f, indent=4)
    print(f"Transaction recorded: {transaction}")

# ------------------- Ejecución -------------------

if __name__ == "__main__":

    stock_data = get_stock_data(stock1)
    if stock_data:
        # Initial fetch of historical data
        # Changed period to "3d" to show only the last 3 days' data
        stock_history_initial = get_stock_history(stock1, period="3d", interval="15m")
        if not stock_history_initial.empty:
            recommendation, cleaned_history = analyse_stock_data(stock_data, stock_history_initial)
            print(f"\nRecomendación final para {stock1}: {recommendation}")
            
            # Call the plotting function
            plot_stock_analysis(stock1, cleaned_history, recommendation)

            # The interactive buy/sell prompt has been removed as requested.
            # If you want to add a new way to record transactions, you can do it here.
        else:
            print(f"No se pudo obtener el historial de datos para {stock1}. No se realizará el análisis.")
    else:
        print(f"No se pudo obtener la información general para {stock1}. No se realizará el análisis.")
