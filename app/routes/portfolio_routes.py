""" Portfolio routes for the application. """
from typing import List
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.config import settings
from app.auth import get_current_user
from app.db import get_session
from app.models.db_models import AssetPosition, User
from app.models.yfinance_models import TickerSearchReference
from app.models.response_models import EnhancedAssetPosition, EnhancedPortfolioResponse, \
    PortfolioMarketData
from app.models.client_models import AssetPositionRequest
from app.redis_service import redis_service
from app.yfinance_service import yfinance_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/portfolio", response_model=List[AssetPosition])
def get_portfolio(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """ Get the portfolio for a user. """
    return session.exec(select(AssetPosition).where(AssetPosition.user_id == user.id)).all()


@router.post("/portfolio", response_model=AssetPositionRequest)
async def add_position(
    position: AssetPositionRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """ Add a position to the portfolio. """

    # Assert that the user has an id
    if user.id is None:
        raise HTTPException(
            status_code=500,
            detail="User authentication error: missing user ID"
        )

    # Validate inputs
    ticker = await yfinance_service.validate_ticker(position.ticker)
    if not ticker:
        raise HTTPException(
            status_code=400, detail="Invalid ticker symbol")

    quantity = position.quantity
    if quantity is None or quantity <= 0 or quantity > 1000000:
        raise HTTPException(
            status_code=400, detail="Quantity must be a positive number between 1 and 1,000,000.")

    # Check if ticker already exists for user
    existing = session.exec(select(AssetPosition).where(
        AssetPosition.user_id == user.id, AssetPosition.ticker == position.ticker)).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="Position already exists. Use update instead.")

    obj_to_add = AssetPosition(
        ticker=ticker,
        quantity=quantity,
        user_id=user.id
    )

    obj_to_return = AssetPositionRequest(
        ticker=ticker,
        quantity=quantity
    )

    session.add(obj_to_add)
    session.commit()

    # Publish ticker update event to Redis
    try:
        await redis_service.publish_ticker_update(
            ticker=ticker,
            user_id=user.id,
            action="add"
        )
    except Exception as e:
        print(f"⚠️  Failed to publish ticker update event: {e}")
        # Don't fail the request if Redis is unavailable

    return obj_to_return


@router.put("/portfolio/{symbol}", response_model=AssetPosition)
async def update_position(
    symbol: str,
    quantity: float,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a position in the portfolio."""
    assert user.id is not None, "Authenticated user must have an id"

    symbol = symbol.upper().strip()

    # Check if position exists
    pos = session.exec(select(AssetPosition).where(
        AssetPosition.user_id == user.id, AssetPosition.ticker == symbol)).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found.")

    pos.quantity = quantity
    session.add(pos)
    session.commit()
    session.refresh(pos)

    # Publish ticker update event to Redis
    try:
        await redis_service.publish_ticker_update(
            ticker=symbol,
            user_id=user.id,
            action="update"
        )
    except Exception as e:
        print(f"⚠️  Failed to publish ticker update event: {e}")
        # Don't fail the request if Redis is unavailable

    return pos


@router.delete("/portfolio/{symbol}", status_code=204)
async def delete_position(
    symbol: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a position from the portfolio."""

    pos = session.exec(select(AssetPosition).where(
        AssetPosition.user_id == user.id, AssetPosition.ticker == symbol)).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found.")

    session.delete(pos)
    session.commit()

    # Publish ticker update event to Redis
    try:
        if user.id is not None:
            await redis_service.publish_ticker_update(
                ticker=symbol,
                user_id=user.id,
                action="delete"
            )
    except Exception as e:
        print(f"⚠️  Failed to publish ticker update event: {e}")
        # Don't fail the request if Redis is unavailable

    return


@router.get("/search_ticker", response_model=List[TickerSearchReference])
async def search_ticker(q: str = Query(..., min_length=1, max_length=30)):
    """ Search for tickers by name or symbol using yfinance.Search. """
    try:
        results = await yfinance_service.search_tickers(q, limit=10)
        return results

    except Exception as e:
        logger.error("Unexpected error in ticker search: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while searching for tickers"
        ) from e


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """ Get the current user. """
    return user


@router.get("/redis-info")
async def redis_info():
    """Get Redis connection information for debugging."""
    try:
        info = await redis_service.get_redis_info()
        return {
            "redis_status": info,
            "environment": {
                "REDIS_HOST": settings.redis_config.host,
                "REDIS_PORT": settings.redis_config.port,
                "REDIS_URL": "***" if settings.redis_config.url else None
            }
        }
    except Exception as e:
        return {
            "redis_status": {
                "connection_status": "error",
                "error": str(e)
            },
            "environment": {
                "REDIS_HOST": settings.redis_config.host,
                "REDIS_PORT": settings.redis_config.port,
                "REDIS_URL": "***" if settings.redis_config.url else None
            }
        }


@router.post("/trigger-price-update")
async def trigger_price_update(request: dict):
    """Trigger a price update for a ticker via Redis pub/sub."""
    ticker = request.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    ticker = ticker.upper().strip()

    try:
        # Publish ticker update event to Redis
        await redis_service.publish_ticker_update(
            ticker=ticker,
            user_id=0,  # System triggered
            action="fetch"
        )

        return {
            "message": f"Price update triggered for {ticker}",
            "ticker": ticker,
            "status": "success"
        }
    except Exception as e:
        print(f"⚠️  Failed to trigger price update: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Price update service unavailable for {ticker}"
        ) from e


@router.get("/portfolio/enhanced", response_model=EnhancedPortfolioResponse)
async def get_enhanced_portfolio(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    period: str = Query(
        "1y", description="Historical data period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)")
):
    """Get enhanced portfolio with yfinance market data and historical prices."""

    # Get user positions
    positions = session.exec(select(AssetPosition).where(
        AssetPosition.user_id == user.id)).all()

    if not positions or len(positions) == 0:
        return EnhancedPortfolioResponse(
            positions=[],
            total_market_value=0.0,
            last_updated=datetime.now().isoformat()
        )

    # Extract tickers
    tickers = sorted([pos.ticker for pos in positions])

    # Check cache first
    cache_key = f"enhanced_portfolio:{user.id}:{period}:{':'.join(sorted(tickers))}"
    cached_data = await redis_service.get_cached_data(cache_key)

    if cached_data:
        logger.info("Returning cached enhanced portfolio for user %s", user.id)
        return EnhancedPortfolioResponse(**cached_data)

    enhanced_positions = []
    total_market_value = 0.0

    try:
        # Get bulk historical data efficiently
        hist_data = await yfinance_service.get_bulk_historical_data(tickers, period)

        # Get current prices for all tickers
        current_prices = await yfinance_service.get_bulk_current_prices(tickers)

        for position in positions:
            ticker = position.ticker
            enhanced_pos = EnhancedAssetPosition(
                id=position.id,
                ticker=ticker,
                quantity=position.quantity,
                user_id=position.user_id
            )

            try:
                # Get ticker info
                ticker_info = await yfinance_service.get_ticker_info(ticker)
                enhanced_pos.ticker_info = ticker_info

                # Set current price and market value
                current_price = current_prices.get(ticker)
                if current_price:
                    enhanced_pos.current_price = float(current_price)
                    enhanced_pos.market_value = float(
                        current_price * position.quantity)
                    total_market_value += enhanced_pos.market_value

                # Extract historical data if available
                if not hist_data.empty and ticker in hist_data.columns.get_level_values(1):
                    ticker_hist = hist_data.xs(ticker, level=1, axis=1)
                    if not ticker_hist.empty:
                        enhanced_pos.historical_data = {
                            'dates': [d.strftime('%Y-%m-%d') for d in ticker_hist.index],
                            'open': ticker_hist['Open'].fillna(0).tolist(),
                            'high': ticker_hist['High'].fillna(0).tolist(),
                            'low': ticker_hist['Low'].fillna(0).tolist(),
                            'close': ticker_hist['Close'].fillna(0).tolist(),
                            'volume': ticker_hist['Volume'].fillna(0).tolist()
                        }

            except Exception as e:
                logger.error("Error fetching data for %s: %s", ticker, e)
                enhanced_pos.error = f"Failed to fetch data: {str(e)}"

            enhanced_positions.append(enhanced_pos)

        response = EnhancedPortfolioResponse(
            positions=enhanced_positions,
            total_market_value=total_market_value,
            last_updated=datetime.now().isoformat()
        )

        # Cache the response for 5 minutes
        await redis_service.set_cached_data(cache_key, response.dict(), expiry=300)

        return response

    except Exception as e:
        logger.error("Error fetching enhanced portfolio data: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch market data. Please try again later."
        ) from e


@router.get("/portfolio/market-data", response_model=PortfolioMarketData)
async def get_portfolio_market_data(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    period: str = Query(
        "1y", description="Historical data period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)")
):
    """Get portfolio market data with aligned time series for all tickers."""

    # Get user positions
    positions = session.exec(select(AssetPosition).where(
        AssetPosition.user_id == user.id)).all()

    if not positions or len(positions) == 0:
        return PortfolioMarketData(
            tickers=[],
            infos=[],
            timeseries_data={"dates": []},
            positions=[],
            total_market_value=0.0,
            last_updated=datetime.now().isoformat()
        )

    # Extract tickers
    tickers = sorted([pos.ticker for pos in positions])

    # Check cache first
    cache_key = f"portfolio_market_data:{user.id}:{period}:{':'.join(tickers)}"
    cached_data = await redis_service.get_cached_data(cache_key)

    if cached_data:
        logger.info(
            "Returning cached portfolio market data for user %s", user.id)
        return PortfolioMarketData(**cached_data)

    try:
        # Get bulk historical data efficiently
        hist_data = await yfinance_service.get_bulk_historical_data(tickers, period)

        # Get current prices for all tickers
        current_prices = await yfinance_service.get_bulk_current_prices(tickers)

        # Get ticker infos
        infos = []
        for ticker in tickers:
            try:
                info = await yfinance_service.get_ticker_info(ticker)
                infos.append(info)
            except Exception as e:
                logger.error("Error fetching info for %s: %s", ticker, e)
                infos.append({"error": f"Failed to fetch info for {ticker}"})

        # Build aligned timeseries data
        timeseries_data = {"dates": []}

        if not hist_data.empty:
            # Extract dates (same for all tickers)
            timeseries_data["dates"] = [d.strftime(
                '%Y-%m-%d') for d in hist_data.index]

            # Extract close prices for each ticker
            for ticker in tickers:
                if ticker in hist_data.columns.get_level_values(1):
                    ticker_hist = hist_data.xs(ticker, level=1, axis=1)
                    if 'Close' in ticker_hist.columns:
                        timeseries_data[ticker] = ticker_hist['Close'].fillna(
                            0).tolist()
                    else:
                        timeseries_data[ticker] = []
                else:
                    timeseries_data[ticker] = []
        else:
            # No historical data available
            for ticker in tickers:
                timeseries_data[ticker] = []

        # Build position info with market values
        position_data = []
        total_market_value = 0.0

        for position in positions:
            ticker = position.ticker
            current_price = current_prices.get(ticker)
            market_value = None

            if current_price:
                market_value = float(current_price * position.quantity)
                total_market_value += market_value

            position_data.append({
                "id": position.id,
                "ticker": ticker,
                "quantity": position.quantity,
                "current_price": current_price,
                "market_value": market_value
            })

        response = PortfolioMarketData(
            tickers=tickers,
            infos=infos,
            timeseries_data=timeseries_data,
            positions=position_data,
            total_market_value=total_market_value,
            last_updated=datetime.now().isoformat()
        )

        # Cache the response for 5 minutes
        await redis_service.set_cached_data(cache_key, response.dict(), expiry=300)

        return response

    except Exception as e:
        logger.error("Error fetching portfolio market data: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch market data. Please try again later."
        ) from e
