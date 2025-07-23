""" Custom response models for the application. """
from typing import Optional, TypedDict, List
import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.utils import calculate_risk_from_prices


class TimeSeriesData(TypedDict):
    """Type definition for time series data structure."""
    date: List[str]
    close: List[float]
    close_fitted: List[float]
    long_term_deviation: List[float]
    long_term_deviation_z: List[float]
    log_returns: List[float]


def _get_fitted_values(values: list[float]) -> np.ndarray:
    """ Get fitted values for a list of values using exponential trend. """
    x = np.arange(len(values))
    y_log = np.log(values)
    z_exp = np.polyfit(x, y_log, 1)
    p_exp = np.poly1d(z_exp)
    y_exp = np.exp(p_exp(x))
    return y_exp


class TickerMetricsResponse(BaseModel):
    """ Response model for risk metrics calculation. """
    ticker: str
    info: Optional[dict] = None
    time_series_data: Optional[TimeSeriesData] = None
    mean_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    error_msg: Optional[str] = None

    @classmethod
    def from_ticker_data(
        cls,
        ticker: str,
        prices: pd.Series,
        info: dict
    ) -> "TickerMetricsResponse":
        """
        Create TickerMetricsResponse from raw ticker data with all time series processing.

        Args:
            ticker: Stock ticker symbol
            prices: Series of closing prices with datetime index
            info: Ticker info from yfinance

        Returns:
            Fully populated TickerMetricsResponse instance
        """
        # Calculate time series metrics
        log_returns = np.log(prices / prices.shift(1))

        fitted_values = pd.Series(
            data=_get_fitted_values(prices.values.tolist()),
            index=prices.index
        )

        long_term_deviation = prices / fitted_values - 1
        long_term_deviation_z = (
            long_term_deviation - long_term_deviation.mean()
        ) / long_term_deviation.std()

        # Build time series dictionary
        time_series_dict: TimeSeriesData = {
            "date": [date.isoformat().split("T")[0] for date in prices.index],
            "close": prices.values.tolist(),
            "close_fitted": fitted_values.tolist(),
            "long_term_deviation": long_term_deviation.values.tolist(),
            "long_term_deviation_z": long_term_deviation_z.values.tolist(),
            "log_returns": log_returns.values.tolist()
        }

        # Calculate risk metrics
        risk_metrics = calculate_risk_from_prices(prices)

        return cls(
            ticker=ticker,
            info=info,
            time_series_data=time_series_dict,
            mean_return=risk_metrics["mean_return"],
            volatility=risk_metrics["volatility"],
            sharpe_ratio=risk_metrics["sharpe_ratio"],
            max_drawdown=risk_metrics["max_drawdown"],
            error_msg=None
        )

    @classmethod
    def create_error_response(cls, ticker: str, error_msg: str) -> "TickerMetricsResponse":
        """Create an error response for failed ticker requests."""
        return cls(
            ticker=ticker,
            info=None,
            time_series_data=None,
            mean_return=None,
            volatility=None,
            sharpe_ratio=None,
            max_drawdown=None,
            error_msg=error_msg
        )
