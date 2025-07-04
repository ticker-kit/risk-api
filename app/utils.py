""" Utility functions for risk metrics calculation. """
import pandas as pd


def calculate_risk_from_prices(prices: pd.Series):
    """ Calculate risk metrics from a series of prices. """
    returns = prices.pct_change().dropna()
    volatility = returns.std()
    sharpe_ratio = returns.mean() / (volatility + 1e-8)
    drawdown = (prices / prices.cummax()) - 1
    max_drawdown = drawdown.min()

    return {
        "mean_return": round(returns.mean(), 4),
        "volatility": round(volatility, 4),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 4)
    }
