"""Exchange factory — registry + creation."""

from typing import Dict, List, Type
from .base import BaseExchange
from .exchanges.binance import BinanceExchange
from .exchanges.bybit import BybitExchange
from .exchanges.hyperliquid import HyperliquidExchange


class ExchangeFactory:
    """Registry for exchange adapters."""

    _registry: Dict[str, Type[BaseExchange]] = {}

    @classmethod
    def register(cls, name: str, exchange_class: Type[BaseExchange]) -> None:
        cls._registry[name.lower()] = exchange_class

    @classmethod
    def create(cls, name: str) -> BaseExchange:
        klass = cls._registry.get(name.lower())
        if not klass:
            raise ValueError(
                f"Exchange '{name}' not registered. Available: {cls.list_exchanges()}"
            )
        return klass()

    @classmethod
    def list_exchanges(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def get_exchange_info(cls, name: str) -> Dict:
        klass = cls._registry.get(name.lower())
        if not klass:
            raise ValueError(f"Exchange '{name}' not registered.")
        return {
            "name": name,
            "class": klass.__name__,
            "supported_markets": klass.get_supported_markets(),
        }


# Auto-register built-in exchanges
ExchangeFactory.register("binance", BinanceExchange)
ExchangeFactory.register("bybit", BybitExchange)
ExchangeFactory.register("hyperliquid", HyperliquidExchange)
