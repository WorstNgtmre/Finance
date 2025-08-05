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

def get_recommendation(df_slice):
    """
    Genera una recomendación de trading (Comprar, Vender, Observar, Mantener)
    basada en los indicadores del slice de datos proporcionado.
    """
    if df_slice.empty or len(df_slice) < max(14, 20, 10, 26): # Asegura que haya suficientes datos para los indicadores
        # El 26 es la ventana por defecto para MACD, aunque ta lo maneje internamente, es bueno para la precaución.
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

def run_single_simulation(file_path, ticker_symbol, initial_cash, auto_trade_quantity):
    """
    Ejecuta una simulación de trading para un único archivo de datos.
    Retorna el valor final de la cartera y la ganancia/pérdida neta.
    """
    print(f"\n--- Iniciando Simulación para {ticker_symbol} ({os.path.basename(file_path)}) ---")

    # --- CAMBIO REALIZADO: Eliminada la línea redundante df.index = pd.to_datetime(df.index) ---
    # Asumiendo que el CSV tiene 'Ticker' como la primera columna y 'Datetime' como la segunda.
    # Si tu CSV tiene 'Datetime' como la primera columna, cambia index_col de nuevo a 0.
    df = pd.read_csv(file_path, index_col=1, parse_dates=True) 
    
    if df.empty:
        print(f"El archivo '{file_path}' está vacío o no contiene datos válidos. Saltando.")
        return 0, 0 # Retorna 0 si no hay datos

    # df.index = pd.to_datetime(df.index) # Esta línea ha sido eliminada
    df = calculate_indicators(df)
    df.dropna(inplace=True) 
    
    if df.empty:
        print(f"No hay suficientes datos válidos para {ticker_symbol} después de calcular los indicadores. Saltando.")
        return 0, 0

    portfolio = {
        "cash": initial_cash,
        "stocks": {},  # {ticker: {"qty": X, "avg_price": Y, "buy_date": Z}}
        "closed_trades": []
    }
    last_auto_trade_rec_for_ticker = None 

    # Determinar el tamaño de la ventana de datos para los indicadores
    window_size = 30 

    for i in range(len(df)):
        if i < window_size - 1:
            continue

        current_time = df.index[i]
        current_price = df['Close'].iloc[i]
        
        df_slice = df.iloc[max(0, i - window_size + 1):i+1]
        
        recommendation = get_recommendation(df_slice)

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
                    # print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA: {auto_trade_quantity} acciones de {ticker_symbol} a ${current_price:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📈 Comprar"
                # else:
                #     print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - COMPRA (FALLIDA): Fondos insuficientes.")
        
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
                    
                    # print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA: {auto_trade_quantity} acciones de {ticker_symbol} a ${current_price:.2f}. P/L Realizado: ${realized_pnl:.2f}. Efectivo: ${portfolio['cash']:.2f}")
                    last_auto_trade_rec_for_ticker = "📉 Vender"
                # else:
                #     print(f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} - VENTA (FALLIDA): No hay suficientes acciones para vender.")
        else:
            last_auto_trade_rec_for_ticker = recommendation 

    # --- Resumen de la Simulación Individual ---
    print(f"\n--- Resumen para {ticker_symbol} ---")
    print(f"Efectivo Inicial: ${initial_cash:.2f}")
    print(f"Efectivo Final: ${portfolio['cash']:.2f}")

    total_current_stock_value = 0
    total_unrealized_pnl = 0
    print("Posiciones Abiertas al Final:")
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
