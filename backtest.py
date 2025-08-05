# trading_simulator.py
import pandas as pd
import ta # Para los indicadores técnicos
from datetime import datetime, timedelta
import json
import os   # Para interactuar con el sistema de archivos

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

def get_recommendation(df_with_indicators): # Renamed df_slice to df_with_indicators
    """
    Genera una recomendación de trading (Comprar, Vender, Observar, Mantener)
    basada en los indicadores del slice de datos proporcionado.
    """
    # This check ensures that the DataFrame has enough rows AFTER dropna
    # for all indicators to have been calculated and for safe access of last_row and prev_row.
    # The largest window is 26 for MACD. So, at least 26 rows are needed.
    # If df.dropna() leaves fewer than 26 rows, then it's truly "No hay datos suficientes".
    if df_with_indicators.empty or len(df_with_indicators) < 26: 
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
    last_row = df_with_indicators.iloc[-1]
    # Acceder a la fila anterior de forma segura
    prev_row = df_with_indicators.iloc[-2] if len(df_with_indicators) >= 2 else None
    
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
    if prev_row is not None: # Check if prev_row exists
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
    if prev_row is not None and not last_row['Volume_SMA'] == 0:
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

def run_single_simulation(file_path, ticker_symbol, initial_cash, auto_trade_quantity):
    """
    Ejecuta una simulación de trading para un único archivo de datos.
    Retorna el valor final de la cartera y la ganancia/pérdida neta.
    """
    print(f"\n--- Iniciando Simulación para {ticker_symbol} ({os.path.basename(file_path)}) ---")

    try:
        # Leer el CSV: header=0 para usar la primera fila como encabezado, skiprows=[1, 2] para omitir las filas de Ticker y Datetime
        df = pd.read_csv(file_path, header=0, skiprows=[1, 2])
        
        # Renombrar la columna 'Price' a 'Datetime' (ya que contiene las fechas)
        if 'Price' in df.columns:
            df.rename(columns={'Price': 'Datetime'}, inplace=True)
        else:
            print(f"Error: Columna 'Price' (donde deberían estar las fechas) no encontrada en {file_path}. Saltando.")
            return 0, 0

        # Establecer 'Datetime' como el índice y parsear las fechas
        # Usar el formato explícito para evitar UserWarning y asegurar la correcta interpretación
        df.set_index('Datetime', inplace=True)
        df.index = pd.to_datetime(df.index, errors='coerce', format='%Y-%m-%d %H:%M:%S%z') 
        
    except Exception as e:
        print(f"Error al leer o procesar el archivo CSV '{file_path}': {e}. Saltando.")
        return 0, 0

    if df.empty:
        print(f"El archivo '{file_path}' está vacío o no contiene datos válidos después de la lectura inicial. Saltando.")
        return 0, 0

    # Normalizar nombres de columnas: reemplazar espacios y capitalizar la primera letra
    df.columns = [col.replace(' ', '_') for col in df.columns]
    # Asegurarse de que las columnas se capitalicen correctamente
    df.columns = [col.title() for col in df.columns]

    # Convertir explícitamente las columnas numéricas a float, forzando errores a NaN
    # 'Adj Close' ha sido eliminada de aquí ya que no está presente en los archivos del usuario.
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume'] 
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            print(f"Advertencia: Columna '{col}' no encontrada en {file_path}.")
            # Si una columna crítica como 'Close' falta, se salta el archivo
            if col == 'Close':
                print(f"Error: La columna 'Close' es esencial y no se encontró en {file_path}. Saltando.")
                return 0, 0

    df = calculate_indicators(df)
    
    # Eliminar filas con cualquier valor NaN (incluyendo NaT en el índice y NaNs de indicadores)
    df.dropna(inplace=True) 

    if df.empty:
        print(f"No hay suficientes datos válidos para {ticker_symbol} después de limpiar y calcular los indicadores. Saltando.")
        return 0, 0

    portfolio = {
        "cash": initial_cash,
        "stocks": {},  # {ticker: {"qty": X, "avg_price": Y, "buy_date": Z}}
        "closed_trades": []
    }
    last_auto_trade_rec_for_ticker = None 

    # --- CAMBIO CLAVE AQUÍ: Ajustar el rango del bucle para asegurar suficientes datos para la recomendación ---
    # El bucle debe empezar desde un índice que asegure que get_recommendation reciba al menos 26 filas.
    # Si df.dropna() ya eliminó las filas iniciales con NaN, el primer índice de df ya es válido.
    # Sin embargo, get_recommendation necesita al menos 26 filas *para su lógica interna de iloc[-1] y iloc[-2]*
    # y para que los indicadores (aunque precalculados) tengan sentido en el contexto del slice.
    # Por lo tanto, el bucle debe empezar desde el índice 25 (para tener 26 filas de 0 a 25)
    # o desde el primer índice válido si df es más corto.
    start_index = 25 # Minimum rows needed for get_recommendation to not return "No hay datos suficientes"
    if len(df) <= start_index:
        print(f"Advertencia: El DataFrame para {ticker_symbol} es demasiado corto ({len(df)} filas) para ejecutar la simulación con la lógica de recomendación. Se necesitan al menos {start_index + 1} filas después de la limpieza. Saltando.")
        return 0, 0 # Retorna 0 si no hay suficientes datos para la simulación

    for i in range(start_index, len(df)):
        current_time = df.index[i]
        current_price = df['Close'].iloc[i]
        
        # --- CAMBIO CLAVE AQUÍ: Pasar el slice de datos hasta el punto actual de la simulación ---
        # Esto asegura que get_recommendation toma decisiones basadas solo en el historial disponible hasta 'i'.
        recommendation = get_recommendation(df.iloc[:i+1]) 

        # Si la recomendación es "No hay datos suficientes", significa que el slice actual
        # es demasiado corto para los cálculos de indicadores, a pesar de que el DF completo
        # ya fue procesado. Esto se maneja con el start_index.
        if recommendation == "No hay datos suficientes":
            continue

        if recommendation == "📈 Comprar":
            if last_auto_trade_rec_for_ticker != "📈 Comprar":
                costo_total = auto_trade_quantity * current_price
                if portfolio["cash"] >= costo_total:
                    if ticker_symbol not in portfolio["stocks"]:
                        portfolio["stocks"][ticker_symbol] = {"qty": auto_trade_quantity, "avg_price": current_price, "buy_date": current_time.strftime("%Y-%m-%d %H:%M:%S")}
                    else:
                        old_qty = portfolio["stocks"][ticker_symbol]["qty"]
                        old_avg_price = portfolio["stocks"][ticker_symbol]["avg_price"]
                        new_total_cost = (old_qty * old_avg_price) + (auto_trade_quantity * current_price)
                        new_total_qty = old_qty + auto_trade_quantity
                        portfolio["stocks"][ticker_symbol]["qty"] = new_total_qty
                        portfolio["stocks"][ticker_symbol]["avg_price"] = new_total_cost / new_total_qty
                    
                    portfolio["cash"] -= costo_total
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA: {auto_trade_quantity} acciones de {ticker_symbol} a ${current_price:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📈 Comprar"
                else:
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA (FALLIDA): Fondos insuficientes.")
        
        elif recommendation == "📉 Vender":
            if last_auto_trade_rec_for_ticker != "📉 Vender":
                if ticker_symbol in portfolio["stocks"] and portfolio["stocks"][ticker_symbol]["qty"] >= auto_trade_quantity:
                    avg_buy_price = portfolio["stocks"][ticker_symbol]["avg_price"]
                    realized_pnl = (current_price - avg_buy_price) * auto_trade_quantity
                    
                    portfolio["cash"] += auto_trade_quantity * current_price
                    
                    portfolio["closed_trades"].append({
                        "Fecha Venta": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Ticker": ticker_symbol,
                        "Cantidad": auto_trade_quantity,
                        "Precio Compra Promedio": round(avg_buy_price, 2),
                        "Precio Venta": round(current_price, 2),
                        "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
                    })

                    portfolio["stocks"][ticker_symbol]["qty"] -= auto_trade_quantity
                    if portfolio["stocks"][ticker_symbol]["qty"] == 0:
                        del portfolio["stocks"][ticker_symbol]
                    
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA: {auto_trade_quantity} acciones de {ticker_symbol} a ${current_price:.2f}. P/L Realizado: ${realized_pnl:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📉 Vender"
                else:
                    print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA (FALLIDA): No hay suficientes acciones para vender.")
        else:
            last_auto_trade_rec_for_ticker = recommendation 
            # print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - {recommendation} para {ticker_symbol}") # Descomentar para ver cada paso

    # --- Resumen de la Simulación Individual ---
    print(f"\n--- Resumen para {ticker_symbol} ---")
    print(f"Efectivo Inicial: ${initial_cash:.2f}")
    print(f"Efectivo Final: ${portfolio['cash']:.2f}")

    total_current_stock_value = 0
    total_unrealized_pnl = 0
    print("Posiciones Abiertas al Final:")
    if portfolio["stocks"]:
        for ticker_held, stock_info in portfolio["stocks"].items():
            # Ensure df is not empty before accessing iloc[-1]
            if not df.empty:
                current_price_held = df['Close'].iloc[-1] 
                unrealized_pnl = (current_price_held - stock_info["avg_price"]) * stock_info["qty"]
                total_current_stock_value += current_price_held * stock_info["qty"]
                total_unrealized_pnl += unrealized_pnl
                print(f"  {ticker_held}: {stock_info['qty']} acciones @ ${stock_info['avg_price']:.2f} (Compra). Valor actual: ${current_price_held * stock_info['qty']:.2f}. P/L No Realizado: ${unrealized_pnl:.2f}")
            else:
                print(f"  No se pudo calcular el valor de las acciones para {ticker_held} debido a la falta de datos.")
    else:
        print("  Ninguna posición abierta.")

    total_realized_pnl = sum(trade["Ganancia/Pérdida Realizada"] for trade in portfolio["closed_trades"])
    
    final_portfolio_value = portfolio["cash"] + total_current_stock_value
    net_pnl = final_portfolio_value - initial_cash

    print(f"Valor Total de Acciones Abiertas: ${total_current_stock_value:.2f}")
    print(f"Ganancia/Pérdida No Realizada Total: ${total_unrealized_pnl:.2f}")
    print(f"Ganancia/Pérdida Realizada Total: ${total_realized_pnl:.2f}")
    print(f"Valor Total Final de Cartera: ${final_portfolio_value:.2f}")
    print(f"Ganancia/Pérdida Neta Total: ${net_pnl:.2f}")

    return final_portfolio_value, net_pnl, total_realized_pnl


def run_multiple_simulations(folder_path, initial_cash=100000.0, auto_trade_quantity=10):
    """
    Ejecuta simulaciones de trading para todos los archivos CSV en una carpeta dada.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: La carpeta '{folder_path}' no existe. Por favor, asegúrate de que esté creada y contenga los archivos CSV.")
        return

    all_results = []
    
    print(f"\n--- Iniciando Múltiples Simulaciones desde la carpeta: {folder_path} ---")
    print(f"Efectivo inicial por simulación: ${initial_cash:.2f}")
    print(f"Cantidad por operación automática: {auto_trade_quantity}\n")

    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)
            
            # Intentar extraer el ticker del nombre del archivo (ej. AAPL_2025_07_15m.csv)
            try:
                ticker_symbol = filename.split('_')[0]
            except IndexError:
                print(f"Advertencia: No se pudo extraer el ticker del nombre de archivo '{filename}'. Saltando.")
                continue

            final_value, net_pnl, realized_pnl = run_single_simulation(file_path, ticker_symbol, initial_cash, auto_trade_quantity)
            if final_value > 0: # Solo si la simulación no fue saltada por falta de datos
                all_results.append({
                    "Ticker": ticker_symbol,
                    "Archivo": filename,
                    "Valor Final Cartera": final_value,
                    "Ganancia/Pérdida Neta": net_pnl,
                    "Ganancia/Pérdida Realizada": realized_pnl
                })
            print("-" * 50) # Separador entre simulaciones

    print("\n\n--- Resumen General de Todas las Simulaciones ---")
    if all_results:
        results_df = pd.DataFrame(all_results)
        print(results_df.to_string(index=False)) # Imprime el DataFrame sin el índice
        
        total_pnl_net = results_df["Ganancia/Pérdida Neta"].sum()
        total_realized_pnl_all = results_df["Ganancia/Pérdida Realizada"].sum()
        
        print(f"\nGanancia/Pérdida Neta Total (todas las simulaciones): ${total_pnl_net:.2f}")
        print(f"Ganancia/Pérdida Realizada Total (todas las simulaciones): ${total_realized_pnl_all:.2f}")
        
        # Opcional: Calcular el porcentaje de ganancia/pérdida promedio
        avg_pnl_percent = (total_pnl_net / (len(all_results) * initial_cash)) * 100
        print(f"Rendimiento Promedio por Simulación: {avg_pnl_percent:.2f}%")

    else:
        print("No se realizaron simulaciones exitosas.")

if __name__ == "__main__":
    # --- Configura aquí la carpeta que contiene tus archivos de backtest ---
    BACKTEST_DATA_FOLDER = "BacktestData" 

    # --- Configuración de la simulación ---
    SIMULATION_INITIAL_CASH = 100000.0 # Efectivo inicial para CADA simulación
    SIMULATION_AUTO_TRADE_QUANTITY = 10 # Cuántas acciones comprar/vender en cada operación automática

    run_multiple_simulations(BACKTEST_DATA_FOLDER, SIMULATION_INITIAL_CASH, SIMULATION_AUTO_TRADE_QUANTITY)
