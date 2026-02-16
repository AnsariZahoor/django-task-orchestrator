"""Hyperliquid pair-fetching adapter (spot + futures)."""

from typing import Dict, List, Tuple
from ..base import BaseExchange


class HyperliquidExchange(BaseExchange):
    """Fetch active/inactive pairs from Hyperliquid spot & futures."""

    API_URL = "https://api.hyperliquid.xyz/info"

    # Symbol normalization
    SYMBOL_MAP = {"USDT0": "USDT", "USDC": "USDC"}

    @classmethod
    def get_supported_markets(cls) -> List[str]:
        return ["spot", "futures"]

    def _normalize(self, symbol: str) -> str:
        return self.SYMBOL_MAP.get(symbol, symbol)

    def fetch_symbols(self, url: str, exchange: str) -> Tuple[List[Dict], List[Dict]]:
        if exchange == "hyperliquid-spot":
            data = self._post_with_retry(url, {"type": "spotMeta"})

            tokens_map = {}
            for token in data.get("tokens", []):
                tokens_map[token["index"]] = self._normalize(token["name"])

            trading = []
            for pair in data.get("universe", []):
                idxs = pair.get("tokens", [])
                if len(idxs) >= 2 and idxs[0] in tokens_map and idxs[1] in tokens_map:
                    base = tokens_map[idxs[0]]
                    quote = tokens_map[idxs[1]]
                    trading.append({"symbol": base, "pair": f"{base}/{quote}"})

            return trading, []

        elif exchange == "hyperliquid-futures":
            data = self._post_with_retry(url, {"type": "meta"})

            trading, non_trading = [], []
            for item in data.get("universe", []):
                sym = item.get("name", "")
                entry = {"symbol": sym, "pair": f"{sym}-USD"}
                if item.get("isDelisted", False):
                    non_trading.append(entry)
                else:
                    trading.append(entry)

            return trading, non_trading

        else:
            raise ValueError(f"Invalid Hyperliquid exchange type: {exchange}")

    def process_spot(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "hyperliquid-spot"
        trading, non_trading = self.fetch_symbols(self.API_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)

    def process_futures(self) -> Tuple[List[Dict], List[Dict]]:
        exchange = "hyperliquid-futures"
        trading, non_trading = self.fetch_symbols(self.API_URL, exchange)
        return self._tag_pairs(exchange, trading, non_trading)
