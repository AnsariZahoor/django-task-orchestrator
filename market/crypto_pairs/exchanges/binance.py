"""Binance pair-fetching adapter (spot + futures)."""

from typing import Dict, List, Tuple
from ..base import BaseExchange


class BinanceExchange(BaseExchange):
    """Fetch active/inactive pairs from Binance spot & futures."""

    SPOT_URL = "https://api.binance.com/api/v3/exchangeInfo?permissions=SPOT"
    FUTURES_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    QUOTE_ASSET = "USDT"

    @classmethod
    def get_supported_markets(cls) -> List[str]:
        return ["spot", "futures"]

    def fetch_symbols(self, url: str, exchange: str) -> Tuple[List[Dict], List[Dict]]:
        data = self._fetch_with_retry(url)
        trading, non_trading = [], []

        if exchange == "binance-spot":
            for item in data.get("symbols", []):
                if item.get("quoteAsset") == self.QUOTE_ASSET:
                    entry = {"symbol": item["baseAsset"], "pair": item["symbol"]}
                    if item.get("status") == "TRADING":
                        trading.append(entry)
                    else:
                        non_trading.append(entry)

        elif exchange == "binance-futures":
            for item in data.get("symbols", []):
                if (
                    item.get("quoteAsset") == self.QUOTE_ASSET
                    and item.get("contractType") == "PERPETUAL"
                ):
                    entry = {"symbol": item["baseAsset"], "pair": item["pair"]}
                    if item.get("status") == "TRADING":
                        trading.append(entry)
                    else:
                        non_trading.append(entry)
        else:
            raise ValueError(f"Invalid Binance exchange type: {exchange}")

        return trading, non_trading

    def process_spot(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "binance-spot"
        trading, non_trading = self.fetch_symbols(self.SPOT_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)

    def process_futures(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "binance-futures"
        trading, non_trading = self.fetch_symbols(self.FUTURES_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)
