import random
import json
import os
from deap import base, creator, tools, algorithms
from typing import Dict, Any, List, Tuple
from backtest_engine import run_backtest
from constants import popular_tickers
from config_editor import get_dict, update_dict, persist_config

OPTIMIZER_STATE_FILE = "optimizer_state.json"
N_TICKERS = 3  # Number of random tickers per evaluation
N_DAYS = 60
INTERVAL = "5m"

CONFIG_RANGES = {
    "COEF_BOLLINGER": (0.5, 2.0),
    "COEF_RSI": (0.5, 3.0),
    "COEF_MACD": (0.5, 3.0),
    "COEF_STOCH": (0.5, 3.0),
    "COEF_ADX_SMA": (0.5, 2.0),
    "COEF_VOLUME": (0.5, 2.0),
    "ADX_TREND_THRESHOLD": (10, 40),
    "BUY_SELL_THRESHOLD": (0.5, 2.5),
    "RSI_OVERBOUGHT": (60, 80),
    "RSI_OVERSOLD": (10, 40),
    "STOCH_OVERBOUGHT": (70, 90),
    "STOCH_OVERSOLD": (10, 40),
    "VOLUME_SMA_MULTIPLIER": (1.0, 3.0),
}

def load_state() -> Dict[str, Any]:
    if os.path.exists(OPTIMIZER_STATE_FILE):
        with open(OPTIMIZER_STATE_FILE, "r") as f:
            return json.load(f)
    return {"best": None, "history": []}

def save_state(state: Dict[str, Any]) -> None:
    with open(OPTIMIZER_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

creator.create("FitnessMax", base.Fitness, weights=(1.0, 0.1, 0.1))
creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()
toolbox.register("attr_float", lambda low, high: random.uniform(low, high))
toolbox.register(
    "individual",
    tools.initCycle,
    creator.Individual,
    [lambda: toolbox.attr_float(*CONFIG_RANGES[k]) for k in CONFIG_RANGES],
    n=1,
)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.2, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)

def evaluate(individual: List[float]) -> Tuple[float, int, float]:
    config = {k: v for k, v in zip(CONFIG_RANGES.keys(), individual)}
    tickers = random.sample(popular_tickers, N_TICKERS)
    total_profit = 0
    total_trades = 0
    total_loss = 0
    for ticker in tickers:
        result = run_backtest(
            ticker,
            start=None,
            end=None,
            interval=INTERVAL,
            cfg_hash="",
            config=config
        )
        profit = result.get("profit_pct", 0)
        trades = result.get("trades", 0)
        loss = min(0, profit)
        total_profit += profit
        total_trades += trades
        total_loss += abs(loss)
    score = total_profit - 0 * total_loss + 0.0 * total_trades
    avg_profit = total_profit / N_TICKERS if N_TICKERS else 0
    avg_trades = total_trades / N_TICKERS if N_TICKERS else 0
    return (score, avg_trades, avg_profit)
toolbox.register("evaluate", evaluate)

def run_optimizer(n_generations=20, pop_size=10, config_ranges=None):
    if config_ranges is not None:
        ranges = config_ranges
    else:
        ranges = CONFIG_RANGES
    # Use 'ranges' instead of 'CONFIG_RANGES' in individual creation
    toolbox.register(
        "individual",
        tools.initCycle,
        creator.Individual,
        [lambda: toolbox.attr_float(*ranges[k]) for k in ranges],
        n=1,
    )
    state = load_state()
    pop = toolbox.population(n=pop_size)
    hof = tools.HallOfFame(1)
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda x: sum(v[0] for v in x)/len(x))
    stats.register("max", lambda x: max(v[0] for v in x))
    stats.register("min", lambda x: min(v[0] for v in x))
    print("Optimizer started...")
    for gen in range(n_generations):
        print(f"Generation {gen+1} running...")
        pop, log = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=1, 
                                       stats=stats, halloffame=hof, verbose=False)
        best_ind = hof[0]
        best_score, best_trades, best_profit = best_ind.fitness.values
        best_config = {k: v for k, v in zip(CONFIG_RANGES.keys(), best_ind)}
        state["history"].append({
            "gen": gen+1,
            "score": best_score,
            "config": best_config,
            "trades": best_trades,
            "profit_pct": best_profit
        })
        if state.get("best") is None or best_score > state["best"]["score"]:
            state["best"] = {
                "score": best_score,
                "config": best_config,
                "trades": best_trades,
                "profit_pct": best_profit
            }
            print(f"New best config found: {best_config} with score {best_score}, trades {best_trades}, profit % {best_profit}")
        save_state(state)
    print("Optimization finished. Best config:", state["best"])
    return state["best"]

def get_optimizer_progress() -> Dict[str, Any]:
    state = load_state()
    history = state.get("history", [])
    best = state.get("best", {})
    progress = {
        "iterations": len(history),
        "best_score": best.get("score"),
        "best_config": best.get("config"),
        "last_score": history[-1]["score"] if history else None,
        "last_config": history[-1]["config"] if history else None,
        "history": history[-10:],
    }
    return progress

def reset_optimizer_state():
    if os.path.exists(OPTIMIZER_STATE_FILE):
        os.remove(OPTIMIZER_STATE_FILE)

def apply_best_config():
    state = load_state()
    best = state.get("best")
    if best and "config" in best:
        update_dict(best["config"])
        persist_config()
        return True
    return False