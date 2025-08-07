# layout.py
import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from constants import popular_tickers, GRAPH_DESCRIPTIONS
from config_editor import get_dict

def _tooltips():
    """Return a list of Tooltips for the tab labels."""
    return [
        dbc.Tooltip(GRAPH_DESCRIPTIONS["Candlestick"], target="tab-candlestick-tooltip", placement="top"),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["RSI"],        target="tab-rsi-tooltip",        placement="top"),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["MACD"],       target="tab-macd-tooltip",       placement="top"),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["ADX"],        target="tab-adx-tooltip",        placement="top"),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["Estocástico"],target="tab-stoch-tooltip",      placement="top"),
        dbc.Tooltip(GRAPH_DESCRIPTIONS["Volumen"],    target="tab-volume-tooltip",     placement="top"),
    ]

def header_row():
    return dbc.Row(className="shadow-sm p-3 mb-4", children=[
        dbc.Col(width=3, children=[
            html.Div(id='company-name-output', className="mb-1 text-center"),
            dbc.InputGroup([
                html.Datalist(id='popular-tickers-list',
                              children=[html.Option(value=t) for t in popular_tickers]),
                dbc.Input(id="ticker", value="AAPL", type="text", debounce=True,
                          placeholder="Introduce un Ticker", list="popular-tickers-list",
                          autoComplete="on", className="rounded-4"),
                dbc.Button("🔄", id="refresh-button", n_clicks=0,
                           className="btn-primary rounded-4")
            ])
        ]),
        dbc.Col(width=5, className="d-flex flex-column justify-content-center", children=[
            dbc.Row(className="g-0 justify-content-center", children=[
                dbc.Col(html.Div(id="recomendacion", className="text-center fw-bold fs-4"), width=6),
                dbc.Col(html.Div(id="analyst-output", className="text-center fs-5"), width=6),
            ])
        ]),
        dbc.Col(width=4, className="d-flex flex-column justify-content-center align-items-center", children=[
            html.Div(id="market-status-info", className="text-center fs-5"),
            html.Div(id="current-price-info", className="text-center fw-bold fs-4")
        ])
    ])

def tabs_block():
    return dbc.Tabs(id="tabs", active_tab="tab-candlestick",
                    className="mb-4", style={'border':'none'}, children=[
        dbc.Tab(label='Precio (Velas y Línea)', tab_id='tab-candlestick', id="tab-candlestick-tooltip"),
        dbc.Tab(label='RSI',                    tab_id='tab-rsi',        id="tab-rsi-tooltip"),
        dbc.Tab(label='MACD',                   tab_id='tab-macd',       id="tab-macd-tooltip"),
        dbc.Tab(label='ADX',                    tab_id='tab-adx',        id="tab-adx-tooltip"),
        dbc.Tab(label='Estocástico',            tab_id='tab-stoch',      id="tab-stoch-tooltip"),
        dbc.Tab(label='Volumen',                tab_id='tab-volume',     id="tab-volume-tooltip"),
        dbc.Tab(label='Backtest',               tab_id='tab-backtest',   id="tab-backtest-tooltip"),
        dbc.Tab(label="Config", tab_id="tab-config", id="tab-config-tooltip")
    ])

def trading_cards():
    return dbc.Row([
        dbc.Col(
            dbc.Card(className="mb-4 rounded-4", children=[
                dbc.CardHeader(html.H4("Simulador Manual", className="text-center")),
                dbc.CardBody([
                    dbc.Input(id="cantidad", type="number", placeholder="Cantidad de acciones",
                              min=1, step=1, value=1, className="mb-2 rounded-5"),
                    dbc.Button("Comprar",  id="comprar",  n_clicks=0,
                               className="btn-success me-2 rounded-5"),
                    dbc.Button("Vender",   id="vender",   n_clicks=0,
                               className="btn-danger me-2 rounded-5"),
                    dbc.Button("Resetear Cartera", id="reset", n_clicks=0,
                               className="btn-secondary rounded-5"),
                    dbc.Button("Parar Aplicación", id="stop-button", n_clicks=0,
                               className="btn-warning mt-2 rounded-5"),
                    html.Div(id="cartera", className="mt-3 text-center fw-bold fs-5")
                ])
            ]), width=6
        ),
        dbc.Col(
            dbc.Card(className="mb-4 rounded-4", children=[
                dbc.CardHeader(html.H4("Trading Automático", className="text-center")),
                dbc.CardBody([
                    dbc.Checklist(
                        options=[{"label":"Activar Compra/Venta Automática","value":"AUTO_TRADE_ON"}],
                        value=[], id="auto-trade-toggle", inline=True, switch=True,
                        className="mb-2"),
                    dbc.Input(id="auto-trade-quantity", type="number",
                              placeholder="Cantidad Auto", min=1, step=1, value=1,
                              className="mb-2 rounded-5"),
                    html.Div(id="auto-trade-status", className="mt-2 text-center")
                ])
            ]), width=6
        )
    ])

def tables():
    open_cols = [
        {"name": "Fecha Compra", "id": "Fecha Compra"},
        {"name": "Ticker", "id": "Ticker"},
        {"name": "Cantidad", "id": "Cantidad"},
        {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
        {"name": "Ganancia/Pérdida (No Realizada)", "id": "Ganancia/Pérdida (No Realizada)"}
    ]

    closed_cols = [
        {"name": "Fecha Venta", "id": "Fecha Venta"},
        {"name": "Ticker", "id": "Ticker"},
        {"name": "Cantidad", "id": "Cantidad"},
        {"name": "Precio Compra Promedio", "id": "Precio Compra Promedio"},
        {"name": "Precio Venta", "id": "Precio Venta"},
        {"name": "Ganancia/Pérdida Realizada", "id": "Ganancia/Pérdida Realizada"}
    ]

    return [
        html.Hr(className="my-4"),
        dash_table.DataTable(
            id="open-positions-table",
            columns=open_cols,
            data=[],
            style_table={'marginBottom': '1.5rem'}
        ),
        html.H4("Historial de Ventas Realizadas", className="text-center mb-3"),
        dash_table.DataTable(
            id="closed-trades-table",
            columns=closed_cols,
            data=[]
        )
    ]

def backtest_ui():
    bt_columns = [{"name": col, "id": col} for col in
              ["EntryTime", "ExitTime", "Size", "EntryPrice", "ExitPrice", "PnL"]]
    return html.Div([
        dbc.Row([
            dbc.Col([dbc.Label("Start Date"),
                     dcc.DatePickerSingle(id='bt-start', date='2025-06-01',
                                          display_format='YYYY-MM-DD', className="mb-2")], width=2),
            dbc.Col([dbc.Label("End Date"),
                     dcc.DatePickerSingle(id='bt-end', date='2025-07-01',
                                          display_format='YYYY-MM-DD', className="mb-2")], width=2),
            dbc.Col([dbc.Label("Interval"),
                     html.Div(dcc.Dropdown(id='bt-interval',
                                           options=[{"label":"1 min","value":"1m"},
                                                    {"label":"5 min","value":"5m"},
                                                    {"label":"15 min","value":"15m"},
                                                    {"label":"1 hour","value":"1h"},
                                                    {"label":"1 day","value":"1d"}],
                                           value="15m", clearable=False,
                                           className="dash-dropdown mb-2"))], width=2),
            dbc.Col([dbc.Button("Run Backtest", id="bt-run", n_clicks=0,
                                className="btn-primary mt-4")], width=2)
        ], className="mb-4"),
        html.Hr(),
        html.Div(id="bt-summary", className="mb-4"),
        dash_table.DataTable(
            id="bt-closed-trades",
            columns=bt_columns,
            data=[],
            style_table={'overflowX': 'auto', 'border-radius': '0.5rem', 'overflow': 'hidden'},
            style_cell={'textAlign': 'center', 'backgroundColor': 'var(--bg-surface)', 'color': 'var(--text)'},
            style_header={'backgroundColor': 'var(--bg-surface-2)', 'fontWeight': 'bold'}
        ),
        html.Div(id="bt-loading", className="d-none", children=[
            dbc.Spinner(size="lg", color="primary", type="grow"),
            html.Br(),
            html.Div("Running backtest... Please wait...")
        ])
    ])

def serve_layout():
    return html.Div(id='main-div', children=[
        dbc.Container(fluid=True, children=[
            header_row(),
            tabs_block(),
            *_tooltips(),
            dcc.Loading(id="loading-1", type="default",
                        children=html.Div(id="dynamic-content")),
            trading_cards(),
            *tables(),
            dcc.Interval(id='analysis-update', interval=60_000, n_intervals=0),
            dcc.Interval(id='price-update',    interval=5_000,  n_intervals=0),
            dbc.Tooltip("Toggle light/dark mode", target="theme-toggle", placement="right")
        ]),
        dcc.Store(id='bt-store',  data=None),
        dcc.Store(id='bt-lock',   data=False),
        html.Div(id='notification-container', style={
            'position': 'fixed', 'bottom': '10px', 'right': '10px',
            'width': '350px', 'z-index': 1000
        }),
        html.Div(id="realized-pnl-message", className="text-center mt-2 fs-5")
    ])

backtest_layout = backtest_ui()

def config_ui():
    cfg = get_dict()
    rows = []
    for key, val in cfg.items():
        rows.append(
            dbc.Row(
                [
                    dbc.Label(key, width=4),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "config-input", "index": key},
                            value=str(val),
                            type="number" if isinstance(val, (int, float)) else "text",
                        ),
                        width=8,
                    ),
                ],
                className="mb-2",
            )
        )
    return html.Div(
        [
            html.H4("Live Configuration Editor"),
            dbc.Form(rows),
            dbc.Button("Apply", id="config-apply", n_clicks=0, color="primary", className="me-2 mt-3"),
            dbc.Button("Reset", id="config-reset", n_clicks=0, color="secondary", className="mt-3"),
            html.Div(id="config-feedback", className="mt-3"),
        ]
    )