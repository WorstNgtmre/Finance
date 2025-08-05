# data_downloader.py
import yfinance as yf
from datetime import datetime
import pandas as pd

def download_stock_data(ticker, year, month, interval="15m"):
    """
    Descarga datos históricos de un ticker para un mes y año específicos.

    Args:
        ticker (str): Símbolo del activo (ej. "AAPL").
        year (int): Año de los datos (ej. 2023).
        month (int): Mes de los datos (1-12, ej. 7 para Julio).
        interval (str): Intervalo de los datos (ej. "15m", "1h").
                        Para day trading, "15m" o "30m" son comunes.
    """
    # Calcular el primer día del mes
    start_date = datetime(year, month, 1)
    
    # Calcular el último día del mes
    # Si es diciembre, el mes siguiente es enero del año siguiente
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    print(f"Descargando datos para {ticker} desde {start_date.strftime('%Y-%m-%d')} hasta {end_date.strftime('%Y-%m-%d')} con intervalo {interval}...")
    
    try:
        # yfinance usa 'end' exclusivo, por eso el mes siguiente
        df = yf.download(ticker, start=start_date, end=end_date, interval=interval)
        
        if df.empty:
            print(f"No se encontraron datos para {ticker} en el período especificado.")
            return

        # Limpiar datos: eliminar filas con volumen cero (fuera de horario de mercado)
        df = df[df['Volume'] > 0]

        # Crear un nombre de archivo descriptivo
        file_name = r"BacktestData/" + f"{ticker}_{year}_{month:02d}_{interval}.csv"
        df.to_csv(file_name)
        print(f"Datos descargados y guardados en {file_name}")

    except Exception as e:
        print(f"Error al descargar datos para {ticker}: {e}")

if __name__ == "__main__":
    # --- Configura aquí el ticker, año y mes que quieres descargar ---
    TICKER_TO_DOWNLOAD = "PLD" # Ejemplo: Microsoft
    YEAR_TO_DOWNLOAD = 2025
    MONTH_TO_DOWNLOAD = 7 # Junio
    INTERVAL_TO_DOWNLOAD = "15m" # Intervalo de 15 minutos
    try:
        download_stock_data(TICKER_TO_DOWNLOAD, YEAR_TO_DOWNLOAD, MONTH_TO_DOWNLOAD, INTERVAL_TO_DOWNLOAD)
        print("\n¡Descarga de datos completada!")
    except Exception as e:
        print(f"An error ocurred. Error {e}")