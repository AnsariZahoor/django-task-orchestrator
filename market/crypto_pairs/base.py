"""
Base Exchange - Lightweight base for fetching trading pairs only.
No klines, funding rates, or OI — just active/inactive pair discovery.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
import logging
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Module-level shared HTTP client
_CLIENT: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    """Get or create shared HTTP client."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=60.0,
            ),
            http2=True,
        )
    return _CLIENT


class BaseExchange(ABC):
    """Abstract base for exchange pair-fetching implementations."""

    def __init__(self, cache_ttl: int = 60):
        self._client = _get_client()
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Dict]] = {}

    @property
    def client(self) -> httpx.Client:
        return self._client

    # -- HTTP helpers ----------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_with_retry(self, url: str) -> dict:
        logger.info("GET %s", url)
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _post_with_retry(self, url: str, payload: dict) -> dict:
        logger.info("POST %s payload=%s", url, payload)
        resp = self.client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    # -- Abstract interface ----------------------------------------------------

    @abstractmethod
    def fetch_symbols(self, url: str, exchange: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch trading and non-trading symbols from the exchange API.

        Returns:
            (trading_symbols, non_trading_symbols)
            Each item: {"symbol": "BTC", "pair": "BTCUSDT"}
        """
        ...

    @classmethod
    @abstractmethod
    def get_supported_markets(cls) -> List[str]:
        """Return supported market types, e.g. ['spot', 'futures']."""
        ...

    @abstractmethod
    def process_spot(self) -> Tuple[List[Dict], List[Dict]]:
        """Return (active, inactive) pairs for spot."""
        ...

    @abstractmethod
    def process_futures(self) -> Tuple[List[Dict], List[Dict]]:
        """Return (active, inactive) pairs for futures."""
        ...

    # -- Shared logic ----------------------------------------------------------

    def _tag_pairs(
        self,
        exchange: str,
        trading: List[Dict],
        non_trading: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Add exchange name and is_active flag to pair dicts."""
        active = [{**p, "exchange": exchange, "is_active": True} for p in trading]
        inactive = [{**p, "exchange": exchange, "is_active": False} for p in non_trading]
        return active, inactive

    def fetch_all_pairs(self, market_type: str, use_cache: bool = True) -> Dict[str, List[Dict]]:
        """
        Fetch all pairs for a market type with optional caching.

        Returns:
            {"active": [...], "inactive": [...]}
        """
        supported = self.__class__.get_supported_markets()
        if market_type not in supported:
            raise ValueError(
                f"Unsupported market '{market_type}'. Supported: {supported}"
            )

        if use_cache and market_type in self._cache:
            ts, data = self._cache[market_type]
            if time.time() - ts < self.cache_ttl:
                return data

        method = getattr(self, f"process_{market_type}", None)
        if method is None:
            raise NotImplementedError(f"process_{market_type} not implemented")

        active, inactive = method()
        result = {"active": active, "inactive": inactive}

        if use_cache:
            self._cache[market_type] = (time.time(), result)

        return result
