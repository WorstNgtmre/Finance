# config.py

import os
from typing import List

# Environment variables
FILE_PATH: str = os.environ.get('PORTFOLIO_DATA_PATH', 'portfolio_data.json')

# Technical indicator thresholds
RSI_OVERSOLD: int = 30
RSI_OVERBOUGHT: int = 70
STOCH_OVERSOLD: int = 20
STOCH_OVERBOUGHT: int = 80
ADX_TREND_THRESHOLD: int = 25
VOLUME_SMA_MULTIPLIER: float = 1.5

# Trading algorithm coefficients
COEF_BOLLINGER = 0.8
COEF_RSI = 2.4
COEF_MACD = 1.55
COEF_STOCH = 2.0
COEF_ADX_SMA = 0.75
COEF_VOLUME = 1.0
BUY_SELL_THRESHOLD = 1.4

# Trading signals
BUY_SIGNAL: str = "📈 Comprar"
SELL_SIGNAL: str = "📉 Vender"
OBSERVE_SIGNAL: str = "👁 Observar"
HOLD_SIGNAL: str = "🤝 Mantener"

# Other constants
CACHE_TIMEOUT: int = 300  # 5 minutes

popular_tickers: List[str] = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'BRK-B', 'JPM', 'JNJ',
    'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'NKE'
]

GRAPH_DESCRIPTIONS = {
    "Candlestick": "Este es un gráfico de velas (candlestick) y de línea de precio que muestra el precio de apertura, cierre, máximo y mínimo del activo en cada intervalo de tiempo. Las velas verdes indican un cierre superior a la apertura, y las rojas, un cierre inferior. Las Bandas de Bollinger consisten en una media móvil simple (SMA20) y dos bandas de desviación estándar por encima y por debajo. Se utilizan para medir la volatilidad, donde los precios que tocan las bandas sugieren un activo sobrecomprado o sobrevendido. La SMA20 (Media Móvil Simple de 20 periodos) suaviza los datos de precios para identificar la dirección de la tendencia a corto plazo.",
    "RSI": "El Índice de Fuerza Relativa (RSI) es un oscilador de momentum que mide la velocidad y el cambio de los movimientos de precios. Valores por debajo de 30 sugieren que el activo está sobrevendido (potencial de compra), y valores por encima de 70, que está sobrecomprado (potencial de venta).",
    "MACD": "La Convergencia/Divergencia de la Media Móvil (MACD) se usa para identificar cambios en la dirección de la tendencia. Un cruce de la línea MACD sobre la línea de señal puede ser una señal de compra, y un cruce por debajo, una señal de venta. El histograma muestra la distancia entre ambas líneas.",
    "ADX": "El Índice Direccional Promedio (ADX) mide la fuerza de la tendencia. Un valor por encima de 25 indica una tendencia fuerte. El ADX no indica la dirección de la tendencia, solo su fuerza. Se suele usar junto con otros indicadores.",
    "Estocástico": "El oscilador estocástico es un indicador de momentum que compara el precio de cierre de un activo con su rango de precios durante un período de tiempo determinado. Valores por debajo de 20 se consideran sobrevendidos, y por encima de 80, sobrecomprados.",
    "Volumen": "El gráfico de volumen muestra la cantidad de acciones negociadas en cada intervalo. Un alto volumen durante un movimiento de precio fuerte puede confirmar la tendencia. Las barras azules indican que el volumen es alto."
}