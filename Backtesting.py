import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# --- VALORES INICIALES PARA LA SIMULACIÓN ---
stock_ticker = "AAPL"
start_date = "2025-07-01"
end_date = "2025-08-01"
initial_capital = 10000.0

def download_historical_data(ticker, start, end):
    """
    Descarga los datos históricos del stock usando yfinance.
    """
    try:
        print(f"Descargando datos históricos para {ticker} desde {start} hasta {end}...")
        history_data = yf.download(ticker, start=start, end=end, interval="15m")
        if history_data.empty:
            print("No se pudieron descargar los datos. Comprueba la conexión y el ticker.")
            return None
        return history_data
    except Exception as e:
        print(f"Error al descargar los datos: {e}")
        return None

def analyse_stock_data(row: pd.Series):
    """
    Implementa una lógica de recomendación de compra, venta o mantenimiento.
    """
    COEF_INTRADAY_TREND = 2.5
    COEF_VOLUME = 2.0
    COEF_LONG_TERM = 0.5
    COEF_RSI_OVERSOLD = 2.8
    COEF_RSI_OVERBOUGHT = 2.8
    DECISION_THRESHOLD = 2.0

    buy_score = 0.0
    sell_score = 0.0

    last_close = row['Close']
    current_volume = row['Volume']
    
    # Se ha ajustado el nombre de la columna y el periodo
    fifty_day_average = row['SMA_400']
    average_volume_10_days = row['SMA_100_Volume']
    
    sma_10 = row['SMA_10']
    current_rsi = row['RSI']

    # 1. Tendencia largo plazo (comparación con media de 400 velas, ajustado)
    if pd.notna(fifty_day_average) and pd.notna(last_close):
        if last_close > fifty_day_average:
            buy_score += COEF_LONG_TERM
        elif last_close < fifty_day_average:
            sell_score += COEF_LONG_TERM

    # 2. Volumen actual vs volumen promedio (ajustado a 100 velas)
    if pd.notna(current_volume) and pd.notna(average_volume_10_days):
        if current_volume > 1.5 * average_volume_10_days:
            buy_score += COEF_VOLUME
        elif current_volume < 0.5 * average_volume_10_days:
            sell_score += COEF_VOLUME

    # 3. Tendencia intradía con SMA 10
    if pd.notna(last_close) and pd.notna(sma_10):
        if last_close > sma_10:
            buy_score += COEF_INTRADAY_TREND
        elif last_close < sma_10:
            sell_score += COEF_INTRADAY_TREND

    # 4. RSI
    if pd.notna(current_rsi):
        if current_rsi < 30:
            buy_score += COEF_RSI_OVERSOLD
        elif current_rsi > 70:
            sell_score += COEF_RSI_OVERBOUGHT

    # 5. Decisión final
    if buy_score - sell_score > DECISION_THRESHOLD:
        return "Comprar", buy_score, sell_score
    elif sell_score - buy_score > DECISION_THRESHOLD:
        return "Vender", buy_score, sell_score
    else:
        return "Mantener", buy_score, sell_score

def backtest_strategy(ticker, start, end, capital):
    print(f"--- Iniciando Backtesting para {ticker} ---")
    print(f"Periodo: {start} a {end}")
    print(f"Capital inicial: ${capital:.2f}\n")

    try:
        history_data = download_historical_data(ticker, start, end)
        if history_data is None or history_data.empty:
            print("No se encontraron datos para la simulación.")
            return

        # Ajuste de los periodos de las medias móviles para que la simulación sea viable
        history_data['SMA_10'] = history_data['Close'].rolling(window=10).mean()
        history_data['SMA_400'] = history_data['Close'].rolling(window=400).mean()
        history_data['SMA_100_Volume'] = history_data['Volume'].rolling(window=100).mean()

        # RSI
        rsi_period = 14
        delta = history_data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()
        rs = gain / loss
        history_data['RSI'] = 100 - (100 / (1 + rs))

        current_capital = capital
        shares_owned = 0
        transactions = []
        purchase_price = 0.0

        for i, row in history_data.iterrows():
            current_price = row['Close']

            # La validación revisa si los indicadores tienen valores numéricos
            if all(pd.notna([current_price, row['SMA_10'], row['SMA_400'], row['SMA_100_Volume'], row['RSI']])):
                recommendation, buy_score, sell_score = analyse_stock_data(row)

                if recommendation == "Comprar" and shares_owned == 0:
                    # Se añade una comprobación para asegurar que el precio es un valor numérico
                    if pd.notna(current_price) and isinstance(current_price, (int, float)):
                        shares_to_buy = int(current_capital // current_price)
                        if shares_to_buy > 0:
                            cost = shares_to_buy * current_price
                            current_capital -= cost
                            shares_owned = shares_to_buy
                            purchase_price = current_price
                            transactions.append(f"COMPRA: {shares_to_buy} acciones a ${current_price:.2f} el {i.strftime('%Y-%m-%d %H:%M')}. Capital restante: ${current_capital:.2f}")
                elif recommendation == "Vender" and shares_owned > 0:
                    # Se añaden comprobaciones explícitas de tipo y valor antes de la comparación
                    if pd.notna(current_price) and isinstance(current_price, (int, float)) and \
                       pd.notna(purchase_price) and isinstance(purchase_price, (int, float)) and \
                       current_price > purchase_price:
                        revenue = shares_owned * current_price
                        current_capital += revenue
                        profit = (current_price - purchase_price) * shares_owned
                        transactions.append(f"VENTA: {shares_owned} acciones a ${current_price:.2f} el {i.strftime('%Y-%m-%d %H:%M')}. Ganancia: ${profit:.2f}. Capital total: ${current_capital:.2f}")
                        shares_owned = 0
                        purchase_price = 0.0

        print("\n" + "="*40)
        print("--- Resumen de la Estrategia ---")
        print("="*40)
        if not transactions:
            print("No se realizaron transacciones durante el periodo.")
        else:
            for t in transactions:
                print(t)

        # Se añade una comprobación para purchase_price en el cálculo final
        # Si shares_owned > 0, significa que no se vendió la última posición.
        # En ese caso, su valor se calcula a partir del precio de cierre de la última fila.
        final_capital = current_capital
        if shares_owned > 0 and pd.notna(purchase_price) and isinstance(purchase_price, (int, float)):
             final_capital += shares_owned * history_data.iloc[-1]['Close']
        
        profit_loss = final_capital - initial_capital

        print("\n" + "="*40)
        print(f"Capital inicial:   ${initial_capital:.2f}")
        print(f"Capital final:     ${final_capital:.2f}")
        print(f"Ganancia/Pérdida:  ${profit_loss:.2f}")
        if shares_owned > 0 and pd.notna(purchase_price):
            print(f"Acciones sin vender: {shares_owned} a un precio de compra de ${purchase_price:.2f}")
        print("="*40)

    except Exception as e:
        print(f"Ocurrió un error durante el backtesting: {e}")

if __name__ == "__main__":
    backtest_strategy(stock_ticker, start_date, end_date, initial_capital)