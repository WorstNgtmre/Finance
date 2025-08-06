# layout.py

import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from .config import popular_tickers, GRAPH_DESCRIPTIONS

def serve_layout():
    return html.Div(id='main-div', style={'backgroundColor': '#121212'}, children=[
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
                data=[],
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