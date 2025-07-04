""" Routes for risk metrics calculation. """
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from .models import PriceInput, TickerInput
from .utils import calculate_risk_from_prices

router = APIRouter()


@router.post("/risk_metrics")
def risk_from_prices(data: PriceInput):
    """ Calculate risk metrics from a list of prices. """
    prices = pd.Series(data.prices)

    if len(prices) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 prices required")

    return calculate_risk_from_prices(prices)


@router.post("/risk_metrics_from_ticker")
def risk_from_ticker(ticker_input: TickerInput):
    """ Calculate risk metrics from a stock ticker. """
    ticker = ticker_input.ticker.upper()
    try:
        df = yf.download(ticker, period="6mo")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if df.empty:
        raise HTTPException(status_code=404, detail="No data found")

    prices = df["Close"].dropna()
    if len(prices) < 2:
        raise HTTPException(status_code=400, detail="Not enough data")

    return {
        "ticker": ticker,
        **calculate_risk_from_prices(prices)
    }
