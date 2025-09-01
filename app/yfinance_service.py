"""
YFinance service module - centralized yfinance interactions.
"""

import logging
from typing import Dict, List, Optional,  Any
from io import StringIO

import yfinance as yf
from yfinance.utils import is_valid_period_format
import pandas as pd
from fastapi import HTTPException

from app.redis_service import redis_service, construct_cache_key, CacheKey
from app.models.yfinance_models import TickerInfo

logger = logging.getLogger(__name__)


class YFinanceService:
    """Service class for all yfinance operations."""

    def adjust_ticker(self, ticker: str) -> str:
        """ Adjust a ticker symbol. """
        if not ticker.strip():
            raise ValueError(f"Error: Ticker symbol is required `{ticker}`")

        return ticker.upper().strip()

    async def validate_ticker(self, ticker: str):
        """ Validate a ticker symbol. """

        upper_ticker = self.adjust_ticker(ticker)

        try:
            await self.get_ticker_info(upper_ticker)
            return upper_ticker

        except Exception as e:
            raise Exception(str(e)) from e

    async def get_ticker_info(self, ticker: str, only_validated: bool = True) -> Dict[str, Any]:
        """
        Get ticker information from yfinance.
        Returns: Dict containing ticker information as a TickerInfo model
        """
        ticker = self.adjust_ticker(ticker)
        cache_key = construct_cache_key(CacheKey.TICKER_INFO, ticker)
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data:
            return TickerInfo(**cached_data).model_dump() if only_validated else cached_data

        try:
            info = yf.Ticker(ticker).info

            if not info or info.get('symbol') is None:
                raise ValueError(
                    f"No information available for ticker: {ticker}")

            # Validate the info
            validated_info = TickerInfo(**info)

            # Cache whole info
            await redis_service.set_cached_data(cache_key, info)

            return validated_info.model_dump() if only_validated else info

        except ValueError as e:
            raise Exception(str(e)) from e

        except Exception as e:
            msg = f"Error: Something went wrong fetching ticker info for {ticker}"
            logger.error("%s: %s", msg, str(e))
            raise Exception(msg) from e

    async def get_historical_data(
            self,
            ticker: str,
            period: str = "1wk") -> pd.DataFrame:

        # Adjust the ticker
        ticker = self.adjust_ticker(ticker)

        # Check if the ticker is valid
        await self.get_ticker_info(ticker)

        # Check if the period is valid
        if not is_valid_period_format(period):
            raise ValueError(f"Invalid period format for {ticker}: {period}")

        # Get the cache key
        cache_key = construct_cache_key(CacheKey.HISTORICAL, ticker, period)

        # Return the cached data if it exists
        cached_data = await redis_service.get_cached_data(cache_key)
        if cached_data is not None:
            return pd.read_json(StringIO(cached_data), orient="split")

        # Fetch the historical data
        try:
            ticker_obj = yf.Ticker(ticker)
            hist_data = ticker_obj.history(
                period=period, auto_adjust=True)

            if hist_data.empty:
                raise RuntimeError(
                    f"Error: No historical data found for ticker `{ticker}`")

            if 'Close' not in hist_data.columns:
                raise RuntimeError(
                    f"Error: Close column not found in historical data for ticker `{ticker}`")

            await redis_service.set_cached_data(cache_key, hist_data.to_json(orient="split"))

            return hist_data

        except RuntimeError as e:
            raise Exception(str(e)) from e

        except Exception as e:
            msg = f"Error: fetching historical data for {ticker}"
            logger.error("%s: %s", msg, str(e))
            raise Exception(msg) from e

    async def get_bulk_historical_data(
            self,
            tickers: List[str],
            period: str = "1wk") -> pd.DataFrame:
        """
        Get historical data for multiple tickers efficiently.

        Args:
            tickers: List of ticker symbols
            period: Time period

        Returns:
            Multi-level DataFrame with historical data for all tickers
        """

        cache_key = construct_cache_key(
            CacheKey.BULK_HISTORICAL, ':'.join(sorted(tickers)), period)
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

    async def search_tickers(self, query: str, max_results=8, fuzzy=False) -> List[Dict[str, Any]]:
        """
        Search for tickers by name or symbol.

        Args:
            query: Search query
            max_results: Maximum number of results
            fuzzy: Whether to use fuzzy search

        Returns:
            List of ticker search results
        """
        query_upper = query.upper().strip()
        if not query_upper:
            raise HTTPException(
                status_code=400, detail="Search query is required")

        cache_key = construct_cache_key(
            CacheKey.SEARCH, query_upper, str(max_results), str(fuzzy))
        cached_data = await redis_service.get_cached_data(cache_key)

        if cached_data:
            return cached_data

        try:
            data = yf.Search(
                query,
                max_results=max_results,
                enable_fuzzy_query=fuzzy).quotes
            results = []

            for item in data:
                if not item.get("symbol"):
                    logger.warning("Invalid ticker search result: %s", item)
                    continue
                results.append(item)

            await redis_service.set_cached_data(cache_key, results)

            return results

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
