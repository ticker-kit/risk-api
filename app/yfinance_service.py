"""
YFinance service module - centralized yfinance interactions.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional,  Any

import yfinance as yf
import pandas as pd
from fastapi import HTTPException

from app.redis_service import redis_service
from app.models.yfinance_models import TickerInfo

logger = logging.getLogger(__name__)


class CacheKey(Enum):
    """Cache keys for yfinance operations."""
    TICKER_INFO = "ticker_info"
    HISTORICAL = "historical"
    SEARCH = "search"


class YFinanceService:
    """Service class for all yfinance operations."""

    async def validate_ticker(self, ticker: str):
        if not ticker:
            raise HTTPException(
                status_code=400, detail="Ticker symbol is required")

        upper_ticker = ticker.upper().strip()

        # 1. Check cache first
        cache_key = f"{CacheKey.TICKER_INFO}:{upper_ticker}"
        cached_result = await redis_service.get_cached_data(cache_key)

        if cached_result is not None:
            cached_result_symbol: str = cached_result.get('symbol')
            if not cached_result_symbol:
                return
            return cached_result_symbol

        # 2. Validate with yfinance
        try:
            yf_ticker = yf.Ticker(upper_ticker)

            # 2.1. Unsuccessful ticker
            info = yf_ticker.info

            if not info:
                return

            fetched_symbol: str = info.get('symbol')

            if not fetched_symbol:
                return

            # 2.2 Successfully validated ticker
            cache_key_new = f"{CacheKey.TICKER_INFO}:{fetched_symbol}"
            await redis_service.set_cached_data(cache_key_new, info)
            return fetched_symbol

        except Exception as e:
            logger.error("Error validating ticker %s: %s", ticker, e)
            return

    async def get_ticker_info(self, ticker: str) -> TickerInfo:
        """
        Get ticker information from yfinance.

        Args:
            ticker: Ticker symbol

        Returns:
            Dict containing ticker information

        Raises:
            HTTPException: If ticker data cannot be retrieved
        """
        cache_key = f"{CacheKey.TICKER_INFO}:{ticker.upper()}"
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data:
            return cached_data

        try:
            info = yf.Ticker(ticker).info

            if not info:
                raise HTTPException(
                    status_code=404,
                    detail=f"No information available for ticker: {ticker}"
                )

            # Clean info data (remove large unnecessary fields)
            cleaned_info = {k: v for k, v in info.items() if k not in [
                'companyOfficers', 'fullTimeEmployees', 'longBusinessSummary'
            ] and not (isinstance(v, (list, dict)) and len(str(v)) > 1000)}

            # Cache the result
            await redis_service.set_cached_data(cache_key, cleaned_info)

            return cleaned_info

        except Exception as e:
            logger.error("Error fetching ticker info for %s: %s", ticker, e)
            raise HTTPException(
                status_code=503,
                detail=f"Unable to retrieve info for ticker: {ticker}"
            ) from e

    async def get_historical_data(
            self,
            ticker: str,
            period: str = "1y",
            auto_adjust: bool = False) -> Optional[pd.DataFrame]:
        """
        Get historical data for a single ticker.

        Args:
            ticker: Ticker symbol
            period: Time period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
            auto_adjust: Whether to auto-adjust prices for splits and dividends

        Returns:
            DataFrame with historical data or None if failed
        """
        cache_key = f"{CacheKey.HISTORICAL}:{ticker.upper()}:{period}:{auto_adjust}"
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data is not None:
            if cached_data == "ERROR":
                return None
            # Convert back to DataFrame
            return pd.DataFrame(cached_data)

        try:
            ticker_obj = yf.Ticker(ticker)
            hist_data = ticker_obj.history(
                period=period, auto_adjust=auto_adjust)

            if hist_data.empty:
                await redis_service.set_cached_data(cache_key, "ERROR")
                return None

            # Cache as dict for JSON serialization
            cache_data = {
                'index': [d.isoformat() for d in hist_data.index],
                'data': hist_data.to_dict('list')
            }

            await redis_service.set_cached_data(cache_key, cache_data)

            return hist_data

        except Exception as e:
            logger.error(
                "Error fetching historical data for %s: %s", ticker, e)
            await redis_service.set_cached_data(cache_key, "ERROR")
            return None

    async def get_bulk_historical_data(
            self,
            tickers: List[str],
            period: str = "1y") -> pd.DataFrame:
        """
        Get historical data for multiple tickers efficiently.

        Args:
            tickers: List of ticker symbols
            period: Time period

        Returns:
            Multi-level DataFrame with historical data for all tickers
        """
        cache_key = f"bulk_historical:{':'.join(sorted(tickers))}:{period}"
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data is not None:
            if cached_data == "ERROR":
                return pd.DataFrame()
            # Reconstruct DataFrame from cached data
            return self._reconstruct_bulk_dataframe(cached_data)

        try:
            tickers_obj = yf.Tickers(' '.join(tickers))
            hist_data = tickers_obj.history(period=period)

            if hist_data.empty:
                await redis_service.set_cached_data(cache_key, "ERROR")
                return pd.DataFrame()

            # Cache the data
            cache_data = {
                'index': [d.isoformat() for d in hist_data.index],
                'columns': [list(col) for col in hist_data.columns],
                'data': hist_data.values.tolist()
            }

            await redis_service.set_cached_data(cache_key, cache_data)

            return hist_data

        except Exception as e:
            logger.error("Error fetching bulk historical data: %s", e)
            await redis_service.set_cached_data(cache_key, "ERROR")
            return pd.DataFrame()

    # CHECKED OK
    async def search_tickers(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for tickers by name or symbol.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of ticker search results
        """
        query_upper = query.upper().strip()
        if not query_upper:
            raise HTTPException(
                status_code=400, detail="Search query is required")

        cache_key = f"{CacheKey.SEARCH}:{query_upper}"
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data:
            return cached_data[:limit]

        try:
            data = yf.Search(query).quotes
            results = []

            for item in data:
                if not item.get("symbol"):
                    logger.warning("Invalid ticker search result: %s", item)
                    continue
                results.append(item)

            await redis_service.set_cached_data(cache_key, results)

            return results[:limit]

        except Exception as e:
            logger.error(
                "Error searching tickers for query '%s': %s", query, e)
            raise HTTPException(
                status_code=500,
                detail="yfinance failed to search for tickers"
            ) from e

    async def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Current price or None if not available
        """
        try:
            info = await self.get_ticker_info(ticker)
            return info.get('regularMarketPrice') or info.get('currentPrice')
        except Exception as e:
            logger.error("Error getting current price for %s: %s", ticker, e)
            return None

    async def get_bulk_current_prices(self, tickers: List[str]) -> Dict[str, Optional[float]]:
        """
        Get current prices for multiple tickers efficiently.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker to current price
        """
        prices = {}

        # Try to get from individual ticker info (cached)
        for ticker in tickers:
            try:
                price = await self.get_current_price(ticker)
                prices[ticker] = price
            except Exception as e:
                logger.error("Error getting price for %s: %s", ticker, e)
                prices[ticker] = None

        return prices

    def _reconstruct_bulk_dataframe(self, cached_data: Dict) -> pd.DataFrame:
        """Reconstruct DataFrame from cached bulk historical data."""
        try:
            index = pd.to_datetime(cached_data['index'])
            columns = pd.MultiIndex.from_tuples(
                [tuple(col) for col in cached_data['columns']]
            )
            return pd.DataFrame(
                cached_data['data'],
                index=index,
                columns=columns
            )
        except Exception as e:
            logger.error("Error reconstructing DataFrame from cache: %s", e)
            return pd.DataFrame()


# Global service instance
yfinance_service = YFinanceService()
