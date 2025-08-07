# callbacks.py
import os # Se añade la importación de 'os'
import dash
from dash import Input, Output, State, callback_context, html, dcc, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from backtest_engine import run_backtest
from layout import backtest_layout

from config import BUY_SIGNAL, SELL_SIGNAL
from data_processing import get_or_update_data
from state_management import TraderState

# A single instance of the state class will be used
state = TraderState()

def register_callbacks(app: dash.Dash):
    @app.callback(
        Output("dynamic-content", "children"), 
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
        State('bt-lock', 'data'),
        prevent_initial_call='initial_duplicate'
    )
    def update_analysis_and_graphs(n_clicks, n_intervals, active_tab, ticker, bt_lock):
        if bt_lock:                # back-test running → skip global refresh
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        changed_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else "initial_load"
        current_ticker_in_input = ticker.strip().upper() if ticker else "AAPL"
        graph_name = {
            'tab-candlestick': 'Candlestick', 'tab-rsi': 'RSI', 'tab-macd': 'MACD',
            'tab-adx': 'ADX', 'tab-stoch': 'Estocástico', 'tab-volume': 'Volumen',
        }.get(active_tab, 'Candlestick')
        notification_list: List[dbc.Alert] = []

        rec, analyst, df, graphs, market_info, long_name, error_message = get_or_update_data(current_ticker_in_input)

        if error_message:
            return go.Figure(), "Error", {'color': '#EF5350'}, "🔍 Recomendación analista: N/A", "text-center fs-5 text-danger", "", "", [dbc.Alert(error_message, color="danger", dismissable=True)], "N/A"

        # Update the state object instead of global variables
        if state.latest_data["rec"] is not None and state.latest_data["rec"] != rec:
            notification_list.append(dbc.Alert(f"🔔 Nueva recomendación para {current_ticker_in_input}: {rec} (antes: {state.latest_data['rec']})", color="info", dismissable=True, className="mt-2"))

        state.update_latest_data(current_ticker_in_input, rec, analyst, df, graphs, market_info, long_name)

        rec_style = {'color': '#66BB6A' if rec == BUY_SIGNAL else '#EF5350' if rec == SELL_SIGNAL else '#FFA726'}
        analyst_text = f"🔍 Recomendación analista: {analyst}"
        market_status_text = f"Mercado: {market_info.get('status', 'N/A')}"
        current_price = market_info.get('current_price')
        current_price_text = f"Precio: ${current_price:.2f}" if current_price is not None else ""
            # assemble the graph
        if active_tab == "tab-backtest":
            content = backtest_layout
        else:
            graph_name = {
                'tab-candlestick': 'Candlestick', 'tab-rsi': 'RSI', 'tab-macd': 'MACD',
                'tab-adx': 'ADX', 'tab-stoch': 'Estocástico', 'tab-volume': 'Volumen',
            }.get(active_tab, 'Candlestick')
            fig = graphs.get(graph_name, go.Figure())
            content = dcc.Graph(id="grafico", figure=fig, config={'displayModeBar': False})

        return (
            content,
            rec,
            rec_style,
            analyst_text,
            "text-center fs-5 text-white",
            market_status_text,
            current_price_text,
            notification_list,
            long_name,
        )
    
    @app.callback(
        Output("cartera", "children"),
        Output("open-positions-table", "data"),
        Input("price-update", "n_intervals"),
    )
    def update_portfolio_display(n_intervals: int) -> Tuple[str, List[Dict[str, Any]]]:
        return state.get_portfolio_data()

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
        ctx = callback_context
        changed_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if state.latest_data["df"].empty:
            return "", [dbc.Alert("❌ No se puede operar sin datos del ticker.", color="danger", dismissable=True)], state.portfolio["closed_trades"]

        current_ticker_in_input = ticker.strip().upper()
        now_price = state.latest_data["df"]["Close"].iloc[-1]

        if cantidad_manual is None or cantidad_manual <= 0:
            return "", [dbc.Alert("❌ La cantidad debe ser un número positivo.", color="danger", dismissable=True)], state.portfolio["closed_trades"]

        if changed_id == "comprar":
            notification_message, notification_color = state._buy_stock(current_ticker_in_input, cantidad_manual, now_price)
            return "", [dbc.Alert(notification_message, color=notification_color, dismissable=True, className="mt-2")], state.portfolio["closed_trades"]

        elif changed_id == "vender":
            notification_message, notification_color, realized_pnl = state._sell_stock(current_ticker_in_input, cantidad_manual, now_price)
            realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Manual de {current_ticker_in_input}: ${realized_pnl:.2f}" if notification_color == "success" else ""
            return realized_pnl_message, [dbc.Alert(notification_message, color=notification_color, dismissable=True, className="mt-2")], state.portfolio["closed_trades"]

        return "", [], state.portfolio["closed_trades"]

    @app.callback(
        Output("notification-container", "children", allow_duplicate=True),
        Output("realized-pnl-message", "children", allow_duplicate=True),
        Output("closed-trades-table", "data", allow_duplicate=True),
        Input("reset", "n_clicks"),
        prevent_initial_call=True
    )
    def handle_reset_portfolio(n_clicks: int) -> Tuple[List[dbc.Alert], str, List[Dict[str, Any]]]:
        if n_clicks > 0:
            message, color, closed_trades = state.reset_portfolio()
            return [dbc.Alert(message, color=color, dismissable=True, className="mt-2")], "", closed_trades
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
        current_ticker_in_input = ticker.strip().upper() if ticker else "AAPL"
        is_auto_trade_enabled = "AUTO_TRADE_ON" in auto_trade_toggle_value
        auto_trade_qty = int(auto_trade_quantity) if auto_trade_quantity and auto_trade_quantity > 0 else 1
        notification_list: List[dbc.Alert] = []
        auto_trade_status_message = "Automático: Desactivado."
        realized_pnl_message = ""

        if not is_auto_trade_enabled:
            return auto_trade_status_message, [], "", state.portfolio["closed_trades"]

        auto_trade_status_message = "Automático: Activado."

        if state.latest_data["df"].empty or state.latest_data["ticker"] != current_ticker_in_input:
            auto_trade_status_message = f"Automático: Activado. Esperando datos para {current_ticker_in_input}."
            return auto_trade_status_message, [], "", state.portfolio["closed_trades"]

        rec = state.latest_data["rec"]
        now_price = state.latest_data["df"]["Close"].iloc[-1]
        last_auto_rec_for_ticker = state.latest_data["last_auto_trade_rec"].get(current_ticker_in_input)

        if rec == BUY_SIGNAL:
            if last_auto_rec_for_ticker != BUY_SIGNAL:
                if auto_trade_qty <= 0:
                    auto_trade_status_message = "Automático: La cantidad debe ser positiva."
                    return auto_trade_status_message, [dbc.Alert("❌ No se puede operar con una cantidad no positiva.", color="danger", dismissable=True)], "", state.portfolio["closed_trades"]

                notification_message, notification_color = state._buy_stock(current_ticker_in_input, auto_trade_qty, now_price)
                if notification_color == "success":
                    state.latest_data["last_auto_trade_rec"][current_ticker_in_input] = BUY_SIGNAL
                    notification_list.append(dbc.Alert(f"🤖 {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
                else:
                    auto_trade_status_message = f"Automático: {notification_message}"
                    notification_list.append(dbc.Alert(f"❌ {notification_message}", color=notification_color, dismissable=True, className="mt-2"))

        elif rec == SELL_SIGNAL:
            if last_auto_rec_for_ticker != SELL_SIGNAL:
                if auto_trade_qty <= 0:
                    auto_trade_status_message = "Automático: La cantidad debe ser positiva."
                    return auto_trade_status_message, [dbc.Alert("❌ No se puede operar con una cantidad no positiva.", color="danger", dismissable=True)], "", state.portfolio["closed_trades"]

                notification_message, notification_color, realized_pnl = state._sell_stock(current_ticker_in_input, auto_trade_qty, now_price)
                if notification_color == "success":
                    realized_pnl_message = f"💰 Ganancia/Pérdida Realizada por Venta Automática de {current_ticker_in_input}: ${realized_pnl:.2f}"
                    state.latest_data["last_auto_trade_rec"][current_ticker_in_input] = SELL_SIGNAL
                    notification_list.append(dbc.Alert(f"🤖 {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
                else:
                    auto_trade_status_message = f"Automático: {notification_message}"
                    notification_list.append(dbc.Alert(f"❌ {notification_message}", color=notification_color, dismissable=True, className="mt-2"))
        else:
            state.latest_data["last_auto_trade_rec"][current_ticker_in_input] = rec
            auto_trade_status_message = f"Automático: {rec} para {current_ticker_in_input}. Esperando señal de compra/venta."

        return auto_trade_status_message, notification_list, realized_pnl_message, state.portfolio["closed_trades"]
    
    @app.callback(
        Output('notification-container', 'children', allow_duplicate=True),
        Input('stop-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def stop_app(n_clicks):
        if n_clicks > 0:
            print("Deteniendo la aplicación...")
            os._exit(0)
        return dash.no_update
        
    # --------------------------------------------------------------
    # 1.  Run the back-test, return results + toast + button state
    # --------------------------------------------------------------
    @app.callback(
        Output('bt-loading',        'style'),
        Output('bt-summary',        'children'),
        Output('bt-closed-trades',  'data'),
        Output('notification-container', 'children', allow_duplicate=True),
        Output('bt-run',            'disabled'),
        Output('bt-lock',          'data'),
        Input('bt-run',             'n_clicks'),
        State('bt-start',           'date'),
        State('bt-end',             'date'),
        State('bt-interval',        'value'),
        State('ticker',             'value'),
        prevent_initial_call=True
    )
    def run_and_display_backtest(n_clicks, start, end, interval, ticker):
        if not (start and end and ticker and interval):
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        lock_flag = True
        # show spinner + disable button
        loading_style = {"display": "block"}
        disabled_flag = True

        result = run_backtest(ticker.strip().upper(), start, end, interval)

        if result is None:
            summary_table = html.Div("No data for the selected range / ticker.")
            trades_data   = []
            toast         = dbc.Alert(
                "No price data for the chosen period / ticker / interval",
                color="warning",
                dismissable=True,
                className="mt-2"
            )
        else:
            summary_table = dbc.Table(
                [
                    html.Tr([html.Td("Net Profit %"),      html.Td(f"{result['profit_pct']} %")]),
                    html.Tr([html.Td("Total Trades"),      html.Td(result['trades'])]),
                    html.Tr([html.Td("Money Spent"),       html.Td(f"${result['money_spent']}")]),
                    html.Tr([html.Td("Money Retrieved"),   html.Td(f"${result['money_retrieved']}")]),
                    html.Tr([html.Td("Shares Still Held"), html.Td(result['shares_left'])])
                ],
                bordered=True, color="dark", className="mb-3"
            )
            trades_data = result["closed_trades"] or []
            toast        = []   # no toast on success

        # hide spinner + enable button
        loading_style = {"display": "none"}
        disabled_flag = False
        lock_flag = False

        return loading_style, summary_table, trades_data, toast, disabled_flag, lock_flag

    # --------------------------------------------------------------
    # 2.  (Optional) keep the cache in bt-store – unchanged
    # --------------------------------------------------------------
    @app.callback(
        Output('bt-store', 'data'),
        Input('bt-run',      'n_clicks'),
        State('bt-start',    'date'),
        State('bt-end',      'date'),
        State('bt-interval', 'value'),
        State('ticker',      'value'),
        prevent_initial_call=True
    )
    def cache_backtest_result(n_clicks, start, end, interval, ticker):
        if not (start and end and interval and ticker):
            return dash.no_update
        return run_backtest(ticker.strip().upper(), start, end, interval)