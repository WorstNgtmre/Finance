# app.py

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from layout import serve_layout
from callbacks import register_callbacks
import threading
import webbrowser
import time

# Dash app setup
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.DARKLY])
app.title = "Análisis Técnico y Simulador de Trading"

# Set the layout
app.layout = serve_layout()

# Register all callbacks from the callbacks module
register_callbacks(app)

def open_browser():
    """Abre el navegador después de un pequeño retraso para dar tiempo a que el servidor se inicie."""
    time.sleep(1)
    webbrowser.open_new("http://127.0.0.1:8050")

if __name__ == "__main__":
    # Inicia un hilo para abrir el navegador
    threading.Thread(target=open_browser).start()
    app.run(debug=False)