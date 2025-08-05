import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import ta
import dash_bootstrap_components as dbc
from datetime import datetime, time, timedelta
import json # Importamos la librería json
import os   # Importamos la librería os para verificar archivos

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
latest_data = {"ticker": None, "graphs": {}, "df": pd.DataFrame(), "rec": "", "analyst": "", "last_rec_for_notification": None, "last_auto_trade_rec": {}}

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
    
    Args:
        df (pd.DataFrame): DataFrame con columnas 'Open', 'High', 'Low', 'Close', 'Volume'.
        
    Returns:
        pd.DataFrame: DataFrame con los indicadores añadidos.
    """
    # Índice de Fuerza Relativa (RSI)
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    
    # Convergencia/Divergencia de Medias Móviles (MACD)
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()
    df['MACD_hist'] = macd.macd_diff() # Histograma MACD
    
    # Bandas de Bollinger
    boll = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['Upper'] = boll.bollinger_hband() # Banda superior
    df['Lower'] = boll.bollinger_lband() # Banda inferior
    df['SMA20'] = ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator() # Media móvil simple de 20 periodos
    
    # Índice Direccional Promedio (ADX)
    df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx()
    
    # Oscilador Estocástico
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
    df['Stoch_K'] = stoch.stoch() # Línea %K
    df['Stoch_D'] = stoch.stoch_signal() # Línea %D

    # Media Móvil Simple del Volumen (para la nueva regla de volumen)
    df['Volume_SMA'] = df['Volume'].rolling(window=10).mean()
    
    return df

# --------------------- FUNCION PRINCIPAL DE ANALISIS Y RECOMENDACION ---------------------
def analyze_stock(ticker, period="5d", interval="15m"):
    """
    Obtiene datos de un ticker, calcula indicadores, genera gráficos
    y emite una recomendación de trading basada en la lógica.
    
    Args:
        ticker (str): Símbolo del ticker (ej. "AAPL").
        period (str): Periodo de tiempo para obtener datos (ej. "5d", "1mo").
        interval (str): Intervalo de los datos (ej. "15m", "1h").
        
    Returns:
        tuple: (recomendacion, recomendacion_analista, df_con_indicadores, diccionario_de_graficos, df_completo_para_simulador)
    """
    stock = yf.Ticker(ticker)
    info = stock.info # Información general del ticker
    hist = stock.history(period=period, interval=interval) # Datos históricos

    if hist.empty:
        # Si no hay datos, devuelve valores por defecto
        return "No hay datos", "N/A", hist, {}, pd.DataFrame()

    # Filtra filas donde el volumen es 0 (usualmente fuera del horario de mercado)
    hist = hist[hist['Volume'] > 0]
    
    # Calcula los indicadores técnicos
    df = calculate_indicators(hist.copy())

    # --- Coeficientes para el peso de cada indicador (ajustables para day trading) ---
    # Puedes cambiar estos valores para darle más o menos importancia a cada indicador.
    # Un valor más alto significa que la señal de ese indicador tendrá un mayor impacto.
    COEF_BOLLINGER = 1.0 # Peso para las Bandas de Bollinger
    COEF_RSI = 2.0       # Mayor peso para RSI (indicador de corto plazo)
    COEF_MACD = 2.0      # Mayor peso para MACD (indicador de corto plazo)
    COEF_STOCH = 2.0     # Mayor peso para Oscilador Estocástico (indicador de corto plazo)
    COEF_ADX_SMA = 1.0   # Peso para ADX y SMA20 (indicadores de tendencia)
    COEF_VOLUME = 1.0    # Nuevo peso para la regla de Volumen
    # ---------------------------------------------------------------------------------

    # Lógica de recomendación basada en indicadores
    buy_score = 0.0
    sell_score = 0.0

    # Reglas de Bandas de Bollinger
    if not df.empty and df['Close'].iloc[-1] < df['Lower'].iloc[-1]:
        buy_score += COEF_BOLLINGER # Precio por debajo de la banda inferior (señal de compra)
    if not df.empty and df['Close'].iloc[-1] > df['Upper'].iloc[-1]:
        sell_score += COEF_BOLLINGER # Precio por encima de la banda superior (señal de venta)

    # Reglas de RSI
    if not df.empty and df['RSI'].iloc[-1] < 30:
        buy_score += COEF_RSI # RSI por debajo de 30 (sobreventa, señal de compra fuerte)
    elif not df.empty and df['RSI'].iloc[-1] > 70:
        sell_score += COEF_RSI # RSI por encima de 70 (sobrecompra, señal de venta fuerte)

    # Reglas de MACD (cruce de líneas)
    if not df.empty and len(df) >= 2:
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] and df['MACD'].iloc[-2] <= df['Signal'].iloc[-2]:
            buy_score += COEF_MACD # Cruce alcista (MACD cruza por encima de la señal, señal de compra fuerte)
        elif df['MACD'].iloc[-1] < df['Signal'].iloc[-1] and df['MACD'].iloc[-2] >= df['Signal'].iloc[-2]:
            sell_score += COEF_MACD # Cruce bajista (MACD cruza por debajo de la señal, señal de venta fuerte)

    # Reglas de Oscilador Estocástico
    if not df.empty and df['Stoch_K'].iloc[-1] < 20 and df['Stoch_D'].iloc[-1] < 20:
        buy_score += COEF_STOCH # Estocástico sobreventa (señal de compra fuerte)
    elif not df.empty and df['Stoch_K'].iloc[-1] > 80 and df['Stoch_D'].iloc[-1] > 80:
        sell_score += COEF_STOCH # Estocástico sobrecompra (señal de venta fuerte)

    # Reglas de ADX y SMA20 (fuerza de tendencia)
    if not df.empty and df['ADX'].iloc[-1] > 25: # Si hay una tendencia fuerte
        if df['Close'].iloc[-1] > df['SMA20'].iloc[-1]:
            buy_score += COEF_ADX_SMA # Precio por encima de SMA20 (tendencia alcista, señal de compra)
        else:
            sell_score += COEF_ADX_SMA # Precio por debajo de SMA20 (tendencia bajista, señal de venta)

    # Nueva Regla de Volumen: Volumen alto con movimiento de precio
    # Se considera volumen alto si es 1.5 veces la media móvil de volumen
    if not df.empty and len(df) >= 2 and not df['Volume_SMA'].iloc[-1] == 0:
        if df['Volume'].iloc[-1] > (1.5 * df['Volume_SMA'].iloc[-1]): # Si el volumen actual es significativamente alto
            if df['Close'].iloc[-1] > df['Close'].iloc[-2]: # Y el precio subió
                buy_score += COEF_VOLUME
            elif df['Close'].iloc[-1] < df['Close'].iloc[-2]: # Y el precio bajó
                sell_score += COEF_VOLUME

    # Determina la recomendación final
    # La diferencia de 1.0 en la condición es un umbral para que la recomendación sea más decisiva.
    # Puedes ajustar este umbral también.
    if buy_score > sell_score + 1.0: 
        recommendation = "📈 Comprar"
    elif sell_score > buy_score + 1.0:
        recommendation = "📉 Vender"
    elif buy_score > 0.0 or sell_score > 0.0:
        recommendation = "👁 Observar" # Hay señales, pero no lo suficientemente fuertes para una acción clara
    else:
        recommendation = "🤝 Mantener" # No hay señales claras de compra o venta

    # Obtiene la recomendación de analistas de Yahoo Finance
    analyst_rec = info.get("recommendationKey", "No disponible").capitalize()

    # Generación de gráficos
    rangebreaks = get_market_rangebreaks()
    graphs = {}

    # Lista de figuras a las que añadir las líneas de separación diaria
    figures_to_update = []

    # Gráfico de Precio con Bandas de Bollinger y SMA20
    fig_price = go.Figure([
        go.Scatter(x=df.index, y=df['Close'], name="Cierre", connectgaps=False, line=dict(color='blue')),
        go.Scatter(x=df.index, y=df['Upper'], name="Banda Sup", connectgaps=False, line=dict(dash='dot', color='red')),
        go.Scatter(x=df.index, y=df['Lower'], name="Banda Inf", connectgaps=False, line=dict(dash='dot', color='green')),
        go.Scatter(x=df.index, y=df['SMA20'], name="SMA20", connectgaps=False, line=dict(dash='dash', color='purple'))
    ])
    fig_price.update_layout(title="Precio con Bandas de Bollinger y SMA20", xaxis=dict(rangebreaks=rangebreaks))
    figures_to_update.append(fig_price)
    graphs["Precio"] = fig_price

    # Gráfico de RSI
    fig_rsi = go.Figure([
        go.Scatter(x=df.index, y=df['RSI'], name="RSI", connectgaps=False, line=dict(color='orange'))
    ])
    fig_rsi.update_layout(title="RSI", xaxis=dict(rangebreaks=rangebreaks), yaxis=dict(range=[0,100]))
    fig_rsi.add_hline(y=30, line_dash="dot", line_color="green", annotation_text="Sobreventa")
    fig_rsi.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="Sobrecompra")
    figures_to_update.append(fig_rsi)
    graphs["RSI"] = fig_rsi

    # Gráfico de MACD
    fig_macd = go.Figure([
        go.Scatter(x=df.index, y=df['MACD'], name="MACD", connectgaps=False, line=dict(color='blue')),
        go.Scatter(x=df.index, y=df['Signal'], name="Señal", connectgaps=False, line=dict(color='red')),
        go.Bar(x=df.index, y=df['MACD_hist'], name="Histograma", marker_color='grey')
    ])
    fig_macd.update_layout(title="MACD", xaxis=dict(rangebreaks=rangebreaks))
    figures_to_update.append(fig_macd)
    graphs["MACD"] = fig_macd

    # Gráfico de ADX
    fig_adx = go.Figure([
        go.Scatter(x=df.index, y=df['ADX'], name="ADX", connectgaps=False, line=dict(color='purple'))
    ])
    fig_adx.update_layout(title="ADX", xaxis=dict(rangebreaks=rangebreaks), yaxis=dict(range=[0,100]))
    fig_adx.add_hline(y=25, line_dash="dot", line_color="grey", annotation_text="Tendencia")
    figures_to_update.append(fig_adx)
    graphs["ADX"] = fig_adx

    # Gráfico de Estocástico
    fig_stoch = go.Figure([
        go.Scatter(x=df.index, y=df['Stoch_K'], name="%K", connectgaps=False, line=dict(color='blue')),
        go.Scatter(x=df.index, y=df['Stoch_D'], name="%D", connectgaps=False, line=dict(color='red'))
    ])
    fig_stoch.update_layout(title="Estocástico", xaxis=dict(rangebreaks=rangebreaks), yaxis=dict(range=[0,100]))
    fig_stoch.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="Sobreventa")
    fig_stoch.add_hline(y=80, line_dash="dot", line_color="red", annotation_text="Sobrecompra")
    figures_to_update.append(fig_stoch)
    graphs["Estocástico"] = fig_stoch

    # Gráfico de Volumen
    fig_vol = go.Figure([
        go.Bar(x=df.index, y=df['Volume'], name="Volumen", marker_color='lightgrey')
    ])
    fig_vol.update_layout(title="Volumen", xaxis=dict(rangebreaks=rangebreaks))
    figures_to_update.append(fig_vol)
    graphs["Volumen"] = fig_vol

    # --- Añadir líneas verticales para separar los días ---
    unique_days = df.index.normalize().unique() # Obtiene solo la parte de la fecha (sin la hora)
    for day in unique_days:
        # Para cada día, añade una línea vertical al inicio del día
        # Solo añade la línea si no es el último día completo, para evitar una línea al final
        if day != unique_days.max(): # Evita dibujar una línea al final del último día
            for fig in figures_to_update:
                fig.add_vline(
                    x=pd.Timestamp(day), # Posición de la línea (inicio del día)
                    line_width=1,
                    line_dash="dash",
                    line_color="rgba(128, 128, 128, 0.5)" # Color gris semitransparente
                )
    # -----------------------------------------------------

    return recommendation, analyst_rec, df, graphs, df

# --------------------- DASH APP ---------------------

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Análisis Técnico y Simulador de Trading"

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H3("Análisis de Ticker", className="text-center mb-3"),
            dbc.Input(id="ticker", value="AAPL", type="text", debounce=True, placeholder="Introduce un Ticker"),
            dbc.Button("Actualizar Datos", id="actualizar", n_clicks=0, className="mt-2 w-100 btn-primary")
        ], width=4, className="d-flex flex-column align-items-center"),
        dbc.Col([
            html.Div(id="recomendacion", className="text-center my-3 fw-bold fs-4 text-success"),
            html.Div(id="analyst-output", className="text-center fs-5 text-muted"),
            html.Div(id='notification', className='text-center fs-5 text-warning')
        ], width=8, className="d-flex flex-column justify-content-center")
    ], className="my-4 p-3 border rounded shadow-sm bg-light"),

    dcc.Tabs(id="tabs", value="Precio", children=[
        dcc.Tab(label=tab, value=tab, className="custom-tab", selected_className="custom-tab--selected") 
        for tab in ['Precio', 'RSI', 'MACD', 'ADX', 'Estocástico', 'Volumen']
    ], className="mt-3 mb-4"),
    dcc.Graph(id="grafico", config={'displayModeBar': False}),

    dbc.Row([
        dbc.Col([
            html.H4("Simulador de Trading Manual", className="text-center mb-3"),
            dbc.Input(id="cantidad", type="number", placeholder="Cantidad de acciones", min=1, step=1, value=1, className="mb-2"),
            dbc.Button("Comprar", id="comprar", n_clicks=0, className="btn-success me-2"),
            dbc.Button("Vender", id="vender", n_clicks=0, className="btn-danger me-2"),
            dbc.Button("Resetear Cartera", id="reset", n_clicks=0, className="btn-secondary"),
            html.Div(id="cartera", className="mt-3 text-center fw-bold fs-5")
        ], width=6, className="p-3 border rounded shadow-sm bg-light"),
        dbc.Col([
            html.H4("Opciones de Compra/Venta Automática", className="text-center mb-3"),
            dbc.Checklist(
                options=[{"label": "Activar Compra/Venta Automática", "value": "AUTO_TRADE_ON"}],
                value=[], # Por defecto, desactivado
                id="auto-trade-toggle",
                inline=True,
                switch=True,
                className="mb-2"
            ),
            dbc.Input(id="auto-trade-quantity", type="number", placeholder="Cantidad Auto", min=1, step=1, value=1, className="mb-2"),
            html.Div(id="auto-trade-status", className="mt-2 text-center text-info")
        ], width=6, className="p-3 border rounded shadow-sm bg-light")
    ], className="my-4 g-4"),

    html.Hr(),
    html.H4("Posiciones Abiertas", className="text-center mb-3"),
    dash_table.DataTable(
        id="open-positions-table", # ID cambiado para claridad
        columns=[
            {"name": "Fecha Compra", "id": "Fecha Compra"},
            {"name": "Ticker", "id": "Ticker"},
            {"name": "Cantidad", "id": "Cantidad"},
            {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
            {"name": "Ganancia/Pérdida (No Realizada)", "id": "Ganancia/Pérdida (No Realizada)"}
        ],
        data=[],
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_cell={"textAlign": "center", "padding": "8px"},
        style_header={
            "backgroundColor": "rgba(0,0,0,0.05)",
            "fontWeight": "bold"
        },
        style_data_conditional=[
            {"if": {"column_id": "Ganancia/Pérdida (No Realizada)", "filter_query": "{Ganancia/Pérdida (No Realizada)} > 0"},
             "color": "green"},
            {"if": {"column_id": "Ganancia/Pérdida (No Realizada)", "filter_query": "{Ganancia/Pérdida (No Realizada)} < 0"},
             "color": "red"}
        ]
    ),
    html.Div(id="realized-pnl-message", className="text-center mt-2 fs-5 text-info"), # Para mostrar P/L realizado de la última venta

    html.Hr(),
    html.H4("Historial de Ventas Realizadas", className="text-center mb-3"),
    dash_table.DataTable(
        id="closed-trades-table", # Nueva tabla para ventas realizadas
        columns=[
            {"name": "Fecha Venta", "id": "Fecha Venta"},
            {"name": "Ticker", "id": "Ticker"},
            {"name": "Cantidad", "id": "Cantidad"},
            {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
            {"name": "Precio Venta", "id": "Precio Venta"},
            {"name": "Ganancia/Pérdida Realizada", "id": "Ganancia/Pérdida Realizada"}
        ],
        data=[],
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_cell={"textAlign": "center", "padding": "8px"},
        style_header={
            "backgroundColor": "rgba(0,0,0,0.05)",
            "fontWeight": "bold"
        },
        style_data_conditional=[
            {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada} > 0"},
             "color": "green"},
            {"if": {"column_id": "Ganancia/Pérdida Realizada", "filter_query": "{Ganancia/Pérdida Realizada} < 0"},
             "color": "red"}
        ]
    ),

    dcc.Interval(id='auto-update', interval=60000, n_intervals=0),

], fluid=True, className="bg-light")

# --------------------- CALLBACK PRINCIPAL ---------------------

@app.callback(
    Output("grafico", "figure"),
    Output("recomendacion", "children"),
    Output("analyst-output", "children"),
    Output("cartera", "children"),
    Output("open-positions-table", "data"), # Salida para posiciones abiertas
    Output("notification", "children"),
    Output("auto-trade-status", "children"),
    Output("realized-pnl-message", "children"), # Salida para P/L realizado de la última venta
    Output("closed-trades-table", "data"), # Nueva salida para el historial de ventas realizadas
    Input("actualizar", "n_clicks"),
    Input("tabs", "value"),
    Input("comprar", "n_clicks"),
    Input("vender", "n_clicks"),
    Input("reset", "n_clicks"),
    Input('auto-update', 'n_intervals'),
    State("ticker", "value"),
    State("cantidad", "value"),
    State("auto-trade-toggle", "value"),
    State("auto-trade-quantity", "value")
)
def update_dashboard(n_clicks, tab, buy_clicks, sell_clicks, reset_clicks, n_intervals, 
                     ticker, cantidad_manual, auto_trade_toggle_value, auto_trade_quantity):
    global portfolio, latest_data

    ctx = callback_context
    if not ctx.triggered:
        changed_id = 'no_trigger'
    else:
        changed_id = ctx.triggered[0]["prop_id"].split(".")[0]

    notification_message = ""
    auto_trade_status_message = ""
    realized_pnl_message = "" # Se inicializa aquí para cada ejecución del callback
    current_ticker_in_input = ticker.strip().upper()

    old_rec_for_this_ticker = None
    if latest_data["ticker"] == current_ticker_in_input:
        old_rec_for_this_ticker = latest_data["last_rec_for_notification"]
    
    # --- Lógica de Obtención/Caché de Datos ---
    if changed_id in ["actualizar", "auto-update"] or latest_data["ticker"] != current_ticker_in_input:
        rec, analyst, df, graphs, _ = analyze_stock(current_ticker_in_input)
        latest_data.update({
            "ticker": current_ticker_in_input, 
            "graphs": graphs, 
            "df": df, 
            "rec": rec, 
            "analyst": analyst,
            "last_rec_for_notification": rec # Guarda la recomendación actual para la próxima comparación
        })
        if latest_data["ticker"] != current_ticker_in_input:
            latest_data["last_auto_trade_rec"].pop(current_ticker_in_input, None) # Limpia el registro de auto-trade para el nuevo ticker
    else:
        rec = latest_data["rec"]
        analyst = latest_data["analyst"]
        graphs = latest_data["graphs"]
        df = latest_data["df"]
    # --- Fin Lógica de Obtención/Caché de Datos ---

    if df.empty:
        return go.Figure(), "❌ No hay datos para este Ticker", "Recomendación analista: N/A", \
               f"💰 Efectivo: ${portfolio['cash']:.2f} | 📦 Acciones: {sum(stock_info['qty'] for stock_info in portfolio['stocks'].values()) if portfolio['stocks'] else 0} | 💼 Valor total: ${portfolio['cash']:.2f}", \
               [], "Introduce un ticker válido.", "Automático: Desactivado", "", [] # Se añade [] para la nueva tabla

    now_price = df["Close"].iloc[-1]

    # --- Lógica de Compra/Venta Automática ---
    is_auto_trade_enabled = "AUTO_TRADE_ON" in auto_trade_toggle_value
    auto_trade_qty = int(auto_trade_quantity) if auto_trade_quantity and auto_trade_quantity > 0 else 1

    if is_auto_trade_enabled and changed_id == "auto-update":
        last_auto_rec_for_ticker = latest_data["last_auto_trade_rec"].get(current_ticker_in_input)

        if rec == "📈 Comprar":
            if last_auto_rec_for_ticker != "📈 Comprar":
                costo_total_auto = auto_trade_qty * now_price
                if portfolio["cash"] >= costo_total_auto:
                    # Actualizar portfolio["stocks"] con el precio promedio de compra
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
                    latest_data["last_auto_trade_rec"][current_ticker_in_input] = "📈 Comprar"
                    save_portfolio(portfolio) # Guardar después de la operación
                else:
                    auto_trade_status_message = "Automático: Fondos insuficientes para comprar."
        
        elif rec == "📉 Vender":
            if last_auto_rec_for_ticker != "📉 Vender":
                if current_ticker_in_input in portfolio["stocks"] and portfolio["stocks"][current_ticker_in_input]["qty"] >= auto_trade_qty:
                    avg_buy_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
                    realized_pnl = (now_price - avg_buy_price) * auto_trade_qty
                    realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Automática de {current_ticker_in_input}: ${realized_pnl:.2f}"

                    portfolio["cash"] += auto_trade_qty * now_price
                    
                    # Añadir a closed_trades
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
                    latest_data["last_auto_trade_rec"][current_ticker_in_input] = "📉 Vender"
                    save_portfolio(portfolio) # Guardar después de la operación
                else:
                    auto_trade_status_message = "Automático: No hay suficientes acciones para vender."
        else:
            latest_data["last_auto_trade_rec"][current_ticker_in_input] = rec
            auto_trade_status_message = f"Automático: {rec} para {current_ticker_in_input}. Esperando señal de compra/venta."
    elif is_auto_trade_enabled:
        auto_trade_status_message = "Automático: Activado. Esperando actualización para operar."
    else:
        auto_trade_status_message = "Automático: Desactivado."
    # --- Fin Lógica de Compra/Venta Automática ---


    # --- Lógica de Compra/Venta Manual ---
    if changed_id == "comprar" and cantidad_manual:
        costo_total = cantidad_manual * now_price
        if portfolio["cash"] >= costo_total:
            # Actualizar portfolio["stocks"] con el precio promedio de compra
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
            save_portfolio(portfolio) # Guardar después de la operación
        else:
            notification_message = "❌ Fondos insuficientes para realizar la compra."

    elif changed_id == "vender" and cantidad_manual:
        if current_ticker_in_input in portfolio["stocks"] and portfolio["stocks"][current_ticker_in_input]["qty"] >= cantidad_manual:
            avg_buy_price = portfolio["stocks"][current_ticker_in_input]["avg_price"]
            realized_pnl = (now_price - avg_buy_price) * cantidad_manual
            realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Manual de {current_ticker_in_input}: ${realized_pnl:.2f}"

            portfolio["cash"] += cantidad_manual * now_price
            
            # Añadir a closed_trades
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
            save_portfolio(portfolio) # Guardar después de la operación
        else:
            notification_message = "❌ No tienes suficientes acciones para vender."

    elif changed_id == "reset":
        portfolio["cash"] = portfolio["initial_cash"]
        portfolio["stocks"] = {}
        portfolio["closed_trades"] = [] # También se limpia el historial de ventas realizadas
        notification_message = "🔄 Cartera reseteada a los valores iniciales."
        save_portfolio(portfolio) # Guardar después de la operación
    # --- Fin Lógica de Compra/Venta Manual ---

    # Calcular valor total de la cartera
    total_valor_acciones = sum(
        (now_price * stock_info['qty']) # Usar now_price para valor actual
        for ticker_, stock_info in portfolio["stocks"].items()
    )
    total_valor = portfolio["cash"] + total_valor_acciones
    cartera_txt = f"💰 Efectivo: ${portfolio['cash']:.2f} | 📦 Acciones: {sum(stock_info['qty'] for stock_info in portfolio['stocks'].values()) if portfolio['stocks'] else 0} | 💼 Valor total: ${total_valor:.2f}"

    # Reconstruir el historial de operaciones para mostrar solo acciones compradas (posiciones abiertas)
    # y actualizar su Ganancia/Pérdida no realizada
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

    # Notificación si la recomendación ha cambiado (solo si no es una operación automática)
    if changed_id == "auto-update" and \
       old_rec_for_this_ticker is not None and \
       old_rec_for_this_ticker != rec and \
       not notification_message.startswith("🤖"):
        notification_message = f"🔔 Nueva recomendación para {current_ticker_in_input}: {rec} (antes: {old_rec_for_this_ticker})"

    fig = graphs.get(tab, go.Figure())

    # --- Lógica de Zoom para mostrar solo el último día completo ---
    if not df.empty:
        last_data_date = df.index[-1].normalize()
        unique_days_in_df = df.index.normalize().unique().sort_values(ascending=False)
        if len(unique_days_in_df) > 0:
            day_to_display = unique_days_in_df[0]
            start_of_day = pd.Timestamp(day_to_display.date())
            end_of_day = pd.Timestamp(day_to_display.date()) + timedelta(days=1) - timedelta(seconds=1)
            fig.update_layout(xaxis_range=[start_of_day, end_of_day])
    # -----------------------------------------------------------------

    return fig, rec, f"🔍 Recomendación analista: {analyst}", cartera_txt, open_positions_data, notification_message, auto_trade_status_message, realized_pnl_message, portfolio["closed_trades"]

if __name__ == "__main__":
    app.run(debug=True)
