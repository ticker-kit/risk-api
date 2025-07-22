""" Custom response models for the application. """
from typing import Optional
from pydantic import BaseModel


class TickerMetricsResponse(BaseModel):
    """ Response model for risk metrics calculation. """
    ticker: str
    info: Optional[dict] = None
    prices: Optional[dict] = None
    mean_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    error_msg: Optional[str] = None
