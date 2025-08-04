import json
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai
import pandas as pd


## VALUES
stock1 = "AAPL"

with open(r"C:\Users\rodri\Documentos\Finance\claves.json","r") as k:
    claves = json.load(k)
genai.configure(api_key=claves["gemini"])

def get_stock_data(ticker: str):
    
    ## Fetches the latest stock data for a given ticker symbol.
    
    try:

        stock = yf.Ticker(ticker)
       
        # Get the current price
        current_price = stock.info.get('currentPrice', 'N/A')
        print(f"\nCurrent Price: {current_price}\n")
        
        return stock.info

    except Exception as e:
        print(f"Could not fetch data for {ticker}. Error: {e}")

def get_stock_history(ticker: str):

    # Get historical market data for the last 5 days with a 15 min interval
    try:
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d", interval = "15m")

        print(f"--- Datos recientes para {ticker} ---")
        print(hist.tail()) # Muestra los últimos 5 registros

        return hist

    except Exception as e:
        print(f"Could not get data from {ticker}. Error:{e}")

def analyse_stock_data(data: dict, history: pd.DataFrame):
    """
    Implementa una lógica de recomendación de compra, venta o mantenimiento
    basada en indicadores técnicos simples y coeficientes de peso.
    """
    try:
        analist_recomendation = data.get("recommendationKey")
        current_price = data.get("currentPrice")
        fifty_day_average = data.get('fiftyDayAverage')
        volume = data.get('volume')
        average_volume_10_days = data.get('averageVolume10days')

        # --- Lógica de recomendación intradía con coeficientes ---
        
        # Coeficientes para cada indicador
        COEF_INTRADAY_TREND = 1.5
        COEF_VOLUME = 1.2
        COEF_LONG_TERM = 0.8
        
        # Inicializa los puntajes de señales
        buy_score = 0.0
        sell_score = 0.0
        
        # 1. Comparación del precio actual con el promedio de 50 días.
        # Es un indicador de largo plazo, así que le damos un peso menor.
        if current_price and fifty_day_average:
            if current_price > fifty_day_average:
                buy_score += COEF_LONG_TERM
            elif current_price < fifty_day_average:
                sell_score += COEF_LONG_TERM

        # 2. Análisis del volumen vs. volumen promedio.
        # Una subida significativa del volumen indica un movimiento fuerte.
        if volume and average_volume_10_days:
            if volume > 1.5 * average_volume_10_days:
                buy_score += COEF_VOLUME # Se asume un impulso de compra, puede variar.
            elif volume < 0.5 * average_volume_10_days:
                sell_score += COEF_VOLUME # Baja actividad, posible falta de interés.

        # 3. Análisis de la tendencia intradía con una Media Móvil Simple (SMA).
        # Este es el indicador más importante para el trading intradía, por eso tiene el mayor peso.
        if history is not None and not history.empty:
            # Calculamos la SMA de 10 periodos (10 x 15min = 150min o 2.5h)
            history['SMA_10'] = history['Close'].rolling(window=10).mean()
            
            # Comparamos el precio de cierre actual con la última SMA de 10
            last_close = history['Close'].iloc[-1]
            last_sma = history['SMA_10'].iloc[-1]
            
            if last_close > last_sma:
                buy_score += COEF_INTRADAY_TREND
            elif last_close < last_sma:
                sell_score += COEF_INTRADAY_TREND
        
        # 4. Decisión final basada en los puntajes
        final_recomendation = "Mantener" # Predeterminado
        if buy_score > sell_score:
            final_recomendation = "Comprar"
        elif sell_score > buy_score:
            final_recomendation = "Vender"
            
        print("\n--- Resultados del Análisis ---")
        print(f"Recomendación del analista (Yahoo Finance): {analist_recomendation}")
        print(f"Puntuación de compra: {buy_score:.2f}")
        print(f"Puntuación de venta: {sell_score:.2f}")
        print("----------------------------")
        print(f"Recomendación de la lógica: {final_recomendation}")
        
        return final_recomendation

    except Exception as e:
        print(f"No se pudieron analizar los datos. Error: {e}")
        return "Error"

if __name__ == "__main__":
    stock_data = get_stock_data(stock1)
    stock_history = get_stock_history(stock1)
    recommendation = analyse_stock_data(stock_data, stock_history)
    print(f"\nRecomendación final para {stock1}: {recommendation}")
