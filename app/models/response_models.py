""" Custom response models for the application. """

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
from pydantic import BaseModel


@dataclass
class TimeSeriesData():
    """Type definition for time series data structure."""
    date: List[str]
    close: List[float]
    close_fitted: List[float]
    long_term_deviation: List[float]
    long_term_deviation_z: List[float]
    log_returns: List[float]
    rolling_return_1w: List[float]
    rolling_return_z_score_1w: List[float]
    rolling_return_1m: List[float]
    rolling_return_z_score_1m: List[float]
    rolling_return_1y: List[float]
    rolling_return_z_score_1y: List[float]

    def to_dict(self) -> dict:
        """ Convert to dictionary. """
        return {
            "date": self.date,
            "close": self.close,
            "close_fitted": self.close_fitted,
            "long_term_deviation": self.long_term_deviation,
            "long_term_deviation_z": self.long_term_deviation_z,
            "log_returns": self.log_returns,
            "rolling_return_1w": self.rolling_return_1w,
            "rolling_return_z_score_1w": self.rolling_return_z_score_1w,
            "rolling_return_1m": self.rolling_return_1m,
            "rolling_return_z_score_1m": self.rolling_return_z_score_1m,
            "rolling_return_1y": self.rolling_return_1y,
            "rolling_return_z_score_1y": self.rolling_return_z_score_1y
        }


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
    time_series_data: Optional[dict] = None
    error_msg: Optional[str] = None
    cagr: Optional[float] = None
    cagr_fitted: Optional[float] = None
    long_term_deviation_rmse: Optional[float] = None
    long_term_deviation_rmse_normalized: Optional[float] = None
    returns_mean_annualized: Optional[float] = None
    returns_std_annualized: Optional[float] = None
    returns_cv: Optional[float] = None
    max_drawdown: Optional[float] = None

    @classmethod
    def from_cache_data(cls, cache_dict: dict) -> "TickerMetricsResponse":
        """ Convert cached data to TickerMetricsResponse. """
        # Check if this is an error response
        if cache_dict["error_msg"]:
            return cls(**cache_dict)

        # Get data from cache
        ticker = cache_dict["ticker"]
        info = cache_dict["info"]
        prices = pd.Series(
            cache_dict["time_series_data"]["close"], index=cache_dict["time_series_data"]["date"])
        prices.index = pd.to_datetime(prices.index)

        # lets do some processing

        fitted_values = pd.Series(
            data=_get_fitted_values(prices.values.tolist()),
            index=prices.index
        )

        long_term_deviation = prices / fitted_values - 1
        long_term_deviation_z = (
            long_term_deviation - long_term_deviation.mean()
        ) / long_term_deviation.std()

        long_term_deviation_rmse: float = np.sqrt(
            np.mean((long_term_deviation) ** 2))

        long_term_deviation_rmse_normalized: float = long_term_deviation_rmse / \
            np.mean(np.abs(long_term_deviation))

        points = len(prices)
        total_days = (prices.index[-1] - prices.index[0]).days + 1
        total_years = total_days / 365.25
        points_per_day = points / total_days
        points_per_week = points_per_day*7
        points_per_month = points_per_day*365.25/12
        points_per_year = points_per_day*365.25

        cagr: float = (prices.iloc[-1] / prices.iloc[0]
                       ) ** (1 / total_years) - 1
        cagr_fitted: float = (
            fitted_values.iloc[-1] / fitted_values.iloc[0]) ** (1 / total_years) - 1

        log_returns = np.log(prices / prices.shift(1))
        log_returns_clean = log_returns.dropna()

        # log_returns_mean = np.mean(log_returns_clean)
        # log_returns_std = np.std(log_returns_clean)
        # log_returns_mean_annualized = log_returns_mean * points_per_year
        # log_returns_std_annualized = log_returns_std * np.sqrt(points_per_year)
        # log_returns_to_risk_ratio_annualized = log_returns_mean_annualized / \
        #     log_returns_std_annualized

        rolling_return_1w, rolling_return_z_score_1w = cls._calculate_rolling_stats(
            log_returns_clean, points_per_week)

        rolling_return_1m, rolling_return_z_score_1m = cls._calculate_rolling_stats(
            log_returns_clean, points_per_month)

        rolling_return_1y, rolling_return_z_score_1y = cls._calculate_rolling_stats(
            log_returns_clean, points_per_year)

        # Build time series dictionary
        time_series_dict = TimeSeriesData(
            date=[date.isoformat().split("T")[0] for date in prices.index],
            close=prices.values.tolist(),
            close_fitted=fitted_values.tolist(),
            long_term_deviation=long_term_deviation.values.tolist(),
            long_term_deviation_z=long_term_deviation_z.values.tolist(),
            log_returns=log_returns.values.tolist(),

            rolling_return_1w=rolling_return_1w.values.tolist(),
            rolling_return_z_score_1w=rolling_return_z_score_1w.values.tolist(),
            rolling_return_1m=rolling_return_1m.values.tolist(),
            rolling_return_z_score_1m=rolling_return_z_score_1m.values.tolist(),
            rolling_return_1y=rolling_return_1y.values.tolist(),
            rolling_return_z_score_1y=rolling_return_z_score_1y.values.tolist()
        ).to_dict()

        returns = prices.pct_change().dropna()

        returns_mean = returns.mean()
        returns_std = returns.std()

        # Avoid division by zero
        if returns_std == 0:
            returns_cv = 999
        else:
            returns_cv = returns_std/returns_mean
        drawdown = (prices / prices.cummax()) - 1
        max_drawdown = drawdown.min()

        return cls(
            ticker=ticker,
            info=info,
            time_series_data=time_series_dict,
            error_msg=None,
            cagr=cagr,
            cagr_fitted=cagr_fitted,
            long_term_deviation_rmse=long_term_deviation_rmse,
            long_term_deviation_rmse_normalized=long_term_deviation_rmse_normalized,

            returns_mean_annualized=round(returns_mean*points_per_year, 4),
            returns_std_annualized=round(
                returns_std*np.sqrt(points_per_year), 4),
            returns_cv=round(returns_cv, 4),
            max_drawdown=round(max_drawdown, 4)
        )

    @classmethod
    def to_cached_data(cls,
                       ticker: str,
                       close_prices: Optional[pd.Series] = None,
                       info: Optional[dict] = None,
                       error_msg: Optional[str] = None) -> "TickerMetricsResponse":
        """ Convert to cached data. """
        if error_msg is not None:
            return cls(ticker=ticker, error_msg=error_msg)

        return cls(
            ticker=ticker,
            info=info,
            time_series_data={
                "date": [date.isoformat().split("T")[0] for date in close_prices.index],
                "close": close_prices.values.tolist()
            }
        )

    @classmethod
    def _calculate_rolling_stats(cls, log_returns: pd.Series, window_size: int):

        rolling = log_returns.rolling(window=round(window_size))

        rolling_sum = rolling.sum()
        rolling_return: pd.Series = np.exp(rolling_sum) - 1
        rolling_return_z_score: pd.Series = (
            rolling_return - rolling_return.mean()) / rolling_return.std()

        return rolling_return, rolling_return_z_score


class EnhancedAssetPosition(BaseModel):
    """Enhanced asset position with yfinance data."""
    # Original position data
    id: Optional[int]
    ticker: str
    quantity: float
    user_id: int

    # Enhanced yfinance data
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    ticker_info: Optional[Dict[str, Any]] = None
    historical_data: Optional[Dict[str, List[float]]] = None
    error: Optional[str] = None


class PortfolioMarketData(BaseModel):
    """Market data for portfolio with aligned time series."""
    tickers: List[str]
    infos: List[Dict[str, Any]]
    # keys: "dates" (List[str]) + ticker symbols (List[float])
    timeseries_data: Dict[str, List[Any]]
    # position info: ticker, quantity, market_value
    positions: List[Dict[str, Any]]
    total_market_value: Optional[float] = None
    last_updated: str


class EnhancedPortfolioResponse(BaseModel):
    """Response model for enhanced portfolio with market data."""
    positions: List[EnhancedAssetPosition]
    total_market_value: Optional[float] = None
    last_updated: str
