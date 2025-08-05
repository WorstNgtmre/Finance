# trading_simulator.py
import pandas as pd
import ta # Para los indicadores técnicos
from datetime import datetime, timedelta
import json # Para cargar la estructura del portfolio si es necesario
import os   # Para verificar si el archivo de datos existe

# --------------------- LÓGICA DE INDICADORES Y RECOMENDACIÓN (COPIADA EXACTAMENTE DE TU CÓDIGO) ---------------------

def calculate_indicators(df):
    """
    Calcula varios indicadores técnicos usando la librería 'ta' y los añade al DataFrame.
    """
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()
    df['MACD_hist'] = macd.macd_diff()
    boll = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['Upper'] = boll.bollinger_hband()
    df['Lower'] = boll.bollinger_lband()
    df['SMA20'] = ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator()
    df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx()
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()
    df['Volume_SMA'] = df['Volume'].rolling(window=10).mean()
    return df

def get_recommendation(df_slice):
    """
    Genera una recomendación de trading (Comprar, Vender, Observar, Mantener)
    basada en los indicadores del slice de datos proporcionado.
    """
    if df_slice.empty or len(df_slice) < max(14, 20, 10): # Asegura que haya suficientes datos para los indicadores
        return "No hay datos suficientes"

    # --- Coeficientes para el peso de cada indicador (ajustables para day trading) ---
    COEF_BOLLINGER = 1.0
    COEF_RSI = 2.0
    COEF_MACD = 2.0
    COEF_STOCH = 2.0
    COEF_ADX_SMA = 1.0
    COEF_VOLUME = 1.0
    # ---------------------------------------------------------------------------------

    buy_score = 0.0
    sell_score = 0.0

    # Usar el último punto de datos para la decisión
    last_row = df_slice.iloc[-1]
    
    # Reglas de Bandas de Bollinger
    if last_row['Close'] < last_row['Lower']:
        buy_score += COEF_BOLLINGER
    if last_row['Close'] > last_row['Upper']:
        sell_score += COEF_BOLLINGER

    # Reglas de RSI
    if last_row['RSI'] < 30:
        buy_score += COEF_RSI
    elif last_row['RSI'] > 70:
        sell_score += COEF_RSI

    # Reglas de MACD (cruce de líneas)
    if len(df_slice) >= 2: # Asegura que haya al menos dos puntos para el cruce
        prev_row = df_slice.iloc[-2]
        if last_row['MACD'] > last_row['Signal'] and prev_row['MACD'] <= prev_row['Signal']:
            buy_score += COEF_MACD
        elif last_row['MACD'] < last_row['Signal'] and prev_row['MACD'] >= prev_row['Signal']:
            sell_score += COEF_MACD

    # Reglas de Oscilador Estocástico
    if last_row['Stoch_K'] < 20 and last_row['Stoch_D'] < 20:
        buy_score += COEF_STOCH
    elif last_row['Stoch_K'] > 80 and last_row['Stoch_D'] > 80:
        sell_score += COEF_STOCH

    # Reglas de ADX y SMA20
    if last_row['ADX'] > 25:
        if last_row['Close'] > last_row['SMA20']:
            buy_score += COEF_ADX_SMA
        else:
            sell_score += COEF_ADX_SMA

    # Nueva Regla de Volumen
    if len(df_slice) >= 2 and not last_row['Volume_SMA'] == 0:
        if last_row['Volume'] > (1.5 * last_row['Volume_SMA']):
            if last_row['Close'] > prev_row['Close']:
                buy_score += COEF_VOLUME
            elif last_row['Close'] < prev_row['Close']:
                sell_score += COEF_VOLUME

    if buy_score > sell_score + 1.0:
        return "📈 Comprar"
    elif sell_score > buy_score + 1.0:
        return "📉 Vender"
    elif buy_score > 0.0 or sell_score > 0.0:
        return "👁 Observar"
    else:
        return "🤝 Mantener"

# --------------------- SIMULADOR DE TRADING ---------------------

def run_simulation(file_path, initial_cash=100000.0, auto_trade_quantity=10):
    """
    Ejecuta una simulación de trading utilizando la lógica de recomendación.

    Args:
        file_path (str): Ruta al archivo CSV con los datos históricos.
        initial_cash (float): Cantidad de efectivo inicial para la simulación.
        auto_trade_quantity (int): Cantidad de acciones a comprar/vender en cada operación automática.
    """
    if not os.path.exists(file_path):
        print(f"Error: El archivo de datos '{file_path}' no se encontró. Por favor, descárgalo primero con data_downloader.py")
        return

    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    
    if df.empty:
        print(f"El archivo '{file_path}' está vacío o no contiene datos válidos.")
        return

    # Asegurarse de que el índice sea DatetimeIndex para operaciones de tiempo
    df.index = pd.to_datetime(df.index)

    # Calcular todos los indicadores una vez para todo el DataFrame
    df = calculate_indicators(df)

    # Eliminar filas con NaN en indicadores (primeros N periodos)
    df.dropna(inplace=True) 
    
    if df.empty:
        print("No hay suficientes datos válidos después de calcular los indicadores. Asegúrate de descargar un período más largo.")
        return

    # Inicializar el portfolio para la simulación
    portfolio = {
        "cash": initial_cash,
        "stocks": {},  # {ticker: {"qty": X, "avg_price": Y, "buy_date": Z}}
        "closed_trades": [] # Historial de ventas realizadas
    }
    
    # Para evitar operaciones repetidas en la misma señal
    last_auto_trade_rec_for_ticker = None 

    print(f"\n--- Iniciando Simulación de Trading para {file_path} ---")
    print(f"Efectivo inicial: ${portfolio['cash']:.2f}")
    print(f"Cantidad por operación automática: {auto_trade_quantity}\n")

    # Determinar el tamaño de la ventana de datos para los indicadores
    # Esto es el máximo de las ventanas de los indicadores (RSI 14, BB 20, Volume_SMA 10, MACD 26, Stoch 14)
    # Usaremos una ventana de 30 para asegurarnos de tener suficientes datos históricos para cualquier indicador.
    window_size = 30 

    for i in range(len(df)):
        # Asegurarse de tener suficientes datos para calcular los indicadores
        if i < window_size - 1:
            continue # Saltar hasta que tengamos suficientes datos para la primera ventana

        current_time = df.index[i]
        current_price = df['Close'].iloc[i]
        
        # Obtener el slice de datos necesario para la recomendación
        df_slice = df.iloc[max(0, i - window_size + 1):i+1]
        
        # Obtener la recomendación
        recommendation = get_recommendation(df_slice)

        # Lógica de auto-trading
        if recommendation == "📈 Comprar":
            if last_auto_trade_rec_for_ticker != "📈 Comprar":
                costo_total = auto_trade_quantity * current_price
                if portfolio["cash"] >= costo_total:
                    # Actualizar portfolio["stocks"] con el precio promedio de compra
                    if file_path.split('_')[0] not in portfolio["stocks"]: # Usa el ticker del nombre del archivo
                        portfolio["stocks"][file_path.split('_')[0]] = {"qty": auto_trade_quantity, "avg_price": current_price, "buy_date": current_time.strftime("%Y-%m-%d %H:%M:%S")}
                    else:
                        old_qty = portfolio["stocks"][file_path.split('_')[0]]["qty"]
                        old_avg_price = portfolio["stocks"][file_path.split('_')[0]]["avg_price"]
                        new_total_cost = (old_qty * old_avg_price) + (auto_trade_quantity * current_price)
                        new_total_qty = old_qty + auto_trade_quantity
                        portfolio["stocks"][file_path.split('_')[0]]["qty"] = new_total_qty
                        portfolio["stocks"][file_path.split('_')[0]]["avg_price"] = new_total_cost / new_total_qty
                    
                    portfolio["cash"] -= costo_total
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA: {auto_trade_quantity} acciones de {file_path.split('_')[0]} a ${current_price:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📈 Comprar"
                # else:
                #     print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA (FALLIDA): Fondos insuficientes.")
        
        elif recommendation == "📉 Vender":
            if last_auto_trade_rec_for_ticker != "📉 Vender":
                ticker_in_portfolio = file_path.split('_')[0]
                if ticker_in_portfolio in portfolio["stocks"] and portfolio["stocks"][ticker_in_portfolio]["qty"] >= auto_trade_quantity:
                    avg_buy_price = portfolio["stocks"][ticker_in_portfolio]["avg_price"]
                    realized_pnl = (current_price - avg_buy_price) * auto_trade_quantity
                    
                    portfolio["cash"] += auto_trade_quantity * current_price
                    
                    # Añadir a closed_trades
                    portfolio["closed_trades"].append({
                        "Fecha Venta": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Ticker": ticker_in_portfolio,
                        "Cantidad": auto_trade_quantity,
                        "Precio Compra Promedio": round(avg_buy_price, 2),
                        "Precio Venta": round(current_price, 2),
                        "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
                    })

                    portfolio["stocks"][ticker_in_portfolio]["qty"] -= auto_trade_quantity
                    if portfolio["stocks"][ticker_in_portfolio]["qty"] == 0:
                        del portfolio["stocks"][ticker_in_portfolio]
                    
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA: {auto_trade_quantity} acciones de {ticker_in_portfolio} a ${current_price:.2f}. P/L Realizado: ${realized_pnl:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📉 Vender"
                # else:
                #     print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA (FALLIDA): No hay suficientes acciones para vender.")
        else:
            # Si la recomendación no es ni comprar ni vender, "reseteamos" la última recomendación
            # para que pueda volver a comprar/vender si la recomendación cambia a una de esas.
            last_auto_trade_rec_for_ticker = recommendation 
            # print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - {recommendation} para {file_path.split('_')[0]}") # Descomentar para ver cada paso

    # --- Resumen de la Simulación ---
    print("\n--- Simulación Finalizada ---")
    print(f"Efectivo Inicial: ${initial_cash:.2f}")
    print(f"Efectivo Final: ${portfolio['cash']:.2f}")

    total_current_stock_value = 0
    total_unrealized_pnl = 0
    print("\nPosiciones Abiertas al Final:")
    if portfolio["stocks"]:
        for ticker_held, stock_info in portfolio["stocks"].items():
            current_price_held = df['Close'].iloc[-1] # Usar el último precio disponible en el DF
            unrealized_pnl = (current_price_held - stock_info["avg_price"]) * stock_info["qty"]
            total_current_stock_value += current_price_held * stock_info["qty"]
            total_unrealized_pnl += unrealized_pnl
            print(f"  {ticker_held}: {stock_info['qty']} acciones @ ${stock_info['avg_price']:.2f} (Compra). Valor actual: ${current_price_held * stock_info['qty']:.2f}. P/L No Realizado: ${unrealized_pnl:.2f}")
    else:
        print("  Ninguna posición abierta.")

    total_realized_pnl = sum(trade["Ganancia/Pérdida Realizada"] for trade in portfolio["closed_trades"])
    
    final_portfolio_value = portfolio["cash"] + total_current_stock_value

    print(f"\nValor Total de Acciones Abiertas: ${total_current_stock_value:.2f}")
    print(f"Ganancia/Pérdida No Realizada Total: ${total_unrealized_pnl:.2f}")
    print(f"Ganancia/Pérdida Realizada Total: ${total_realized_pnl:.2f}")
    print(f"Valor Total Final de Cartera: ${final_portfolio_value:.2f}")
    print(f"Ganancia/Pérdida Neta Total: ${final_portfolio_value - initial_cash:.2f}")

    print("\nHistorial de Ventas Realizadas:")
    if portfolio["closed_trades"]:
        for trade in portfolio["closed_trades"]:
            print(f"  {trade['Fecha Venta']} - VENTA {trade['Cantidad']} de {trade['Ticker']} @ ${trade['Precio Venta']:.2f}. P/L Realizado: ${trade['Ganancia/Pérdida Realizada']:.2f}")
    else:
        print("  Ninguna venta realizada.")


if __name__ == "__main__":
    # --- Configura aquí el archivo de datos para la simulación ---
    # Asegúrate de que este archivo exista y haya sido descargado por data_downloader.py
    FILE_TO_SIMULATE = "MSFT_2024_06_15m.csv" # Ejemplo: Datos de Microsoft de Junio 2024 con 15m de intervalo

    # --- Configuración de la simulación ---
    SIMULATION_INITIAL_CASH = 100000.0
    SIMULATION_AUTO_TRADE_QUANTITY = 10 # Cuántas acciones comprar/vender en cada operación automática

    run_simulation(FILE_TO_SIMULATE, SIMULATION_INITIAL_CASH, SIMULATION_AUTO_TRADE_QUANTITY)