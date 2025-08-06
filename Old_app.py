import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import ta
import dash_bootstrap_components as dbc
from datetime import datetime, time, timedelta
import json
import os
import yfinance.exceptions
from typing import Dict, Any, List, Optional, Tuple, Union

# --------------------- ENVIRONMENT VARIABLES ---------------------
FILE_PATH = os.environ.get('PORTFOLIO_DATA_PATH', 'portfolio_data.json')

# --------------------- GLOBAL VARIABLES ---------------------
initial_portfolio_state: Dict[str, Any] = {
    "cash": 100000.0,
    "stocks": {},
    "initial_cash": 100000.0,
    "closed_trades": []
}

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80
ADX_TREND_THRESHOLD = 25
VOLUME_SMA_MULTIPLIER = 1.5

BUY_SIGNAL = "📈 Comprar"
SELL_SIGNAL = "📉 Vender"
OBSERVE_SIGNAL = "👁 Observar"
HOLD_SIGNAL = "🤝 Mantener"

popular_tickers: List[str] = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'BRK-B', 'JPM', 'JNJ',
    'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'NKE'
]

data_cache: Dict[str, Any] = {}
CACHE_TIMEOUT = 300

GRAPH_DESCRIPTIONS = {
    "Candlestick": "Este es un gráfico de velas (candlestick) y de línea de precio que muestra el precio de apertura, cierre, máximo y mínimo del activo en cada intervalo de tiempo. Las velas verdes indican un cierre superior a la apertura, y las rojas, un cierre inferior. Las Bandas de Bollinger consisten en una media móvil simple (SMA20) y dos bandas de desviación estándar por encima y por debajo. Se utilizan para medir la volatilidad, donde los precios que tocan las bandas sugieren un activo sobrecomprado o sobrevendido. La SMA20 (Media Móvil Simple de 20 periodos) suaviza los datos de precios para identificar la dirección de la tendencia a corto plazo.",
    "RSI": "El Índice de Fuerza Relativa (RSI) es un oscilador de momentum que mide la velocidad y el cambio de los movimientos de precios. Valores por debajo de 30 sugieren que el activo está sobrevendido (potencial de compra), y valores por encima de 70, que está sobrecomprado (potencial de venta).",
    "MACD": "La Convergencia/Divergencia de la Media Móvil (MACD) se usa para identificar cambios en la dirección de la tendencia. Un cruce de la línea MACD sobre la línea de señal puede ser una señal de compra, y un cruce por debajo, una señal de venta. El histograma muestra la distancia entre ambas líneas.",
    "ADX": "El Índice Direccional Promedio (ADX) mide la fuerza de la tendencia. Un valor por encima de 25 indica una tendencia fuerte. El ADX no indica la dirección de la tendencia, solo su fuerza. Se suele usar junto con otros indicadores.",
    "Estocástico": "El oscilador estocástico es un indicador de momentum que compara el precio de cierre de un activo con su rango de precios durante un período de tiempo determinado. Valores por debajo de 20 se consideran sobrevendidos, y por encima de 80, sobrecomprados.",
    "Volumen": "El gráfico de volumen muestra la cantidad de acciones negociadas en cada intervalo. Un alto volumen durante un movimiento de precio fuerte puede confirmar la tendencia. Las barras azules indican que el volumen es alto."
}

# --------------------- AUXILIARY FUNCTIONS ---------------------
def load_portfolio() -> Dict[str, Any]:
    """
    Carga el estado del portfolio desde un archivo JSON.
    Si el archivo no existe o es inválido, devuelve el estado inicial.

    Returns:
        Dict[str, Any]: El diccionario con el estado del portfolio.
    """
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, 'r') as f:
                data = json.load(f)
                if not all(key in data for key in ["cash", "stocks", "initial_cash", "closed_trades"]):
                    print("Advertencia: El archivo portfolio_data.json tiene un formato antiguo o inválido. Se usará el estado inicial.")
                    return initial_portfolio_state
                return data
        except json.JSONDecodeError:
            print("Error al decodificar JSON desde portfolio_data.json. Se usará el estado inicial.")
            return initial_portfolio_state
    return initial_portfolio_state

def save_portfolio(data: Dict[str, Any]) -> None:
    """
    Guarda el estado del portfolio en un archivo JSON.

    Args:
        data (Dict[str, Any]): El diccionario con el estado del portfolio a guardar.
    """
    with open(FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def get_market_rangebreaks() -> List[Dict[str, Union[str, float]]]:
    """
    Define los rangos de tiempo a omitir en los gráficos (fines de semana y horas de cierre).

    Returns:
        List[Dict[str, Union[str, float]]]: Lista de diccionarios con los rangos de tiempo.
    """
    return [
        dict(bounds=["sat", "mon"]),
        dict(bounds=[16, 9.5], pattern="hour")
    ]

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula varios indicadores técnicos usando la librería 'ta' y los añade al DataFrame.

    Args:
        df (pd.DataFrame): DataFrame con los datos de precios (Open, High, Low, Close, Volume).

    Returns:
        pd.DataFrame: El DataFrame con las columnas de los indicadores añadidas.
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

    Args:
        df (pd.DataFrame): DataFrame con los datos de precios e indicadores.
        template (str): Plantilla de Plotly para los gráficos.
        title_color (str): Color del texto del título.

    Returns:
        Dict[str, go.Figure]: Un diccionario con los objetos de gráfico.
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

def _buy_stock(ticker: str, quantity: int, price: float) -> Tuple[str, str]:
    """
    Función modular para comprar acciones.
    
    Args:
        ticker (str): El símbolo del activo.
        quantity (int): La cantidad de acciones a comprar.
        price (float): El precio actual de la acción.
    
    Returns:
        Tuple[str, str]: Un par de tuplas con el mensaje de notificación y su color.
    """
    global portfolio
    costo_total = quantity * price
    if portfolio["cash"] >= costo_total:
        if ticker not in portfolio["stocks"]:
            portfolio["stocks"][ticker] = {"qty": quantity, "avg_price": price, "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        else:
            old_qty = portfolio["stocks"][ticker]["qty"]
            old_avg_price = portfolio["stocks"][ticker]["avg_price"]
            new_total_cost = (old_qty * old_avg_price) + (quantity * price)
            new_total_qty = old_qty + quantity
            portfolio["stocks"][ticker]["qty"] = new_total_qty
            portfolio["stocks"][ticker]["avg_price"] = new_total_cost / new_total_qty

        portfolio["cash"] -= costo_total
        save_portfolio(portfolio)
        notification_message = f"✅ Compradas {quantity} acciones de {ticker} a ${price:.2f} cada una."
        return notification_message, "success"
    else:
        notification_message = "❌ Fondos insuficientes para realizar la compra."
        return notification_message, "danger"

def _sell_stock(ticker: str, quantity: int, price: float) -> Tuple[str, str, float]:
    """
    Función modular para vender acciones.

    Args:
        ticker (str): El símbolo del activo.
        quantity (int): La cantidad de acciones a vender.
        price (float): El precio actual de la acción.
    
    Returns:
        Tuple[str, str, float]: Un par de tuplas con el mensaje de notificación, su color y la ganancia/pérdida realizada.
    """
    global portfolio
    if ticker in portfolio["stocks"] and portfolio["stocks"][ticker]["qty"] >= quantity:
        avg_buy_price = portfolio["stocks"][ticker]["avg_price"]
        realized_pnl = (price - avg_buy_price) * quantity

        portfolio["cash"] += quantity * price

        portfolio["closed_trades"].append({
            "Fecha Venta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Ticker": ticker,
            "Cantidad": quantity,
            "Precio Compra Promedio": round(avg_buy_price, 2),
            "Precio Venta": round(price, 2),
            "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
        })

        portfolio["stocks"][ticker]["qty"] -= quantity
        if portfolio["stocks"][ticker]["qty"] == 0:
            del portfolio["stocks"][ticker]

        save_portfolio(portfolio)
        notification_message = f"✅ Vendidas {quantity} acciones de {ticker} a ${price:.2f} cada una."
        return notification_message, "success", realized_pnl
    else:
        notification_message = "❌ No tienes suficientes acciones para vender."
        return notification_message, "danger", 0.0

def evaluate_signals(df: pd.DataFrame) -> str:
    """
    Evalúa señales de compra/venta en base a indicadores técnicos.
    """
    COEF_BOLLINGER = 1.0
    COEF_RSI = 2.0
    COEF_MACD = 2.0
    COEF_STOCH = 2.0
    COEF_ADX_SMA = 1.0
    COEF_VOLUME = 1.0

    buy_score = 0.0
    sell_score = 0.0

    if df['Close'].iloc[-1] < df['Lower'].iloc[-1]:
        buy_score += COEF_BOLLINGER
    elif df['Close'].iloc[-1] > df['Upper'].iloc[-1]:
        sell_score += COEF_BOLLINGER

    rsi = df['RSI'].iloc[-1]
    if rsi < RSI_OVERSOLD:
        buy_score += COEF_RSI
    elif rsi > RSI_OVERBOUGHT:
        sell_score += COEF_RSI

    if len(df) >= 2:
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        if curr['MACD'] > curr['Signal'] and prev['MACD'] <= prev['Signal']:
            buy_score += COEF_MACD
        elif curr['MACD'] < curr['Signal'] and prev['MACD'] >= prev['Signal']:
            sell_score += COEF_MACD

    if curr['Stoch_K'] < STOCH_OVERSOLD and curr['Stoch_D'] < STOCH_OVERSOLD:
        buy_score += COEF_STOCH
    elif curr['Stoch_K'] > STOCH_OVERBOUGHT and curr['Stoch_D'] > STOCH_OVERBOUGHT:
        sell_score += COEF_STOCH

    if curr['ADX'] > ADX_TREND_THRESHOLD:
        if curr['Close'] > curr['SMA20']:
            buy_score += COEF_ADX_SMA
        else:
            sell_score += COEF_ADX_SMA

    if curr['Volume_SMA'] != 0:
        if curr['Volume'] > (VOLUME_SMA_MULTIPLIER * curr['Volume_SMA']):
            if curr['Close'] > prev['Close']:
                buy_score += COEF_VOLUME
            elif curr['Close'] < prev['Close']:
                sell_score += COEF_VOLUME

    if buy_score > sell_score + 1.0:
        return BUY_SIGNAL
    elif sell_score > buy_score + 1.0:
        return SELL_SIGNAL
    elif buy_score > 0.0 or sell_score > 0.0:
        return OBSERVE_SIGNAL
    else:
        return HOLD_SIGNAL

def _get_or_update_data(ticker: str, period: str = "5d", interval: str = "15m", template: str = 'plotly_dark') -> Tuple[Optional[str], Optional[str], Optional[pd.DataFrame], Optional[Dict[str, go.Figure]], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Obtiene o actualiza los datos del ticker, incluyendo indicadores y gráficos, usando un caché.

    Args:
        ticker (str): El símbolo del activo a analizar.
        period (str): El período de tiempo para los datos históricos.
        interval (str): El intervalo de tiempo de los datos.
        template (str): La plantilla de Plotly para los gráficos.

    Returns:
        Tuple[Optional[str], Optional[str], Optional[pd.DataFrame], Optional[Dict[str, go.Figure]], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        Una tupla con la recomendación, la recomendación del analista, el DataFrame, los gráficos, información del mercado, el nombre largo del ticker y un mensaje de error (si lo hay).
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

    recommendation = evaluate_signals(df)

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

# --------------------- DASH APP ---------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.DARKLY])
app.title = "Análisis Técnico y Simulador de Trading"

# Initial portfolio state load
portfolio = load_portfolio()
latest_data: Dict[str, Any] = {"ticker": None, "graphs": {}, "df": pd.DataFrame(), "rec": "", "analyst": "", "market_info": {}, "last_rec_for_notification": None, "last_auto_trade_rec": {}}


app.layout = html.Div(id='main-div', style={'backgroundColor': '#121212'}, children=[
    dbc.Container(id='main-container', fluid=True, className="text-white", children=[
        dbc.Row(id='header-row', className="shadow-sm p-3", style={'backgroundColor': '#1e1e1e', 'borderRadius': '4px'}, children=[
            dbc.Col(width=3, children=[
                html.Div(id='company-name-output', className="mb-1 text-white text-center"),
                dbc.InputGroup(children=[
                    html.Datalist(id='popular-tickers-list', children=[html.Option(value=ticker) for ticker in popular_tickers]),
                    dbc.Input(id="ticker", value="AAPL", type="text", debounce=True, placeholder="Introduce un Ticker", list="popular-tickers-list", autoComplete="on", className="text-white rounded-4", style={'backgroundColor': '#121212'}),
                    dbc.Button("🔄", id="refresh-button", n_clicks=0, className="btn-primary rounded-4")
                ])
            ]),
            dbc.Col([
                dbc.Row(className="g-0", justify="center", children=[
                    dbc.Col(html.Div(id="recomendacion", className="text-center fw-bold fs-4"), width=6),
                    dbc.Col(html.Div(id="analyst-output", className="text-center fs-5 text-white"), width=6),
                ]),
            ], width=5, className="d-flex flex-column justify-content-center"),
            dbc.Col([
                html.Div(id="market-status-info", className="text-center fs-5 text-white"),
                html.Div(id="current-price-info", className="text-center fw-bold fs-4 text-white")
            ], width=4, className="d-flex flex-column justify-content-center align-items-center")
        ]),

        dbc.Tabs(id="tabs", active_tab="tab-candlestick", children=[
            dbc.Tab(label='Precio (Velas y Línea)', tab_id='tab-candlestick', id="tab-candlestick-tooltip"),
            dbc.Tab(label='RSI', tab_id='tab-rsi', id="tab-rsi-tooltip"),
            dbc.Tab(label='MACD', tab_id='tab-macd', id="tab-macd-tooltip"),
            dbc.Tab(label='ADX', tab_id='tab-adx', id="tab-adx-tooltip"),
            dbc.Tab(label='Estocástico', tab_id='tab-stoch', id="tab-stoch-tooltip"),
            dbc.Tab(label='Volumen', tab_id='tab-volume', id="tab-volume-tooltip"),
        ], className="mb-4", style={'border': 'none'}),

        dcc.Loading(
            id="loading-1",
            type="default",
            children=dcc.Graph(id="grafico", config={'displayModeBar': False})
        ),

        dbc.Tooltip(GRAPH_DESCRIPTIONS["Candlestick"], target="tab-candlestick-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["RSI"], target="tab-rsi-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["MACD"], target="tab-macd-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["ADX"], target="tab-adx-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["Estocástico"], target="tab-stoch-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["Volumen"], target="tab-volume-tooltip", placement='top', style={"background-color": "#212529 !important", "color": "white !important"}),

        dbc.Row([
            dbc.Col(
                dbc.Card(id='sim-manual-card', className="mb-4 text-white rounded-4", style={'backgroundColor': '#1e1e1e'}, children=[
                    dbc.CardHeader(html.H4("Simulador Manual", id="sim-manual-title", className="text-center text-white"), className="rounded-4"),
                    dbc.CardBody([
                        dbc.Input(id="cantidad", type="number", placeholder="Cantidad de acciones", min=1, step=1, value=1, className="mb-2 text-white rounded-5", style={'backgroundColor': '#121212'}),
                        dbc.Button("Comprar", id="comprar", n_clicks=0, className="btn-success me-2 rounded-5"),
                        dbc.Button("Vender", id="vender", n_clicks=0, className="btn-danger me-2 rounded-5"),
                        dbc.Button("Resetear Cartera", id="reset", n_clicks=0, className="btn-secondary rounded-5"),
                        html.Div(id="cartera", className="mt-3 text-center fw-bold fs-5")
                    ])
                ]),
                width=6
            ),
            dbc.Col(
                dbc.Card(id='sim-auto-card', className="mb-4 text-white rounded-4", style={'backgroundColor': '#1e1e1e'}, children=[
                    dbc.CardHeader(html.H4("Trading Automático", id="sim-auto-title", className="text-center text-white"), className="rounded-4"),
                    dbc.CardBody([
                        html.Div([
                            dbc.Checklist(
                                options=[{"label": "Activar Compra/Venta Automática", "value": "AUTO_TRADE_ON"}],
                                value=[],
                                id="auto-trade-toggle",
                                inline=True,
                                switch=True,
                                className="mb-2 text-white",
                            ),
                            dbc.Tooltip("Activa o desactiva la compra/venta automática basada en la recomendación del análisis.", target="auto-trade-toggle", placement="right")
                        ], id="auto-trade-toggle-wrapper"),
                        dbc.Input(id="auto-trade-quantity", type="number", placeholder="Cantidad Auto", min=1, step=1, value=1, className="mb-2 text-white rounded-5", style={'backgroundColor': '#121212'}),
                        html.Div(id="auto-trade-status", className="mt-2 text-center text-info")
                    ])
                ]),
                width=6
            )
        ]),

        html.Hr(style={'borderColor': '#1e1e1e'}),
        html.H4("Posiciones Abiertas", className="text-center mb-3 text-white"),
        dash_table.DataTable(
            id="open-positions-table",
            columns=[
                {"name": "Fecha Compra", "id": "Fecha Compra"},
                {"name": "Ticker", "id": "Ticker"},
                {"name": "Cantidad", "id": "Cantidad"},
                {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
                {"name": "Ganancia/Pérdida (No Realizada)", "id": "Ganancia/Pérdida (No Realizada)"}
            ],
            data=[],
            style_table={"overflowX": "auto", "minWidth": "100%", 'backgroundColor': '#1e1e1e', 'border-collapse': 'collapse', 'border-radius': '0.5rem', 'overflow': 'hidden'},
            style_cell={"textAlign": "center", "padding": "8px", 'backgroundColor': '#1e1e1e', 'color': 'white', 'border': '1px solid #1e1e1e'},
            style_header={
                "backgroundColor": "#1e1e1e",
                "fontWeight": "bold",
                "color": "white",
                'border': '1px solid #1e1e1e'
            },
            style_data_conditional=[
                {"if": {"column_id": "Ganancia/Pérdida (No Realizada)", "filter_query": "{Ganancia/Pérdida (No Realizada)} > 0"},
                 "color": "#66BB6A"},
                {"if": {"column_id": "Ganancia/Pérdida (No Realizada)", "filter_query": "{Ganancia/Pérdida (No Realizada)} < 0"},
                 "color": "#EF5350"}
            ]
        ),
        html.Div(id="realized-pnl-message", className="text-center mt-2 fs-5 text-info"),

        html.Hr(style={'borderColor': '#1e1e1e'}),
        html.H4("Historial de Ventas Realizadas", className="text-center mb-3 text-white"),
        dash_table.DataTable(
            id="closed-trades-table",
            columns=[
                {"name": "Fecha Venta", "id": "Fecha Venta"},
                {"name": "Ticker", "id": "Ticker"},
                {"name": "Cantidad", "id": "Cantidad"},
                {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
                {"name": "Precio Venta", "id": "Precio Venta"},
                {"name": "Ganancia/Pérdida Realizada", "id": "Ganancia/Pérdida Realizada"}
            ],
            data=portfolio["closed_trades"],
            style_table={"overflowX": "auto", "minWidth": "100%", 'backgroundColor': '#1e1e1e', 'border-collapse': 'collapse', 'border-radius': '0.5rem', 'overflow': 'hidden'},
            style_cell={"textAlign": "center", "padding": "8px", 'backgroundColor': '#1e1e1e', 'color': 'white', 'border': '1px solid #1e1e1e'},
            style_header={
                "backgroundColor": "#1e1e1e",
                "fontWeight": "bold",
                "color": "white",
                'border': '1'
            },
            style_data_conditional=[
                {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada} > 0"},
                 "color": "#66BB6A"},
                {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada} < 0"},
                 "color": "#EF5350"}
            ]
        ),

        dcc.Interval(id='analysis-update', interval=60000, n_intervals=0),
        dcc.Interval(id='price-update', interval=5000, n_intervals=0),
    ]),

    html.Div(id='notification-container', children=[], style={
        'position': 'fixed',
        'bottom': '10px',
        'right': '10px',
        'width': '350px',
        'z-index': '1000'
    })
])

# --------------------- CALLBACKS ---------------------
# The update_ui_styles callback has been removed as the styles are now hardcoded into the layout.

@app.callback(
    Output("grafico", "figure"),
    Output("recomendacion", "children"),
    Output("recomendacion", "style"),
    Output("analyst-output", "children"),
    Output("analyst-output", "className"),
    Output("market-status-info", "children"),
    Output("current-price-info", "children"),
    Output('notification-container', 'children', allow_duplicate=True),
    Output('company-name-output', 'children'),
    Input("refresh-button", "n_clicks"),
    Input("analysis-update", "n_intervals"),
    Input("tabs", "active_tab"),
    State("ticker", "value"),
    prevent_initial_call='initial_duplicate'
)
def update_analysis_and_graphs(n_clicks: int, n_intervals: int, active_tab: str, ticker: str) -> Tuple[go.Figure, str, Dict[str, str], str, str, str, str, List[dbc.Alert], str]:
    """
    Actualiza los gráficos, la recomendación y la información del mercado del ticker seleccionado.

    Args:
        n_clicks (int): Número de clics en el botón de refresco.
        n_intervals (int): Número de intervalos del temporizador de actualización.
        active_tab (str): ID de la pestaña activa.
        ticker (str): Símbolo del ticker ingresado.

    Returns:
        Tuple[go.Figure, str, Dict[str, str], str, str, str, str, List[dbc.Alert], str]:
        Una tupla con la figura del gráfico, la recomendación, el estilo, el texto del analista, la clase CSS, el estado del mercado, el precio actual, una lista de notificaciones y el nombre de la compañía.
    """
    global latest_data

    ctx = callback_context
    changed_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "initial_load"
    current_ticker_in_input = ticker.strip().upper() if ticker else "AAPL"
    tab_to_graph_name = {
        'tab-candlestick': 'Candlestick', 'tab-rsi': 'RSI', 'tab-macd': 'MACD',
        'tab-adx': 'ADX', 'tab-stoch': 'Estocástico', 'tab-volume': 'Volumen',
    }
    graph_name = tab_to_graph_name.get(active_tab, 'Candlestick')
    notification_list: List[dbc.Alert] = []

    # Use the new helper function to get or update data
    rec, analyst, df, graphs, market_info, long_name, error_message = _get_or_update_data(current_ticker_in_input)

    if error_message:
        return go.Figure(), "Error", {'color': '#EF5350'}, "🔍 Recomendación analista: N/A", "text-center fs-5 text-danger", "", "", [dbc.Alert(error_message, color="danger", dismissable=True)], "N/A"

    if latest_data["rec"] is not None and latest_data["rec"] != rec:
        notification_list.append(dbc.Alert(f"🔔 Nueva recomendación para {current_ticker_in_input}: {rec} (antes: {latest_data['rec']})", color="info", dismissable=True, className="mt-2"))

    latest_data.update({
        "ticker": current_ticker_in_input,
        "graphs": graphs,
        "df": df,
        "rec": rec,
        "analyst": analyst,
        "market_info": market_info,
    })

    fig = graphs.get(graph_name, go.Figure())

    rec_style = {}
    if rec == BUY_SIGNAL:
        rec_style['color'] = '#66BB6A'
    elif rec == SELL_SIGNAL:
        rec_style['color'] = '#EF5350'
    else:
        rec_style['color'] = '#FFA726'

    analyst_text = f"🔍 Recomendación analista: {analyst}"
    analyst_class = "text-center fs-5 text-white"

    market_status_text = f"Mercado: {market_info.get('status', 'N/A')}"

    current_price = market_info.get('current_price')
    current_price_text = f"Precio: ${current_price:.2f}" if current_price is not None else ""

    return fig, rec, rec_style, analyst_text, analyst_class, market_status_text, current_price_text, notification_list, long_name

@app.callback(
    Output("cartera", "children"),
    Output("open-positions-table", "data"),
    Input("price-update", "n_intervals"),
    Input("comprar", "n_clicks"),
    Input("vender", "n_clicks"),
    Input("reset", "n_clicks"),
    Input("auto-trade-toggle", "value"),
    Input("auto-trade-quantity", "value")
)
def update_portfolio_display(n_intervals: int, buy_clicks: int, sell_clicks: int, reset_clicks: int, auto_trade_toggle_value: List[str], auto_trade_quantity: int) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Actualiza la visualización del estado del portfolio y las posiciones abiertas.
    
    Args:
        n_intervals (int): Número de intervalos del temporizador de precios.
        buy_clicks (int): Clics en el botón de compra.
        sell_clicks (int): Clics en el botón de venta.
        reset_clicks (int): Clics en el botón de reset.
        auto_trade_toggle_value (List[str]): Valor del interruptor de trading automático.
        auto_trade_quantity (int): Cantidad de acciones para el trading automático.

    Returns:
        Tuple[str, List[Dict[str, Any]]]: Una tupla con el texto de la cartera y los datos de la tabla de posiciones abiertas.
    """
    global portfolio
    
    if latest_data["df"].empty:
        total_valor = portfolio["cash"]
        cartera_txt = f"💰 Efectivo: ${portfolio['cash']:.2f} | 📦 Acciones: 0 | 💼 Valor total: ${total_valor:.2f} | 📈 Ganancia/Pérdida: 0.00% "
        return cartera_txt, []
        
    now_price = latest_data["df"]["Close"].iloc[-1]
    
    total_valor_acciones = sum(
        (now_price * stock_info['qty'])
        for ticker_, stock_info in portfolio["stocks"].items()
    )
    total_valor = portfolio["cash"] + total_valor_acciones
    
    pnl_percentage = ((total_valor - portfolio["initial_cash"]) / portfolio["initial_cash"]) * 100 if portfolio["initial_cash"] > 0 else 0
    
    open_positions_data = []
    for ticker_held, stock_info in portfolio["stocks"].items():
        unrealized_pnl = (now_price - stock_info["avg_price"]) * stock_info["qty"]
        open_positions_data.append({
            "Fecha Compra": stock_info.get("buy_date", "N/A"),
            "Ticker": ticker_held,
            "Cantidad": stock_info["qty"],
            "Precio Compra Promedio": round(stock_info["avg_price"], 2),
            "Ganancia/Pérdida (No Realizada)": round(unrealized_pnl, 2)
        })

    cartera_txt = f"💰 Efectivo: ${portfolio['cash']:.2f} | 📦 Acciones: {sum(stock_info['qty'] for stock_info in portfolio['stocks'].values())} | 💼 Valor total: ${total_valor:.2f} | 📈 Ganancia/Pérdida: {pnl_percentage:.2f}% "
    
    return cartera_txt, open_positions_data

@app.callback(
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("notification-container", "children", allow_duplicate=True),
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input("comprar", "n_clicks"),
    Input("vender", "n_clicks"),
    State("ticker", "value"),
    State("cantidad", "value"),
    prevent_initial_call=True
)
def handle_manual_trading(buy_clicks: int, sell_clicks: int, ticker: str, cantidad_manual: Optional[int]) -> Tuple[str, List[dbc.Alert], List[Dict[str, Any]]]:
    """
    Maneja las operaciones de trading manual (compra y venta).

    Args:
        buy_clicks (int): Número de clics en el botón de compra.
        sell_clicks (int): Número de clics en el botón de venta.
        ticker (str): Símbolo del ticker.
        cantidad_manual (Optional[int]): Cantidad de acciones para la operación.

    Returns:
        Tuple[str, List[dbc.Alert], List[Dict[str, Any]]]:
        Una tupla con el mensaje de P&L, una lista de notificaciones y los datos de la tabla de trades cerrados.
    """
    global latest_data
    ctx = callback_context
    changed_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if latest_data["df"].empty:
        return "", [dbc.Alert("❌ No se puede operar sin datos del ticker.", color="danger", dismissable=True)], portfolio["closed_trades"]

    current_ticker_in_input = ticker.strip().upper()
    now_price = latest_data["df"]["Close"].iloc[-1]

    if cantidad_manual is None or cantidad_manual <= 0:
        return "", [dbc.Alert("❌ La cantidad debe ser un número positivo.", color="danger", dismissable=True)], portfolio["closed_trades"]

    if changed_id == "comprar":
        notification_message, notification_color = _buy_stock(current_ticker_in_input, cantidad_manual, now_price)
        return "", [dbc.Alert(notification_message, color=notification_color, dismissable=True, className="mt-2")], portfolio["closed_trades"]
    
    elif changed_id == "vender":
        notification_message, notification_color, realized_pnl = _sell_stock(current_ticker_in_input, cantidad_manual, now_price)
        realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Manual de {current_ticker_in_input}: ${realized_pnl:.2f}" if notification_color == "success" else ""
        return realized_pnl_message, [dbc.Alert(notification_message, color=notification_color, dismissable=True, className="mt-2")], portfolio["closed_trades"]
    
    return "", [], portfolio["closed_trades"]

@app.callback(
    Output("notification-container", "children", allow_duplicate=True),
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input("reset", "n_clicks"),
    prevent_initial_call=True
)
def handle_reset_portfolio(n_clicks: int) -> Tuple[List[dbc.Alert], str, List[Dict[str, Any]]]:
    """
    Maneja la lógica de resetear el portfolio.
    
    Args:
        n_clicks (int): Número de clics en el botón de reset.

    Returns:
        Tuple[List[dbc.Alert], str, List[Dict[str, Any]]]:
        Una tupla con una lista de notificaciones, un mensaje de P&L vacío y la tabla de trades cerrados reseteada.
    """
    global portfolio
    if n_clicks > 0:
        portfolio["cash"] = portfolio["initial_cash"]
        portfolio["stocks"] = {}
        portfolio["closed_trades"] = []
        save_portfolio(portfolio)
        return [dbc.Alert("🔄 Cartera reseteada a los valores iniciales.", color="info", dismissable=True, className="mt-2")], "", []
    return dash.no_update, dash.no_update, dash.no_update

@app.callback(
    Output("auto-trade-status", "children"),
    Output("notification-container", "children", allow_duplicate=True),
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input('analysis-update', 'n_intervals'),
    State("ticker", "value"),
    State("auto-trade-toggle", "value"),
    State("auto-trade-quantity", "value"),
    prevent_initial_call=True
)
def handle_auto_trading(n_intervals: int, ticker: str, auto_trade_toggle_value: List[str], auto_trade_quantity: Optional[int]) -> Tuple[str, List[dbc.Alert], str, List[Dict[str, Any]]]:
    """
    Maneja las operaciones de trading automático basadas en la recomendación del análisis.

    Args:
        n_intervals (int): Número de intervalos del temporizador de análisis.
        ticker (str): Símbolo del ticker.
        auto_trade_toggle_value (List[str]): Valor del interruptor de trading automático.
        auto_trade_quantity (Optional[int]): Cantidad de acciones para la operación automática.

    Returns:
        Tuple[str, List[dbc.Alert], str, List[Dict[str, Any]]]:
        Una tupla con el estado del trading automático, una lista de notificaciones, un mensaje de P&L y los datos de la tabla de trades cerrados.
    """
    global portfolio, latest_data

    current_ticker_in_input = ticker.strip().upper() if ticker else "AAPL"

    is_auto_trade_enabled = "AUTO_TRADE_ON" in auto_trade_toggle_value
    auto_trade_qty = int(auto_trade_quantity) if auto_trade_quantity and auto_trade_quantity > 0 else 1

    notification_list: List[dbc.Alert] = []
    auto_trade_status_message = "Automático: Desactivado."
    realized_pnl_message = ""

    if not is_auto_trade_enabled:
        return auto_trade_status_message, [], "", portfolio["closed_trades"]

    auto_trade_status_message = "Automático: Activado."

    if latest_data["df"].empty or latest_data["ticker"] != current_ticker_in_input:
        auto_trade_status_message = f"Automático: Activado. Esperando datos para {current_ticker_in_input}."
        return auto_trade_status_message, [], "", portfolio["closed_trades"]

    rec = latest_data["rec"]
    now_price = latest_data["df"]["Close"].iloc[-1]
    last_auto_rec_for_ticker = latest_data["last_auto_trade_rec"].get(current_ticker_in_input)

    if rec == BUY_SIGNAL:
        if last_auto_rec_for_ticker != BUY_SIGNAL:
            if auto_trade_qty <= 0:
                auto_trade_status_message = "Automático: La cantidad debe ser positiva."
                return auto_trade_status_message, [dbc.Alert("❌ No se puede operar con una cantidad no positiva.", color="danger", dismissable=True)], "", portfolio["closed_trades"]

            notification_message, notification_color = _buy_stock(current_ticker_in_input, auto_trade_qty, now_price)
            if notification_color == "success":
                latest_data["last_auto_trade_rec"][current_ticker_in_input] = BUY_SIGNAL
                notification_list.append(dbc.Alert(f"🤖 {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
            else:
                auto_trade_status_message = f"Automático: {notification_message}"
                notification_list.append(dbc.Alert(f"❌ {notification_message}", color=notification_color, dismissable=True, className="mt-2"))

    elif rec == SELL_SIGNAL:
        if last_auto_rec_for_ticker != SELL_SIGNAL:
            if auto_trade_qty <= 0:
                auto_trade_status_message = "Automático: La cantidad debe ser positiva."
                return auto_trade_status_message, [dbc.Alert("❌ No se puede operar con una cantidad no positiva.", color="danger", dismissable=True)], "", portfolio["closed_trades"]

            notification_message, notification_color, realized_pnl = _sell_stock(current_ticker_in_input, auto_trade_qty, now_price)
            if notification_color == "success":
                realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Automática de {current_ticker_in_input}: ${realized_pnl:.2f}"
                latest_data["last_auto_trade_rec"][current_ticker_in_input] = SELL_SIGNAL
                notification_list.append(dbc.Alert(f"🤖 {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
            else:
                auto_trade_status_message = f"Automático: {notification_message}"
                notification_list.append(dbc.Alert(f"❌ {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
    else:
        latest_data["last_auto_trade_rec"][current_ticker_in_input] = rec
        auto_trade_status_message = f"Automático: {rec} para {current_ticker_in_input}. Esperando señal de compra/venta."

    return auto_trade_status_message, notification_list, realized_pnl_message, portfolio["closed_trades"]

if __name__ == "__main__":
    app.run(debug=True)