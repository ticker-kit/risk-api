""" Routes for risk metrics calculation. """
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from app.models.models import PriceInput, TickerInput
from app.utils import calculate_risk_from_prices

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
    ticker = ticker_input.ticker.upper().strip()

    # Basic ticker validation
    if not ticker or len(ticker) > 10:
        raise HTTPException(
            status_code=400, detail="Invalid ticker: must be 1-10 characters")

    # Only allow alphanumeric characters and dots
    if not all(c.isalnum() or c == '.' or c == '^' for c in ticker):
        raise HTTPException(
            status_code=400, detail="Invalid ticker: only letters, numbers, dots, and ^ allowed")

    try:
        df = yf.download(ticker, period="6mo", progress=False)
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid" in error_msg or "not found" in error_msg:
            raise HTTPException(
                status_code=404, detail=f"Ticker '{ticker}' not found") from None
        elif "timeout" in error_msg or "connection" in error_msg:
            raise HTTPException(
                status_code=503, detail="Market data service temporarily unavailable") from None
        else:
            raise HTTPException(
                status_code=500, detail="Unable to retrieve market data") from e

    if df is None or df.empty:
        raise HTTPException(
            status_code=404, detail=f"Symbol '{ticker}' does not exist")

    prices = df["Close"].dropna()
    if not isinstance(prices, pd.Series):
        raise HTTPException(status_code=500, detail="Data retrieval error")

    if len(prices) < 2:
        raise HTTPException(
            status_code=400, detail=f"Insufficient data points for '{ticker}'")

    return {
        "ticker": ticker,
        **calculate_risk_from_prices(prices)
    }
