"""
YFinance service module - centralized yfinance interactions.
"""
import json
import logging
from typing import Dict, List, Optional,  Any

import yfinance as yf
import pandas as pd


from yfinance.utils import is_valid_period_format
from app.redis_service import redis_service, construct_cache_key, CacheKey
from app.models.yfinance_models import TickerInfo, HistoryDict

logger = logging.getLogger(__name__)


class YFinanceService:
    """Service class for all yfinance operations."""

    #########################################################
    # History Data Converters

    def history_df_to_dict(self, df: pd.DataFrame, remove_time=True) -> Dict:
        """ Convert a dataframe to a dictionary. """
        result = df.copy()
        if remove_time:
            # Basically lose the time component but makes it comparable to other data
            result.index = result.index.normalize()

        result['index'] = [ts.isoformat() for ts in result.index.tolist()]
        result = result.to_dict(orient="list")
        validated_result = HistoryDict(**result)
        return validated_result.model_dump()

    def history_dict_to_json(self, dictionary: Dict) -> str:
        """ Convert a dictionary to a JSON string. """
        return json.dumps(dictionary)

    def history_json_to_dict(self, json_string: str) -> Dict:
        """ Convert a JSON string to a dictionary. """
        return json.loads(json_string)

    def history_dict_to_df(self, dictionary: Dict) -> pd.DataFrame:
        """ Convert a dictionary to a dataframe. """
        result = pd.DataFrame.from_dict(dictionary, orient="columns")
        result.set_index('index', inplace=True)
        result.index = pd.to_datetime(result.index, utc=True)
        return result

    def history_df_to_json(self, df: pd.DataFrame, remove_time=True) -> str:
        """ Convert a dataframe to a JSON string. """
        return self.history_dict_to_json(self.history_df_to_dict(df, remove_time))

    def history_json_to_df(self, json_string: str) -> pd.DataFrame:
        """ Convert a JSON string to a dataframe. """
        return self.history_dict_to_df(self.history_json_to_dict(json_string))

    #########################################################

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
            period="1wk",
            remove_time=True) -> pd.DataFrame:
        """Get historical data for a ticker"""

        # Adjust the ticker
        ticker = self.adjust_ticker(ticker)

        # Check if the ticker is valid
        await self.get_ticker_info(ticker)

        # Check if the period is valid
        if not is_valid_period_format(period):
            raise ValueError(f"Invalid period format for {ticker}: {period}")

        # Get the cache key
        cache_key = construct_cache_key(
            CacheKey.HISTORICAL, ticker, period, str(remove_time))

        # Return the cached data if it exists
        cached_data = await redis_service.get_cached_data(cache_key)
        if cached_data is not None:
            return self.history_json_to_df(cached_data)

        # Fetch the historical data
        try:
            ticker_obj = yf.Ticker(ticker)
            hist_data = ticker_obj.history(
                period=period, auto_adjust=True)

            if hist_data.empty:
                raise RuntimeError(
                    f"Error: No historical data found for ticker `{ticker}`")

            hist_data.index = hist_data.index.tz_convert('UTC')

            await redis_service.set_cached_data(cache_key, self.history_df_to_json(hist_data, remove_time))

            if remove_time:
                hist_data.index = hist_data.index.normalize()

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
            raise ValueError("Query is required")

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
            raise Exception("yfinance failed to search for tickers") from e

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
