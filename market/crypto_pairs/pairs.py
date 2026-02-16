"""
High-level API for fetching active/inactive trading pairs.

Usage:
    from crypto_pairs import get_active_pairs, get_inactive_pairs, get_all_pairs

    # Get active Binance spot pairs
    active = get_active_pairs("binance", "spot")

    # Get inactive Hyperliquid futures pairs
    inactive = get_inactive_pairs("hyperliquid", "futures")

    # Get everything
    all_pairs = get_all_pairs("bybit", "futures")
"""

from typing import Dict, List, Literal
from .factory import ExchangeFactory


def get_active_pairs(
    exchange: str,
    market: Literal["spot", "futures"],
) -> List[Dict]:
    """
    Fetch active (currently trading) pairs.

    Args:
        exchange: 'binance' | 'bybit' | 'hyperliquid'
        market: 'spot' | 'futures'

    Returns:
        List of dicts: [{"symbol": "BTC", "pair": "BTCUSDT", "exchange": "binance-spot", "is_active": True}, ...]
    """
    inst = ExchangeFactory.create(exchange)
    result = inst.fetch_all_pairs(market)
    return result["active"]


def get_inactive_pairs(
    exchange: str,
    market: Literal["spot", "futures"],
) -> List[Dict]:
    """
    Fetch inactive (delisted/paused) pairs.

    Args:
        exchange: 'binance' | 'bybit' | 'hyperliquid'
        market: 'spot' | 'futures'

    Returns:
        List of dicts: [{"symbol": "LUNA", "pair": "LUNAUSDT", "exchange": "binance-futures", "is_active": False}, ...]
    """
    inst = ExchangeFactory.create(exchange)
    result = inst.fetch_all_pairs(market)
    return result["inactive"]


def get_all_pairs(
    exchange: str,
    market: Literal["spot", "futures"],
) -> Dict[str, List[Dict]]:
    """
    Fetch both active and inactive pairs.

    Args:
        exchange: 'binance' | 'bybit' | 'hyperliquid'
        market: 'spot' | 'futures'

    Returns:
        {"active": [...], "inactive": [...]}
    """
    inst = ExchangeFactory.create(exchange)
    return inst.fetch_all_pairs(market)


def list_exchanges() -> List[str]:
    """Return registered exchange names."""
    return ExchangeFactory.list_exchanges()


def get_exchange_info(exchange: str) -> Dict:
    """Get exchange metadata (name, supported markets)."""
    return ExchangeFactory.get_exchange_info(exchange)
