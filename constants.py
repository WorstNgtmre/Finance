from typing import List

popular_tickers: List[str] = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'BRK-B', 'JPM', 'JNJ',
    'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'NKE'
]

GRAPH_DESCRIPTIONS = {
    "Candlestick": (
        "Este es un gráfico de velas (candlestick) y de línea de precio que muestra el precio de apertura, "
        "cierre, máximo y mínimo del activo en cada intervalo de tiempo. Las velas verdes indican que el precio "
        "cerró más alto que abrió (tendencia alcista), mientras que las velas rojas indican lo contrario (tendencia bajista). "
        "Es útil para identificar patrones de precios, niveles de soporte y resistencia, y señales de reversión."
    ),
    "RSI": (
        "El Índice de Fuerza Relativa (RSI) es un oscilador de momentum que mide la velocidad y el cambio de los movimientos de precio. "
        "Su valor oscila entre 0 y 100. Un RSI por encima de 70 se considera sobrecompra, y por debajo de 30 se considera sobreventa. "
        "Se utiliza para detectar posibles puntos de entrada o salida basados en condiciones extremas del mercado."
    ),
    "MACD": (
        "La Convergencia/Divergencia de la Media Móvil (MACD) es un indicador de seguimiento de tendencia que muestra la relación entre dos medias móviles del precio. "
        "Se compone de la línea MACD, la línea de señal y el histograma. Cuando la línea MACD cruza por encima de la línea de señal, puede indicar una señal de compra, "
        "y cuando cruza por debajo, una señal de venta. También ayuda a identificar cambios en la fuerza, dirección y duración de una tendencia."
    ),
    "ADX": (
        "El Índice Direccional Promedio (ADX) mide la fuerza de una tendencia sin importar su dirección. "
        "Un valor ADX superior a 25 generalmente indica una tendencia fuerte, mientras que un valor inferior sugiere un mercado sin tendencia. "
        "Se utiliza junto con las líneas +DI y -DI para determinar la dirección de la tendencia y su fortaleza relativa."
    ),
    "Estocástico": (
        "El oscilador estocástico es un indicador de momentum que compara el precio de cierre de un activo con su rango de precios durante un período determinado. "
        "Se compone de dos líneas: %K y %D. Valores por encima de 80 indican sobrecompra, y por debajo de 20 indican sobreventa. "
        "Es útil para identificar posibles puntos de reversión en el mercado y condiciones extremas de precio."
    ),
    "Volumen": (
        "El gráfico de volumen muestra la cantidad de activos negociados durante un intervalo de tiempo específico. "
        "Un volumen alto suele confirmar la fuerza de una tendencia, mientras que un volumen bajo puede indicar debilidad o falta de interés. "
        "Se utiliza para validar movimientos de precio y detectar posibles cambios en la dirección del mercado."
    )
}
