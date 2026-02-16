"""
crypto_pairs — Standalone library for fetching active/inactive trading pairs
from multiple cryptocurrency exchanges (Binance, Bybit, Hyperliquid).

Usage:
    from crypto_pairs import get_active_pairs, get_inactive_pairs, get_all_pairs

    active = get_active_pairs("binance", "spot")
    inactive = get_inactive_pairs("binance", "futures")
    everything = get_all_pairs("hyperliquid", "futures")
"""

from .pairs import (
    get_active_pairs,
    get_inactive_pairs,
    get_all_pairs,
    list_exchanges,
    get_exchange_info,
)
from .factory import ExchangeFactory

__all__ = [
    "get_active_pairs",
    "get_inactive_pairs",
    "get_all_pairs",
    "list_exchanges",
    "get_exchange_info",
    "ExchangeFactory",
]
