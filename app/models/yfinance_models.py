""" Yfinance models for the application. """
from typing import Optional
from pydantic import BaseModel


class TickerSearchReference(BaseModel):
    """ A reference to a ticker search result. """
    symbol: str
    shortname: Optional[str] = None
    typeDisp: Optional[str] = None
    exchDisp: Optional[str] = None
    exchange: Optional[str] = None
    quoteType: Optional[str] = None
    longname: Optional[str] = None
    index: Optional[str] = None
    score: Optional[float] = None
    isYahooFinance: Optional[bool] = None


class TickerInfo(BaseModel):
    """ A model for ticker information. """
    symbol: str
    quoteType: str
    typeDisp: str
    currency: str
    exchange: str
    expireIsoDate: Optional[str] = None
