"""Bybit pair-fetching adapter (spot + futures)."""

from typing import Dict, List, Tuple
from ..base import BaseExchange


class BybitExchange(BaseExchange):
    """Fetch active/inactive pairs from Bybit spot & futures."""

    SPOT_URL = "https://api.bybit.com/v5/market/instruments-info?category=spot&status=Trading&limit=1000"
    FUTURES_URL = "https://api.bybit.com/v5/market/instruments-info?category=linear&status=Trading&limit=1000"
    QUOTE_ASSET = "USDT"

    @classmethod
    def get_supported_markets(cls) -> List[str]:
        return ["spot", "futures"]

    def fetch_symbols(self, url: str, exchange: str) -> Tuple[List[Dict], List[Dict]]:
        data = self._fetch_with_retry(url)
        result_list = data.get("result", {}).get("list", [])
        trading, non_trading = [], []

        if exchange == "bybit-spot":
            trading = [
                {"symbol": item.get("baseCoin"), "pair": item.get("symbol")}
                for item in result_list
                if item.get("quoteCoin") == self.QUOTE_ASSET
                and item.get("status") == "Trading"
            ]
            # Bybit spot API doesn't return inactive in Trading endpoint
            non_trading = []

        elif exchange == "bybit-futures":
            trading = [
                {"symbol": item.get("baseCoin"), "pair": item.get("symbol")}
                for item in result_list
                if item.get("quoteCoin") == self.QUOTE_ASSET
                and item.get("contractType") == "LinearPerpetual"
                and item.get("status") == "Trading"
            ]
            non_trading = []

        else:
            raise ValueError(f"Invalid Bybit exchange type: {exchange}")

        return trading, non_trading

    def process_spot(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "bybit-spot"
        trading, non_trading = self.fetch_symbols(self.SPOT_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)

    def process_futures(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "bybit-futures"
        trading, non_trading = self.fetch_symbols(self.FUTURES_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)
