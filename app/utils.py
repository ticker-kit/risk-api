""" Utility functions for risk metrics calculation. """
import pandas as pd


def calculate_risk_from_prices(prices: pd.Series):
    """ Calculate risk metrics from a series of prices. """
    returns = prices.pct_change().dropna()

    mean_return = returns.mean()
    volatility = returns.std()

    sharpe_ratio = mean_return / volatility
    drawdown = (prices / prices.cummax()) - 1
    max_drawdown = drawdown.min()

    return {
        "mean_return": round(float(mean_return), 4),
        "volatility": round(float(volatility), 4),
        "sharpe_ratio": round(float(sharpe_ratio), 2),
        "max_drawdown": round(float(max_drawdown), 4)
    }
