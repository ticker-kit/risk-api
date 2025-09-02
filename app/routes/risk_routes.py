""" Routes for risk metrics calculation. """
import logging
from fastapi import APIRouter, HTTPException

from app.models.response_models import TickerMetricsResponse
# from app.redis_service import redis_service, construct_cache_key, CacheKey
from app.yfinance_service import yfinance_service
from app.models.base_models import create_asset_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ticker/{ticker}", response_model=TickerMetricsResponse)
async def get_ticker_data(ticker: str, currency: str | None = None):
    """ Calculate risk metrics from a stock ticker. """

    print(ticker)
    print(currency)

    ticker = yfinance_service.adjust_ticker(ticker)

    # cache_key = construct_cache_key(CacheKey.TICKER_METRICS, ticker)

    try:
        initial_asset_data = await create_asset_analysis(ticker, period="10y")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return initial_asset_data.to_asset_analysis_response()
