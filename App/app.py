# app.py

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from .layout import serve_layout
from .callbacks import register_callbacks

# Dash app setup
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.DARKLY])
app.title = "Análisis Técnico y Simulador de Trading"

# Set the layout
app.layout = serve_layout()

# Register all callbacks from the callbacks module
register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False,open_browser = True)