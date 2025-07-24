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
    cached_dict = await redis_service.get_cached_data(cache_key)
    if cached_dict:
        return TickerMetricsResponse.from_cache_data(cached_dict)

    try:
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period="20y", auto_adjust=True)
        info = ticker_obj.info
    except Exception as e:
        # 2. Return error data
        logger.error(
            "Unable to retrieve yf.Ticker data for ticker: %s, error: %s", ticker, e
        )
        return TickerMetricsResponse.to_cached_data(
            ticker, error_msg=f"Unable to retrieve yf.Ticker data for ticker: {ticker}"
        )

    if df is None or df.empty:
        # 3. Return not found data
        not_found_response = TickerMetricsResponse.to_cached_data(
            ticker, error_msg=f"Symbol '{ticker}' does not exist"
        )
        await redis_service.set_cached_data(cache_key, not_found_response.model_dump())
        return not_found_response

    # 4. Return success data - all processing now handled by the class method
    close_prices = df["Close"].dropna()
    new_cached_data = TickerMetricsResponse.to_cached_data(
        ticker,
        close_prices=close_prices,
        info=info
    )

    await redis_service.set_cached_data(cache_key, new_cached_data.model_dump())

    success_data = TickerMetricsResponse.from_cache_data(
        new_cached_data.model_dump())

    return success_data
