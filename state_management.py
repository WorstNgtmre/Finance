# state_management.py

import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from config import FILE_PATH, BUY_SIGNAL, SELL_SIGNAL
from data_processing import get_or_update_data

class TraderState:
    def __init__(self):
        self.initial_portfolio_state = {
            "cash": 100000.0, "stocks": {}, "initial_cash": 100000.0, "closed_trades": []
        }
        self.portfolio = self._load_portfolio()
        self.latest_data = {
            "ticker": None, "graphs": {}, "df": pd.DataFrame(), "rec": "",
            "analyst": "", "market_info": {}, "last_rec_for_notification": None,
            "last_auto_trade_rec": {}
        }
        
    def _load_portfolio(self) -> Dict[str, Any]:
        """
        Carga el estado del portfolio desde un archivo JSON.
        Si el archivo no existe o es inválido, devuelve el estado inicial.
        """
        if os.path.exists(FILE_PATH):
            try:
                with open(FILE_PATH, 'r') as f:
                    data = json.load(f)
                    if not all(key in data for key in ["cash", "stocks", "initial_cash", "closed_trades"]):
                        print("Advertencia: El archivo portfolio_data.json tiene un formato antiguo o inválido. Se usará el estado inicial.")
                        return self.initial_portfolio_state
                    return data
            except json.JSONDecodeError:
                print("Error al decodificar JSON desde portfolio_data.json. Se usará el estado inicial.")
                return self.initial_portfolio_state
        return self.initial_portfolio_state

    def _save_portfolio(self) -> None:
        """
        Guarda el estado del portfolio en un archivo JSON.
        """
        with open(FILE_PATH, 'w') as f:
            json.dump(self.portfolio, f, indent=4)
    
    def _buy_stock(self, ticker: str, quantity: int, price: float) -> Tuple[str, str]:
        """
        Función modular para comprar acciones.
        """
        costo_total = quantity * price
        if self.portfolio["cash"] >= costo_total:
            if ticker not in self.portfolio["stocks"]:
                self.portfolio["stocks"][ticker] = {"qty": quantity, "avg_price": price, "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            else:
                old_qty = self.portfolio["stocks"][ticker]["qty"]
                old_avg_price = self.portfolio["stocks"][ticker]["avg_price"]
                new_total_cost = (old_qty * old_avg_price) + (quantity * price)
                new_total_qty = old_qty + quantity
                self.portfolio["stocks"][ticker]["qty"] = new_total_qty
                self.portfolio["stocks"][ticker]["avg_price"] = new_total_cost / new_total_qty

            self.portfolio["cash"] -= costo_total
            self._save_portfolio()
            notification_message = f"✅ Compradas {quantity} acciones de {ticker} a ${price:.2f} cada una."
            return notification_message, "success"
        else:
            notification_message = "❌ Fondos insuficientes para realizar la compra."
            return notification_message, "danger"

    def _sell_stock(self, ticker: str, quantity: int, price: float) -> Tuple[str, str, float]:
        """
        Función modular para vender acciones.
        """
        if ticker in self.portfolio["stocks"] and self.portfolio["stocks"][ticker]["qty"] >= quantity:
            avg_buy_price = self.portfolio["stocks"][ticker]["avg_price"]
            realized_pnl = (price - avg_buy_price) * quantity

            self.portfolio["cash"] += quantity * price

            self.portfolio["closed_trades"].append({
                "Fecha Venta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Cantidad": quantity,
                "Precio Compra Promedio": round(avg_buy_price, 2),
                "Precio Venta": round(price, 2),
                "Ganancia/Pérdida Realizada": round(realized_pnl, 2)
            })

            self.portfolio["stocks"][ticker]["qty"] -= quantity
            if self.portfolio["stocks"][ticker]["qty"] == 0:
                del self.portfolio["stocks"][ticker]

            self._save_portfolio()
            notification_message = f"✅ Vendidas {quantity} acciones de {ticker} a ${price:.2f} cada una."
            return notification_message, "success", realized_pnl
        else:
            notification_message = "❌ No tienes suficientes acciones para vender."
            return notification_message, "danger", 0.0
    
    def reset_portfolio(self) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Resetea el portfolio a los valores iniciales.
        """
        self.portfolio["cash"] = self.initial_portfolio_state["initial_cash"]
        self.portfolio["stocks"] = {}
        self.portfolio["closed_trades"] = []
        self._save_portfolio()
        return "🔄 Cartera reseteada a los valores iniciales.", "info", []

    def update_latest_data(self, ticker, rec, analyst, df, graphs, market_info, long_name):
        self.latest_data.update({
            "ticker": ticker,
            "graphs": graphs,
            "df": df,
            "rec": rec,
            "analyst": analyst,
            "market_info": market_info,
            "last_rec_for_notification": rec
        })

    def get_portfolio_data(self) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Genera el texto de la cartera y los datos de la tabla de posiciones abiertas.
        """
        if self.latest_data["df"].empty:
            total_valor = self.portfolio["cash"]
            cartera_txt = f"💰 Efectivo: ${self.portfolio['cash']:.2f} | 📦 Acciones: 0 | 💼 Valor total: ${total_valor:.2f} | 📈 Ganancia/Pérdida: 0.00% "
            return cartera_txt, []

        now_price = self.latest_data["df"]["Close"].iloc[-1]

        total_valor_acciones = sum(
            (now_price * stock_info['qty'])
            for stock_info in self.portfolio["stocks"].values()
        )
        total_valor = self.portfolio["cash"] + total_valor_acciones

        pnl_percentage = ((total_valor - self.portfolio["initial_cash"]) / self.portfolio["initial_cash"]) * 100 if self.portfolio["initial_cash"] > 0 else 0

        open_positions_data = []
        for ticker_held, stock_info in self.portfolio["stocks"].items():
            unrealized_pnl = (now_price - stock_info["avg_price"]) * stock_info["qty"]
            open_positions_data.append({
                "Fecha Compra": stock_info.get("buy_date", "N/A"),
                "Ticker": ticker_held,
                "Cantidad": stock_info["qty"],
                "Precio Compra Promedio": round(stock_info["avg_price"], 2),
                "Ganancia/Pérdida (No Realizada)": round(unrealized_pnl, 2)
            })

        cartera_txt = f"💰 Efectivo: ${self.portfolio['cash']:.2f} | 📦 Acciones: {sum(stock_info['qty'] for stock_info in self.portfolio['stocks'].values())} | 💼 Valor total: ${total_valor:.2f} | 📈 Ganancia/Pérdida: {pnl_percentage:.2f}% "

        return cartera_txt, open_positions_data