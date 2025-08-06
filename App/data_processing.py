# data_processing.py

import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objs as go
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
import yfinance.exceptions

from .config import (
    RSI_OVERSOLD, RSI_OVERBOUGHT, STOCH_OVERSOLD, STOCH_OVERBOUGHT,
    ADX_TREND_THRESHOLD, VOLUME_SMA_MULTIPLIER, BUY_SIGNAL, SELL_SIGNAL,
    OBSERVE_SIGNAL, HOLD_SIGNAL, CACHE_TIMEOUT, GRAPH_DESCRIPTIONS,
    COEF_BOLLINGER, COEF_RSI, COEF_MACD, COEF_STOCH, COEF_ADX_SMA, COEF_VOLUME,
    BUY_SELL_THRESHOLD
)

data_cache: Dict[str, Any] = {}

def get_market_rangebreaks() -> List[Dict[str, Union[str, float]]]:
    """
    Define los rangos de tiempo a omitir en los gráficos (fines de semana y horas de cierre).
    """
    return [
        dict(bounds=["sat", "mon"]),
        dict(bounds=[16, 9.5], pattern="hour")
    ]

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
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

def generate_graphs(df: pd.DataFrame, template: str = 'plotly_dark', title_color: str = 'white') -> Dict[str, go.Figure]:
    """
    Genera todos los objetos de gráfico para un DataFrame dado.
    """
    graphs = {}
    rangebreaks = get_market_rangebreaks()

    # Candlestick
    fig_candlestick = go.Figure(data=[
        go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Velas', increasing_line_color='#66BB6A', decreasing_line_color='#EF5350'),
        go.Scatter(x=df.index, y=df['Close'], name="Precio", connectgaps=False, line=dict(color='#42A5F5', width=1)),
        go.Scatter(x=df.index, y=df['Upper'], name="Banda Sup", connectgaps=False, line=dict(dash='dot', color='#EF5350')),
        go.Scatter(x=df.index, y=df['Lower'], name="Banda Inf", connectgaps=False, line=dict(dash='dot', color='#66BB6A')),
        go.Scatter(x=df.index, y=df['SMA20'], name="SMA20", connectgaps=False, line=dict(dash='dash', color='purple'))
    ])
    fig_candlestick.update_layout(title_text="Precio (Candlestick y Línea) con Bandas de Bollinger y SMA20", template=template, title_font_color=title_color)
    graphs["Candlestick"] = fig_candlestick

    # RSI
    fig_rsi = go.Figure([go.Scatter(x=df.index, y=df['RSI'], name="RSI", connectgaps=False, line=dict(color='orange'))])
    fig_rsi.update_layout(title_text="RSI", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_rsi.add_hline(y=RSI_OVERSOLD, line_dash="dot", line_color="#66BB6A", annotation_text="Sobreventa")
    fig_rsi.add_hline(y=RSI_OVERBOUGHT, line_dash="dot", line_color="#EF5350", annotation_text="Sobrecompra")
    graphs["RSI"] = fig_rsi

    # MACD
    fig_macd = go.Figure([
        go.Scatter(x=df.index, y=df['MACD'], name="MACD", connectgaps=False, line=dict(color='#42A5F5')),
        go.Scatter(x=df.index, y=df['Signal'], name="Señal", connectgaps=False, line=dict(color='#EF5350')),
        go.Bar(x=df.index, y=df['MACD_hist'], name="Histograma", marker_color='grey')
    ])
    fig_macd.update_layout(title_text="MACD", template=template, title_font_color=title_color)
    graphs["MACD"] = fig_macd

    # ADX
    fig_adx = go.Figure([go.Scatter(x=df.index, y=df['ADX'], name="ADX", connectgaps=False, line=dict(color='purple'))])
    fig_adx.update_layout(title_text="ADX", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_adx.add_hline(y=ADX_TREND_THRESHOLD, line_dash="dot", line_color="grey", annotation_text="Tendencia")
    graphs["ADX"] = fig_adx

    # Estocástico
    fig_stoch = go.Figure([
        go.Scatter(x=df.index, y=df['Stoch_K'], name="%K", connectgaps=False, line=dict(color='#42A5F5')),
        go.Scatter(x=df.index, y=df['Stoch_D'], name="%D", connectgaps=False, line=dict(color='#EF5350'))
    ])
    fig_stoch.update_layout(title_text="Estocástico", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_stoch.add_hline(y=STOCH_OVERSOLD, line_dash="dot", line_color="#66BB6A", annotation_text="Sobreventa")
    fig_stoch.add_hline(y=STOCH_OVERBOUGHT, line_dash="dot", line_color="#EF5350", annotation_text="Sobrecompra")
    graphs["Estocástico"] = fig_stoch

    # Volumen
    fig_vol = go.Figure([go.Bar(x=df.index, y=df['Volume'], name="Volumen", marker_color='#42A5F5')])
    fig_vol.update_layout(title_text="Volumen", template=template, title_font_color=title_color)
    graphs["Volumen"] = fig_vol

    for fig in graphs.values():
        fig.update_layout(xaxis_rangeslider_visible=False, xaxis=dict(rangebreaks=rangebreaks))
        unique_days = df.index.normalize().unique()
        daily_lines = [
            go.layout.Shape(type="line", x0=pd.Timestamp(day), x1=pd.Timestamp(day), y0=0, y1=1,
                            yref="paper", line=dict(width=1, dash="dash", color="rgba(128, 128, 128, 0.5)"))
            for day in unique_days if day != unique_days.max()
        ]
        fig.update_layout(shapes=daily_lines)
    return graphs

def get_or_update_data(ticker: str, period: str = "5d", interval: str = "15m", template: str = 'plotly_dark') -> Tuple[Optional[str], Optional[str], Optional[pd.DataFrame], Optional[Dict[str, go.Figure]], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Obtiene o actualiza los datos del ticker, incluyendo indicadores y gráficos, usando un caché.
    """
    global data_cache

    cache_key = f"{ticker}_{period}_{interval}"
    now = datetime.now()

    if cache_key in data_cache and (now - data_cache[cache_key]['timestamp']).total_seconds() < CACHE_TIMEOUT:
        cached_data = data_cache[cache_key]['data']
        return cached_data['recommendation'], cached_data['analyst'], cached_data['df'], cached_data['graphs'], cached_data['market_info'], cached_data['long_name'], None

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period=period, interval=interval)
        long_name = info.get("longName", ticker)
    except yfinance.exceptions.YFPricesError:
        return None, None, None, None, None, None, f"Error: Ticker '{ticker}' no encontrado o no tiene datos disponibles."
    except ConnectionError:
        return None, None, None, None, None, None, f"Error de conexión: No se pudo conectar a los servidores de datos."
    except Exception as e:
        return None, None, None, None, None, None, f"Error inesperado: {e}"

    if hist.empty or "Close" not in hist.columns:
        return None, None, None, None, None, long_name, "No hay datos de precio para este ticker."

    hist = hist[hist['Volume'] > 0]
    df = calculate_indicators(hist.copy())

    # Lógica de puntuación y recomendación
    buy_score = 0.0
    sell_score = 0.0

    if not df.empty and df['Close'].iloc[-1] < df['Lower'].iloc[-1]:
        buy_score += COEF_BOLLINGER
    if not df.empty and df['Close'].iloc[-1] > df['Upper'].iloc[-1]:
        sell_score += COEF_BOLLINGER
    if not df.empty and df['RSI'].iloc[-1] < RSI_OVERSOLD:
        buy_score += COEF_RSI
    elif not df.empty and df['RSI'].iloc[-1] > RSI_OVERBOUGHT:
        sell_score += COEF_RSI
    if not df.empty and len(df) >= 2:
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] and df['MACD'].iloc[-2] <= df['Signal'].iloc[-2]:
            buy_score += COEF_MACD
        elif df['MACD'].iloc[-1] < df['Signal'].iloc[-1] and df['MACD'].iloc[-2] >= df['Signal'].iloc[-2]:
            sell_score += COEF_MACD
    if not df.empty and df['Stoch_K'].iloc[-1] < STOCH_OVERSOLD and df['Stoch_D'].iloc[-1] < STOCH_OVERSOLD:
        buy_score += COEF_STOCH
    elif not df.empty and df['Stoch_K'].iloc[-1] > STOCH_OVERBOUGHT and df['Stoch_D'].iloc[-1] > STOCH_OVERBOUGHT:
        sell_score += COEF_STOCH
    if not df.empty and df['ADX'].iloc[-1] > ADX_TREND_THRESHOLD:
        if df['Close'].iloc[-1] > df['SMA20'].iloc[-1]:
            buy_score += COEF_ADX_SMA
        else:
            sell_score += COEF_ADX_SMA
    if not df.empty and len(df) >= 2 and not df['Volume_SMA'].iloc[-1] == 0:
        if df['Volume'].iloc[-1] > (VOLUME_SMA_MULTIPLIER * df['Volume_SMA'].iloc[-1]):
            if df['Close'].iloc[-1] > df['Close'].iloc[-2]:
                buy_score += COEF_VOLUME
            elif df['Close'].iloc[-1] < df['Close'].iloc[-2]:
                sell_score += COEF_VOLUME

    if buy_score > sell_score + BUY_SELL_THRESHOLD:
        recommendation = BUY_SIGNAL
    elif sell_score > buy_score + BUY_SELL_THRESHOLD:
        recommendation = SELL_SIGNAL
    elif buy_score > 0.0 or sell_score > 0.0:
        recommendation = OBSERVE_SIGNAL
    else:
        recommendation = HOLD_SIGNAL

    analyst_rec = info.get("recommendationKey", "No disponible").capitalize()
    
    market_info = {}
    market_state = info.get('marketState', 'CLOSED')
    if market_state in ['REGULAR']:
        market_info['status'] = "Abierto"
        market_info['current_price'] = df['Close'].iloc[-1]
    else:
        market_info['status'] = "Cerrado"
        market_info['current_price'] = None

    graphs = generate_graphs(df, template)

    data_cache[cache_key] = {
        'timestamp': now,
        'data': {
            'recommendation': recommendation,
            'analyst': analyst_rec,
            'df': df,
            'graphs': graphs,
            'market_info': market_info,
            'long_name': long_name
        }
    }

    return recommendation, analyst_rec, df, graphs, market_info, long_name, None