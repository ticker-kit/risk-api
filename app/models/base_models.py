"""Base model for asset analysis"""
from typing import Optional
import numpy as np
import logging
import pandas as pd
from app.yfinance_service import yfinance_service
from app.models.asset_period import AssetPeriod
from app.functions.stat_functions import get_fitted_values

logger = logging.getLogger(__name__)


async def create_asset_analysis(ticker: str, period: str = "1wk"):
    """Create an asset analysis instance"""
    asset_analysis = AssetAnalysis(ticker, period)
    await asset_analysis.init()
    return asset_analysis


class CloseFitted():
    """Close fitted data"""
    # column names: Close, Close_Fitted, Fitted_Errors, Fitted_Errors_z
    table: pd.DataFrame
    rmse: float
    rmse_adj: float
    cagr_fitted: float


class AssetAnalysis():
    """Base model for asset analysis"""

    def __init__(self, ticker: str, period: str = "1wk"):
        if not ticker.strip():
            raise ValueError("Ticker is required")

        if ticker != ticker.upper().strip():
            raise ValueError("Ticker must be in uppercase")

        self.__ticker = ticker
        self.__period = period

        self.__info: Optional[dict] = None
        # columns': ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
        self.__history: Optional[pd.DataFrame] = None
        self.__expires: bool = False
        self.__has_negative_close: bool = False

        self.__cagr: Optional[float] = None

        self.__close_fitted: Optional[CloseFitted] = None

    async def init(self):
        """Initialize the asset analysis"""
        try:
            self.__info = await yfinance_service.get_ticker_info(self.__ticker)

            self.__history = await yfinance_service.get_historical_data(self.__ticker, self.__period)

            self.__expires = self.__info.get('expireIsoDate') is not None

            self.__has_negative_close = self.__history['Close'].dropna(
            )[self.__history['Close'].dropna() <= 0].size > 0

            if not self.__has_negative_close:
                self.__cagr = (self.__history['Close'].iloc[-1] / self.__history['Close'].iloc[0]
                               ) ** (1 / self.get_period().years) - 1
        except Exception as e:
            msg = f"Error: initializing asset analysis for {self.__ticker}"
            logger.error("%s: %s", msg, str(e))
            raise Exception(msg) from e

    def get_ticker(self):
        """Returns the ticker"""
        return self.__ticker

    def get_info(self):
        """Returns the ticker info"""
        return self.__info

    def get_history(self):
        """Returns the historical data"""
        return self.__history

    def get_period(self):
        """Returns the period of the asset"""
        if self.__history is None:
            raise ValueError("History is not initialized")

        if self.__history.index.empty:
            raise ValueError("History index is empty")

        if not self.__history.index.is_unique:
            raise ValueError("History index is not unique")

        # if not self.__history.index.is_monotonic_increasing:
        #     raise ValueError("History index is not monotonic increasing")

        if not str(self.__history.index.dtype).startswith('datetime64'):
            raise ValueError("History index is not datetime64")

        return AssetPeriod.from_date_index(self.__history.index)

    def get_close_fitted(self):
        """Returns the fitted close values"""
        if self.__close_fitted is not None:
            return self.__close_fitted

        if self.__history is None:
            return None

        if self.__expires or self.__has_negative_close:
            return None

        close_values = self.__history['Close'].values.tolist()
        y_exp, _ = get_fitted_values(close_values)

        cagr_fitted = (y_exp[-1] / y_exp[0]) ** (1 /
                                                 self.get_period().years) - 1

        fitted_errors = close_values / y_exp - 1
        fitted_errors_z = (
            fitted_errors - fitted_errors.mean()) / fitted_errors.std()

        fitted_errors_rmse: float = np.sqrt(np.mean((fitted_errors) ** 2))
        fitted_errors_rmse_adj = fitted_errors_rmse / np.mean(y_exp)

        self.__close_fitted = {
            'table': pd.DataFrame(
                data={
                    'Close': close_values,
                    'Close_Fitted': y_exp,
                    'Fitted_Errors': fitted_errors,
                    'Fitted_Errors_z': fitted_errors_z
                },
                index=self.__history.index
            ),
            'rmse': fitted_errors_rmse,
            'rmse_adj': fitted_errors_rmse_adj,
            'cagr_fitted': cagr_fitted
        }

        return self.__close_fitted

    def get_log_returns(self):
        """Returns the log returns"""

        if self.__has_negative_close:
            return None

        log_returns = np.log(
            self.__history['Close'] / self.__history['Close'].shift(1))

        log_returns.name = "log_returns"

        log_returns_clean = log_returns.dropna()

        period_class = self.get_period()

        rolling_return_1w, rolling_return_z_score_1w = self.__calculate_rolling_stats(
            log_returns_clean, period_class.points_per_week, "1w")

        rolling_return_1m, rolling_return_z_score_1m = self.__calculate_rolling_stats(
            log_returns_clean, period_class.points_per_month, "1m")

        rolling_return_1y, rolling_return_z_score_1y = self.__calculate_rolling_stats(
            log_returns_clean, period_class.points_per_year, "1y")

        return pd.concat([log_returns,
                          rolling_return_1w, rolling_return_z_score_1w,
                          rolling_return_1m, rolling_return_z_score_1m,
                          rolling_return_1y, rolling_return_z_score_1y], axis=1)

    def to_asset_analysis_response(self):
        """Convert the asset analysis to a response model"""

        cf = self.get_close_fitted()
        log_returns = self.get_log_returns()

        tables = [
            ('date', self.__history.index.tolist()),
            ('close', self.__history['Close'].values.tolist()),
            ('close_fitted', cf['table']['Close_Fitted'].values.tolist()
                if cf is not None else None),
            ('long_term_deviation', cf['table']['Fitted_Errors'].values.tolist()
                if cf is not None else None),
            ('long_term_deviation_z', cf['table']['Fitted_Errors_z'].values.tolist()
                if cf is not None else None),
            ('log_returns', log_returns['log_returns'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_1w', log_returns['rolling_return_1w'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_z_score_1w', log_returns['rolling_return_z_score_1w'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_1m', log_returns['rolling_return_1m'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_z_score_1m', log_returns['rolling_return_z_score_1m'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_1y', log_returns['rolling_return_1y'].values.tolist(
            ) if log_returns is not None else None),
            ('rolling_return_z_score_1y', log_returns['rolling_return_z_score_1y'].values.tolist(
            ) if log_returns is not None else None)
        ]

        return {
            "ticker": self.__ticker,
            "info": self.__info,
            "expires": self.__expires,
            "has_negative_close": self.__has_negative_close,
            "cagr": self.__cagr,
            "time_series_data": {k: v for k, v in tables if v is not None},
            "cagr_fitted": cf['cagr_fitted'] if cf is not None else None
        }

    def __calculate_rolling_stats(self, log_returns: pd.Series, window_size: int, name_suffix: str | None = None):
        rolling = log_returns.rolling(window=round(window_size))

        rolling_sum = rolling.sum()
        rolling_return: pd.Series = np.exp(rolling_sum) - 1

        rolling_return_z_score: pd.Series = (
            rolling_return - rolling_return.mean()) / rolling_return.std()

        if name_suffix is not None:
            rolling_return.name = f"rolling_return_{name_suffix}"
            rolling_return_z_score.name = f"rolling_return_z_score_{name_suffix}"

        return rolling_return, rolling_return_z_score
