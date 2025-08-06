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

# --------------------- VARIABLES GLOBALES ---------------------
# Ruta del archivo donde se guardará el portfolio
FILE_PATH = 'portfolio_data.json'

# Estructura inicial del portfolio
initial_portfolio_state = {
    "cash": 100000.0,
    "stocks": {},  # {ticker: {"qty": X, "avg_price": Y, "buy_date": Z}}
    "initial_cash": 100000.0,
    "closed_trades": [] # [{"Fecha Venta": ..., "Ticker": ..., "Cantidad": ..., "Precio Compra Promedio": ..., "Precio Venta": ..., "Ganancia/Pérdida Realizada": ...}]
}

# Constantes para la lógica de trading y UI
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

# Lista de tickers populares para el datalist
popular_tickers = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'BRK-B', 'JPM', 'JNJ',
    'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'NKE'
]

# Carga el portfolio al inicio del programa o usa el estado inicial
def load_portfolio():
    """Carga el estado del portfolio desde un archivo JSON."""
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, 'r') as f:
                data = json.load(f)
                # Asegurarse de que la estructura cargada sea compatible
                if "cash" not in data or "stocks" not in data or "initial_cash" not in data or "closed_trades" not in data:
                    print("Advertencia: El archivo portfolio_data.json tiene un formato antiguo o inválido. Se usará el estado inicial.")
                    return initial_portfolio_state
                return data
        except json.JSONDecodeError:
            print("Error al decodificar JSON desde portfolio_data.json. Se usará el estado inicial.")
            return initial_portfolio_state
    return initial_portfolio_state

def save_portfolio(data):
    """Guarda el estado del portfolio en un archivo JSON."""
    with open(FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)

portfolio = load_portfolio() # Cargar el portfolio al iniciar la aplicación

# Cache para los datos más recientes del ticker
latest_data = {"ticker": None, "graphs": {}, "df": pd.DataFrame(), "rec": "", "analyst": "", "market_info": {}, "last_rec_for_notification": None, "last_auto_trade_rec": {}}

# Descripciones para los gráficos
GRAPH_DESCRIPTIONS = {
    "Candlestick": "Este es un gráfico de velas (candlestick) y de línea de precio que muestra el precio de apertura, cierre, máximo y mínimo del activo en cada intervalo de tiempo. Las velas verdes indican un cierre superior a la apertura, y las rojas, un cierre inferior. Las Bandas de Bollinger consisten en una media móvil simple (SMA20) y dos bandas de desviación estándar por encima y por debajo. Se utilizan para medir la volatilidad, donde los precios que tocan las bandas sugieren un activo sobrecomprado o sobrevendido. La SMA20 (Media Móvil Simple de 20 periodos) suaviza los datos de precios para identificar la dirección de la tendencia a corto plazo.",
    "RSI": "El Índice de Fuerza Relativa (RSI) es un oscilador de momentum que mide la velocidad y el cambio de los movimientos de precios. Valores por debajo de 30 sugieren que el activo está sobrevendido (potencial de compra), y valores por encima de 70, que está sobrecomprado (potencial de venta).",
    "MACD": "La Convergencia/Divergencia de la Media Móvil (MACD) se usa para identificar cambios en la dirección de la tendencia. Un cruce de la línea MACD sobre la línea de señal puede ser una señal de compra, y un cruce por debajo, una señal de venta. El histograma muestra la distancia entre ambas líneas.",
    "ADX": "El Índice Direccional Promedio (ADX) mide la fuerza de la tendencia. Un valor por encima de 25 indica una tendencia fuerte. El ADX no indica la dirección de la tendencia, solo su fuerza. Se suele usar junto con otros indicadores.",
    "Estocástico": "El oscilador estocástico es un indicador de momentum que compara el precio de cierre de un activo con su rango de precios durante un período de tiempo determinado. Valores por debajo de 20 se consideran sobrevendidos, y por encima de 80, sobrecomprados.",
    "Volumen": "El gráfico de volumen muestra la cantidad de acciones negociadas en cada intervalo. Un alto volumen durante un movimiento de precio fuerte puede confirmar la tendencia. Las barras azules indican que el volumen es alto."
}

# --------------------- FUNCIONES AUXILIARES ---------------------
def get_market_rangebreaks():
    """Define los rangos de tiempo a omitir en los gráficos (fines de semana y horas de cierre)."""
    return [
        dict(bounds=["sat", "mon"]), # Omite fines de semana
        dict(bounds=[16, 9.5], pattern="hour") # Omite horas fuera del horario de mercado (ej. 16:00 a 9:30)
    ]

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

# --------------------- FUNCION PRINCIPAL DE ANALISIS Y RECOMENDACION ---------------------
def analyze_stock(ticker, period="5d", interval="15m", template='plotly_dark'):
    """
    Obtiene datos de un ticker, calcula indicadores, genera gráficos
    y emite una recomendación de trading basada en la lógica.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period=period, interval=interval)
        long_name = info.get("longName", ticker) # Obtener el nombre completo de la empresa
    except (yfinance.exceptions.YFPricesError, ConnectionError, Exception) as e:
        return f"Error: No se pudo obtener datos para el Ticker '{ticker}'. Detalles: {e}", "N/A", pd.DataFrame(), {}, {}, "N/A"
    
    if hist.empty or "Close" not in hist.columns:
        return "No hay datos", "N/A", hist, {}, {}, long_name

    hist = hist[hist['Volume'] > 0]
    
    df = calculate_indicators(hist.copy())

    COEF_BOLLINGER = 1.0
    COEF_RSI = 2.0
    COEF_MACD = 2.0
    COEF_STOCH = 2.0
    COEF_ADX_SMA = 1.0
    COEF_VOLUME = 1.0

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

    if buy_score > sell_score + 1.0: 
        recommendation = BUY_SIGNAL
    elif sell_score > buy_score + 1.0:
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

    rangebreaks = get_market_rangebreaks()
    graphs = {}
    title_color = 'white'

    # Gráfico unificado de Candlestick con Bandas de Bollinger, SMA20 y línea de precio
    fig_candlestick = go.Figure(data=[
        go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Velas', increasing_line_color='#66BB6A', decreasing_line_color='#EF5350'),
        go.Scatter(x=df.index, y=df['Close'], name="Precio", connectgaps=False, line=dict(color='#42A5F5', width=1)),
        go.Scatter(x=df.index, y=df['Upper'], name="Banda Sup", connectgaps=False, line=dict(dash='dot', color='#EF5350')),
        go.Scatter(x=df.index, y=df['Lower'], name="Banda Inf", connectgaps=False, line=dict(dash='dot', color='#66BB6A')),
        go.Scatter(x=df.index, y=df['SMA20'], name="SMA20", connectgaps=False, line=dict(dash='dash', color='purple'))
    ])
    fig_candlestick.update_layout(title_text="Precio (Candlestick y Línea) con Bandas de Bollinger y SMA20", template=template, title_font_color=title_color)
    graphs["Candlestick"] = fig_candlestick

    # Gráfico de RSI
    fig_rsi = go.Figure([
        go.Scatter(x=df.index, y=df['RSI'], name="RSI", connectgaps=False, line=dict(color='orange'))
    ])
    fig_rsi.update_layout(title_text="RSI", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_rsi.add_hline(y=RSI_OVERSOLD, line_dash="dot", line_color="#66BB6A", annotation_text="Sobreventa")
    fig_rsi.add_hline(y=RSI_OVERBOUGHT, line_dash="dot", line_color="#EF5350", annotation_text="Sobrecompra")
    graphs["RSI"] = fig_rsi

    # Gráfico de MACD
    fig_macd = go.Figure([
        go.Scatter(x=df.index, y=df['MACD'], name="MACD", connectgaps=False, line=dict(color='#42A5F5')),
        go.Scatter(x=df.index, y=df['Signal'], name="Señal", connectgaps=False, line=dict(color='#EF5350')),
        go.Bar(x=df.index, y=df['MACD_hist'], name="Histograma", marker_color='grey')
    ])
    fig_macd.update_layout(title_text="MACD", template=template, title_font_color=title_color)
    graphs["MACD"] = fig_macd

    # Gráfico de ADX
    fig_adx = go.Figure([
        go.Scatter(x=df.index, y=df['ADX'], name="ADX", connectgaps=False, line=dict(color='purple'))
    ])
    fig_adx.update_layout(title_text="ADX", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_adx.add_hline(y=ADX_TREND_THRESHOLD, line_dash="dot", line_color="grey", annotation_text="Tendencia")
    graphs["ADX"] = fig_adx

    # Gráfico de Estocástico
    fig_stoch = go.Figure([
        go.Scatter(x=df.index, y=df['Stoch_K'], name="%K", connectgaps=False, line=dict(color='#42A5F5')),
        go.Scatter(x=df.index, y=df['Stoch_D'], name="%D", connectgaps=False, line=dict(color='#EF5350'))
    ])
    fig_stoch.update_layout(title_text="Estocástico", yaxis=dict(range=[0,100]), template=template, title_font_color=title_color)
    fig_stoch.add_hline(y=STOCH_OVERSOLD, line_dash="dot", line_color="#66BB6A", annotation_text="Sobreventa")
    fig_stoch.add_hline(y=STOCH_OVERBOUGHT, line_dash="dot", line_color="#EF5350", annotation_text="Sobrecompra")
    graphs["Estocástico"] = fig_stoch

    # Gráfico de Volumen
    fig_vol = go.Figure([
        go.Bar(x=df.index, y=df['Volume'], name="Volumen", marker_color='#42A5F5')
    ])
    fig_vol.update_layout(title_text="Volumen", template=template, title_font_color=title_color)
    graphs["Volumen"] = fig_vol

    # Actualizar todos los gráficos para que muestren el rango completo de datos
    for fig in graphs.values():
        fig.update_layout(xaxis_rangeslider_visible=False, xaxis=dict(rangebreaks=get_market_rangebreaks()))
        unique_days = df.index.normalize().unique()
        daily_lines = [
            go.layout.Shape(type="line", x0=pd.Timestamp(day), x1=pd.Timestamp(day), y0=0, y1=1,
                            yref="paper", line=dict(width=1, dash="dash", color="rgba(128, 128, 128, 0.5)"))
            for day in unique_days if day != unique_days.max()
        ]
        fig.update_layout(shapes=daily_lines)
    
    return recommendation, analyst_rec, df, graphs, market_info, long_name

# --------------------- DASH APP ---------------------

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.DARKLY])
app.title = "Análisis Técnico y Simulador de Trading"

app.layout = html.Div(id='main-div', style={'backgroundColor': '#121212'}, children=[
    dbc.Container(id='main-container', fluid=True, className="text-white", children=[ # Removed marginTop
        dbc.Row(id='header-row', className="shadow-sm p-3", style={'backgroundColor': '#1e1e1e', 'borderRadius': '4px'}, children=[ # Changed background color and added border-radius
            dbc.Col(width=3, children=[
                html.Div(id='company-name-output', className="mb-1 text-white text-center"),
                dbc.InputGroup(children=[
                    html.Datalist(id='popular-tickers-list', children=[html.Option(value=ticker) for ticker in popular_tickers]),
                    dbc.Input(id="ticker", value="AAPL", type="text", debounce=True, placeholder="Introduce un Ticker", className="text-white rounded-4", style={'backgroundColor': '#121212'}),
                    dbc.Button("🔄", id="refresh-button", n_clicks=0, className="btn-primary rounded-4")
                ])
            ]),
            dbc.Col([
                dbc.Row(className="g-0", justify="center", children=[ 
                    dbc.Col(html.Div(id="recomendacion", className="text-center fw-bold fs-4"), width=6),
                    dbc.Col(html.Div(id="analyst-output", className="text-center fs-5 text-white"), width=6),
                ]),
                html.Div(id='notification', className='text-center fs-5') # text-warning removed
            ], width=5, className="d-flex flex-column justify-content-center"),
            dbc.Col([
                html.Div(id="market-status-info", className="text-center fs-5 text-white"),
                html.Div(id="current-price-info", className="text-center fw-bold fs-4 text-white")
            ], width=4, className="d-flex flex-column justify-content-center align-items-center")
        ]),

        dbc.Tabs(id="tabs", active_tab="tab-candlestick", children=[
            dbc.Tab(label='Precio (Velas y Línea)', tab_id='tab-candlestick'),
            dbc.Tab(label='RSI', tab_id='tab-rsi'),
            dbc.Tab(label='MACD', tab_id='tab-macd'),
            dbc.Tab(label='ADX', tab_id='tab-adx'),
            dbc.Tab(label='Estocástico', tab_id='tab-stoch'),
            dbc.Tab(label='Volumen', tab_id='tab-volume'),
        ], className="mb-4", style={'border': 'none'}), # Changed to 'border': 'none'
        html.P(id="graph-description", className="text-white text-center"),
        dcc.Graph(id="grafico", config={'displayModeBar': False}),

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

        html.Hr(style={'borderColor': '#1e1e1e'}), # Changed color to blend with card/table background
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
                 "color": "#66BB6A"}, # Suavizado de green
                {"if": {"column_id": "Ganancia/Pérdida (No Realizada)", "filter_query": "{Ganancia/Pérdida (No Realizada)} < 0"},
                 "color": "#EF5350"} # Suavizado de red
            ]
        ),
        html.Div(id="realized-pnl-message", className="text-center mt-2 fs-5 text-info"),

        html.Hr(style={'borderColor': '#1e1e1e'}), # Changed color to blend with card/table background
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
                {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada)} > 0"},
                 "color": "#66BB6A"}, # Suavizado de green
                {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada)} < 0"},
                 "color": "#EF5350"} # Suavizado de red
            ]
        ),

        dcc.Interval(id='analysis-update', interval=60000, n_intervals=0), # Actualiza análisis cada minuto
        dcc.Interval(id='price-update', interval=5000, n_intervals=0), # Actualiza precio cada 5 segundos
    ])
])

# --------------------- CALLBACKS ---------------------

# Callback para actualizar los estilos de los componentes (ahora solo para modo oscuro)
@app.callback(
    Output('header-row', 'className'),
    Output('header-row', 'style'), # Added style output for header-row
    Output('open-positions-table', 'style_header'),
    Output('closed-trades-table', 'style_header'),
    Output('sim-manual-card', 'className'),
    Output('sim-auto-card', 'className'),
    Output('sim-manual-card', 'style'), 
    Output('sim-auto-card', 'style'),
    Output('sim-manual-title', 'className'),
    Output('sim-auto-title', 'className'),
    Input('analysis-update', 'n_intervals'), # Usamos un input dummy para que se dispare al inicio
)
def update_ui_styles(n_intervals):
    # La clase 'fixed-top' y 'bg-dark' ya están en la definición del layout.
    # Esta función ahora solo actualiza los estilos de los otros componentes.
    header_class = "shadow-sm p-3" # Removed fixed-top
    header_style = {'backgroundColor': '#1e1e1e', 'borderRadius': '4px'} # Changed background color and added border-radius

    header_table_style = {
        "backgroundColor": "#1e1e1e",
        "fontWeight": "bold",
        "color": "white",
        'border': '1px solid #1e1e1e'
    }
    
    card_class = "mb-4 text-white rounded-4" 
    card_style = {'backgroundColor': '#1e1e1e'} 
    title_class = "text-center text-white"
    
    return header_class, header_style, header_table_style, header_table_style, card_class, card_class, card_style, card_style, title_class, title_class


# Callback para la actualización de análisis completo (gráficos, recomendación, descripción)
@app.callback(
    Output("grafico", "figure"),
    Output("recomendacion", "children"),
    Output("recomendacion", "style"), # Changed from className to style
    Output("analyst-output", "children"),
    Output("analyst-output", "className"),
    Output("market-status-info", "children"),
    Output("current-price-info", "children"),
    Output('notification', 'children'),
    Output('notification', 'style'), # Added style output for notification
    Output('graph-description', 'children'),
    Output('graph-description', 'className'),
    Output('company-name-output', 'children'), # Nuevo Output
    Input("refresh-button", "n_clicks"),
    Input("analysis-update", "n_intervals"),
    Input("tabs", "active_tab"),
    State("ticker", "value")
)
def update_analysis_and_graphs(n_clicks, n_intervals, active_tab, ticker):
    global latest_data
    
    ctx = callback_context
    changed_id = ctx.triggered[0]["prop_id"].split(".")[0]

    current_ticker_in_input = ticker.strip().upper()
    
    # Mapeo de `tab_id` a nombre de gráfico
    tab_to_graph_name = {
        'tab-candlestick': 'Candlestick',
        'tab-rsi': 'RSI',
        'tab-macd': 'MACD',
        'tab-adx': 'ADX',
        'tab-stoch': 'Estocástico',
        'tab-volume': 'Volumen',
    }
    graph_name = tab_to_graph_name.get(active_tab, 'Candlestick')

    if changed_id in ["refresh-button", "analysis-update"] or latest_data["ticker"] != current_ticker_in_input:
        rec, analyst, df, graphs, market_info, long_name = analyze_stock(current_ticker_in_input)
        
        if rec.startswith("Error:"):
            return go.Figure(), rec, {'color': '#EF5350'}, f"🔍 Recomendación analista: N/A", "text-center fs-5 text-danger", "", "", "", {'color': '#FFA726'}, "", "N/A"

        latest_data.update({
            "ticker": current_ticker_in_input,
            "graphs": graphs,
            "df": df,
            "rec": rec,
            "analyst": analyst,
            "market_info": market_info,
            "last_rec_for_notification": rec
        })
    else:
        rec = latest_data["rec"]
        analyst = latest_data["analyst"]
        graphs = latest_data["graphs"]
        df = latest_data["df"]
        market_info = latest_data["market_info"]
        long_name = yf.Ticker(current_ticker_in_input).info.get("longName", current_ticker_in_input)

    notification_message = ""
    notification_style = {'color': '#FFA726'} # Default warning color
    if changed_id == "analysis-update" and \
       latest_data["last_rec_for_notification"] is not None and \
       latest_data["last_rec_for_notification"] != rec:
        notification_message = f"🔔 Nueva recomendación para {current_ticker_in_input}: {rec} (antes: {latest_data['last_rec_for_notification']})"
    latest_data["last_rec_for_notification"] = rec

    fig = graphs.get(graph_name, go.Figure())
    description = GRAPH_DESCRIPTIONS.get(graph_name, "")
    description_class = "text-white text-center"
    
    rec_style = {} # Initialize style dictionary
    if rec == BUY_SIGNAL:
        rec_style['color'] = '#66BB6A' # Softer green
    elif rec == SELL_SIGNAL:
        rec_style['color'] = '#EF5350' # Softer red
    else:
        rec_style['color'] = '#FFA726' # Softer orange for warning/observe
    
    analyst_text = f"🔍 Recomendación analista: {analyst}"
    analyst_class = "text-center fs-5 text-white"

    market_status_text = f"Mercado: {market_info.get('status', 'N/A')}"
    
    current_price = market_info.get('current_price')
    current_price_text = f"Precio: ${current_price:.2f}" if current_price is not None else ""
        
    return fig, rec, rec_style, analyst_text, analyst_class, market_status_text, current_price_text, notification_message, notification_style, description, description_class, long_name

# Callback para la actualización de precios y cartera (más frecuente)
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
def update_portfolio(n_intervals, buy_clicks, sell_clicks, reset_clicks, auto_trade_toggle_value, auto_trade_quantity):
    global portfolio, latest_data
    
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

# Callback para operaciones manuales
@app.callback(
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "style", allow_duplicate=True), # Added style output for notification
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input("comprar", "n_clicks"),
    Input("vender", "n_clicks"),
    State("ticker", "value"),
    State("cantidad", "value"),
    prevent_initial_call=True
)
def handle_manual_trading(buy_clicks, sell_clicks, ticker, cantidad_manual):
    global portfolio
    ctx = callback_context
    changed_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    notification_style = {'color': '#FFA726'} # Default warning color

    if latest_data["df"].empty:
        return "", "❌ No se puede operar sin datos del ticker.", notification_style, portfolio["closed_trades"]
    
    current_ticker_in_input = ticker.strip().upper()
    now_price = latest_data["df"]["Close"].iloc[-1]
    
    notification_message = ""
    realized_pnl_message = ""

    if changed_id == "comprar" and cantidad_manual:
        costo_total = cantidad_manual * now_price
        if portfolio["cash"] >= costo_total:
            if current_ticker_in_input not in portfolio["stocks"]:
                portfolio["stocks"][current_ticker_in_input] = {"qty": cantidad_manual, "avg_price": now_price, "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            else:
                old_qty = portfolio["stocks"][current_ticker_in_input]["qty"]
                old_avg_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
                new_total_cost = (old_qty * old_avg_price) + (cantidad_manual * now_price)
                new_total_qty = old_qty + cantidad_manual
                portfolio["stocks"][current_ticker_in_input]["qty"] = new_total_qty
                portfolio["stocks"][current_ticker_in_input]["avg_price"] = new_total_cost / new_total_qty
            
            portfolio["cash"] -= costo_total
            notification_message = f"✅ Compradas {cantidad_manual} acciones de {current_ticker_in_input} a ${now_price:.2f} cada una."
            notification_style = {'color': '#66BB6A'} # Softer green for success
            save_portfolio(portfolio)
        else:
            notification_message = "❌ Fondos insuficientes para realizar la compra."
            notification_style = {'color': '#EF5350'} # Softer red for error
            
    elif changed_id == "vender" and cantidad_manual:
        if current_ticker_in_input in portfolio["stocks"] and portfolio["stocks"][current_ticker_in_input]["qty"] >= cantidad_manual:
            avg_buy_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
            realized_pnl = (now_price - avg_buy_price) * cantidad_manual
            realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Manual de {current_ticker_in_input}: ${realized_pnl:.2f}"

            portfolio["cash"] += cantidad_manual * now_price
            
            portfolio["closed_trades"].append({
                "Fecha Venta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": current_ticker_in_input,
                "Cantidad": cantidad_manual,
                "Precio Compra Promedio": round(avg_buy_price, 2),
                "Precio Venta": round(now_price, 2),
                "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
            })

            portfolio["stocks"][current_ticker_in_input]["qty"] -= cantidad_manual
            if portfolio["stocks"][current_ticker_in_input]["qty"] == 0:
                del portfolio["stocks"][current_ticker_in_input]
            
            notification_message = f"✅ Vendidas {cantidad_manual} acciones de {current_ticker_in_input} a ${now_price:.2f} cada una."
            notification_style = {'color': '#66BB6A'} # Softer green for success
            latest_data["last_auto_trade_rec"][current_ticker_in_input] = SELL_SIGNAL
            save_portfolio(portfolio)
        else:
            notification_message = "❌ No tienes suficientes acciones para vender."
            notification_style = {'color': '#EF5350'} # Softer red for error
    
    return realized_pnl_message, notification_message, notification_style, portfolio["closed_trades"]

# Callback para el botón de reset
@app.callback(
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "style", allow_duplicate=True), # Added style output for notification
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input("reset", "n_clicks"),
    prevent_initial_call=True
)
def handle_reset_portfolio(n_clicks):
    global portfolio
    notification_style = {'color': '#FFA726'} # Default warning color
    if n_clicks > 0:
        portfolio["cash"] = portfolio["initial_cash"]
        portfolio["stocks"] = {}
        portfolio["closed_trades"] = []
        save_portfolio(portfolio)
        notification_style = {'color': '#42A5F5'} # Softer blue for info/reset
        return "🔄 Cartera reseteada a los valores iniciales.", notification_style, "", []
    return "", notification_style, "", portfolio["closed_trades"]

# Callback para la lógica de trading automática
@app.callback(
    Output("auto-trade-status", "children"),
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "style", allow_duplicate=True), # Added style output for notification
    Output("realized-pnl-message", "children", allow_duplicate=True),
    Output("closed-trades-table", "data", allow_duplicate=True),
    Input('analysis-update', 'n_intervals'),
    State("ticker", "value"),
    State("auto-trade-toggle", "value"),
    State("auto-trade-quantity", "value"),
    prevent_initial_call=True
)
def handle_auto_trading(n_intervals, ticker, auto_trade_toggle_value, auto_trade_quantity):
    global portfolio, latest_data

    current_ticker_in_input = ticker.strip().upper()
    
    is_auto_trade_enabled = "AUTO_TRADE_ON" in auto_trade_toggle_value
    auto_trade_qty = int(auto_trade_quantity) if auto_trade_quantity and auto_trade_quantity > 0 else 1

    notification_message = ""
    auto_trade_status_message = "Automático: Desactivado."
    realized_pnl_message = ""
    notification_style = {'color': '#FFA726'} # Default warning color

    if not is_auto_trade_enabled:
        return auto_trade_status_message, notification_message, notification_style, realized_pnl_message, portfolio["closed_trades"]

    if latest_data["df"].empty or latest_data["ticker"] != current_ticker_in_input:
        auto_trade_status_message = f"Automático: Activado. Esperando datos para {current_ticker_in_input}."
        return auto_trade_status_message, notification_message, notification_style, realized_pnl_message, portfolio["closed_trades"]

    rec = latest_data["rec"]
    now_price = latest_data["df"]["Close"].iloc[-1]
    last_auto_rec_for_ticker = latest_data["last_auto_trade_rec"].get(current_ticker_in_input)

    if rec == BUY_SIGNAL:
        if last_auto_rec_for_ticker != BUY_SIGNAL:
            costo_total_auto = auto_trade_qty * now_price
            if portfolio["cash"] >= costo_total_auto:
                if current_ticker_in_input not in portfolio["stocks"]:
                    portfolio["stocks"][current_ticker_in_input] = {"qty": auto_trade_qty, "avg_price": now_price, "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                else:
                    old_qty = portfolio["stocks"][current_ticker_in_input]["qty"]
                    old_avg_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
                    new_total_cost = (old_qty * old_avg_price) + (auto_trade_qty * now_price)
                    new_total_qty = old_qty + auto_trade_qty
                    portfolio["stocks"][current_ticker_in_input]["qty"] = new_total_qty
                    portfolio["stocks"][current_ticker_in_input]["avg_price"] = new_total_cost / new_total_qty
                
                portfolio["cash"] -= costo_total_auto
                notification_message = f"🤖 Compra automática de {auto_trade_qty} acciones de {current_ticker_in_input} a ${now_price:.2f}."
                notification_style = {'color': '#66BB6A'} # Softer green for success
                latest_data["last_auto_trade_rec"][current_ticker_in_input] = BUY_SIGNAL
                save_portfolio(portfolio)
            else:
                auto_trade_status_message = "Automático: Fondos insuficientes para comprar."
                notification_style = {'color': '#EF5350'} # Softer red for error
    
    elif rec == SELL_SIGNAL:
        if last_auto_rec_for_ticker != SELL_SIGNAL:
            if current_ticker_in_input in portfolio["stocks"] and portfolio["stocks"][current_ticker_in_input]["qty"] >= auto_trade_qty:
                avg_buy_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
                realized_pnl = (now_price - avg_buy_price) * auto_trade_qty
                realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Automática de {current_ticker_in_input}: ${realized_pnl:.2f}"

                portfolio["cash"] += auto_trade_qty * now_price
                
                portfolio["closed_trades"].append({
                    "Fecha Venta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Ticker": current_ticker_in_input,
                    "Cantidad": auto_trade_qty,
                    "Precio Compra Promedio": round(avg_buy_price, 2),
                    "Precio Venta": round(now_price, 2),
                    "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
                })

                portfolio["stocks"][current_ticker_in_input]["qty"] -= auto_trade_qty
                if portfolio["stocks"][current_ticker_in_input]["qty"] == 0:
                    del portfolio["stocks"][current_ticker_in_input]
                
                notification_message = f"🤖 Venta automática de {auto_trade_qty} acciones de {current_ticker_in_input} a ${now_price:.2f}."
                notification_style = {'color': '#66BB6A'} # Softer green for success
                latest_data["last_auto_trade_rec"][current_ticker_in_input] = SELL_SIGNAL
                save_portfolio(portfolio)
            else:
                auto_trade_status_message = "Automático: No hay suficientes acciones para vender."
                notification_style = {'color': '#EF5350'} # Softer red for error
    else:
        latest_data["last_auto_trade_rec"][current_ticker_in_input] = rec
        auto_trade_status_message = f"Automático: {rec} para {current_ticker_in_input}. Esperando señal de compra/venta."

    return auto_trade_status_message, notification_message, notification_style, realized_pnl_message, portfolio["closed_trades"]


if __name__ == "__main__":
    app.run(debug=True)
