""" Routes for risk metrics calculation. """
import logging
import yfinance as yf
from fastapi import APIRouter, HTTPException

from app.models.response_models import TickerMetricsResponse
from app.redis_service import redis_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ticker/{ticker}", response_model=TickerMetricsResponse)
async def get_ticker_data(ticker: str, refresh: bool = False):
    """ Calculate risk metrics from a stock ticker. """
    ticker = ticker.upper().strip()

    # Basic ticker validation
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    cache_key = f"ticker_data:{ticker}"

    if refresh:
        await redis_service.delete_cached_data(cache_key)

    # 1. Return cached data
    cached_data = await redis_service.get_cached_data(cache_key)
    if cached_data:
        return cached_data

    try:
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period="6mo", auto_adjust=True)
        info = ticker_obj.info
    except Exception as e:
        # 2. Return error data
        logger.error(
            "Unable to retrieve yf.Ticker data for ticker: %s, error: %s", ticker, e
        )
        return TickerMetricsResponse.create_error_response(
            ticker, f"Unable to retrieve yf.Ticker data for ticker: {ticker}"
        )

    if df is None or df.empty:
        # 3. Return not found data
        not_found_response = TickerMetricsResponse.create_error_response(
            ticker, f"Symbol '{ticker}' does not exist"
        )
        await redis_service.set_cached_data(cache_key, not_found_response.model_dump())
        return not_found_response

    # 4. Return success data - all processing now handled by the class method
    prices = df["Close"].dropna()
    success_data = TickerMetricsResponse.from_ticker_data(ticker, prices, info)

    await redis_service.set_cached_data(cache_key, success_data.model_dump())
    return success_data
