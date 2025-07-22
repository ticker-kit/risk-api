""" Routes for risk metrics calculation. """
import logging
import yfinance as yf
from fastapi import APIRouter, HTTPException

from app.models.response_models import TickerMetricsResponse
from app.redis_service import redis_service
from app.utils import calculate_risk_from_prices

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ticker/{ticker}", response_model=TickerMetricsResponse)
async def get_ticker_data(ticker: str, refresh: bool = False):
    """ Calculate risk metrics from a stock ticker. """
    ticker = ticker.upper().strip()

    # Basic ticker validation
    if not ticker:
        raise HTTPException(
            status_code=400, detail="Ticker is required")

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
            "Unable to retrieve yf.Ticker data for ticker: %s, error: %s", ticker, e)

        error_data = TickerMetricsResponse(
            ticker=ticker,
            info=None,
            prices=None,
            mean_return=None,
            volatility=None,
            sharpe_ratio=None,
            max_drawdown=None,
            error_msg=f"Unable to retrieve yf.Ticker data for ticker: {ticker}"
        )

        # Don't cache API/network errors
        return error_data

    if df is None or df.empty:
        # 3. Return not found data
        not_found_data = TickerMetricsResponse(
            ticker=ticker,
            info=None,
            prices=None,
            mean_return=None,
            volatility=None,
            sharpe_ratio=None,
            max_drawdown=None,
            error_msg=f"Symbol '{ticker}' does not exist"
        )

        await redis_service.set_cached_data(cache_key, not_found_data.model_dump())
        return not_found_data

    # 4. Return success data
    prices = df["Close"].dropna()
    prices_dict = {
        "date": [date.isoformat().split("T")[0] for date in prices.index],
        "close": prices.values.tolist()
    }
    risk_metrics = calculate_risk_from_prices(prices)

    success_data = TickerMetricsResponse(
        ticker=ticker,
        info=info,
        prices=prices_dict,
        mean_return=risk_metrics["mean_return"],
        volatility=risk_metrics["volatility"],
        sharpe_ratio=risk_metrics["sharpe_ratio"],
        max_drawdown=risk_metrics["max_drawdown"],
        error_msg=None
    )

    await redis_service.set_cached_data(cache_key, success_data.model_dump())
    return success_data
