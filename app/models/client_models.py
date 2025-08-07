""" Client models for the application. """
from typing import Optional
from pydantic import BaseModel
from app.yfinance_service import yfinance_service


class AssetPositionRequest(BaseModel):
    """ Asset position request model for the database. """
    ticker: str
    quantity: float


class AssetPositionWithInfo(BaseModel):
    """ Asset position with info model for the client. """
    ticker: str
    quantity: float

    symbol: str
    currency: str
    previousClose: float
    bid: float
    ask: float
    regularMarketPrice: float
    quoteType: str
    typeDisp: str
    longName: str
    shortName: str
    fullExchangeName: str

    legalType: Optional[str]
    fundFamily: Optional[str]

    @classmethod
    async def add_info(cls, ticker: str, quantity: float):
        """ Add info to the asset position. """
        info = await yfinance_service.get_ticker_info(ticker)

        return cls(
            ticker=ticker,
            quantity=quantity,
            symbol=info.get('symbol'),
            currency=info.get('currency'),
            previousClose=info.get('previousClose'),
            bid=info.get('bid'),
            ask=info.get('ask'),
            regularMarketPrice=info.get('regularMarketPrice'),
            quoteType=info.get('quoteType'),
            typeDisp=info.get('typeDisp'),
            longName=info.get('longName'),
            shortName=info.get('shortName'),
            fundFamily=info.get('fundFamily'),
            fullExchangeName=info.get('fullExchangeName'),
            legalType=info.get('legalType'),
        )
