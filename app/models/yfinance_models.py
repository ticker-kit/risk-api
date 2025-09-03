""" 
Yfinance models for the application.
More fields can be added as needed.
May break if yfinance changes the fields.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


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
    longName: Optional[str] = None
    shortName: str
    quoteType: str
    typeDisp: str
    fullExchangeName: str
    longBusinessSummary: str
    quoteSourceName: str
    currency: str
    exchange: str
    region: str

    ask: Optional[float] = None
    bid: Optional[float] = None
    previousClose: Optional[float] = None
    regularMarketPrice: Optional[float] = None
    fiftyTwoWeekLow: Optional[float] = None
    fiftyTwoWeekHigh: Optional[float] = None
    country: Optional[str] = None
    beta: Optional[float] = None
    expireIsoDate: Optional[str] = None
    industryDisp: Optional[str] = None
    sectorDisp: Optional[str] = None
    longBusinessSummary: Optional[str] = None
    enterpriseValue: Optional[float] = None
    bookValue: Optional[float] = None
    marketCap: Optional[float] = None
    category: Optional[str] = None
    fundFamily: Optional[str] = None
    regularMarketChangePercent: Optional[float] = None
    volume: Optional[int] = None
    regularMarketVolume: Optional[int] = None


class HistoryDict(BaseModel):
    """
    yfinance.Ticker([TICKER]).history() 
    The above returns a pandas dataframe, but converted to dictionary we get this model.
    """
    index: List[str]

    Open: List[float]
    High: List[float]
    Low: List[float]
    Close: List[float]
    Volume: List[int]

    Dividends: Optional[List[float]] = Field(default=None)
    Stock_Splits: Optional[List[float]] = Field(
        default=None,
        alias='Stock Splits')
    Capital_Gains: Optional[List[float]] = Field(
        default=None,
        alias='Capital Gains')
