import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .services import fetch_exchange_prices, SUPPORTED_EXCHANGES
from .crypto_pairs import (
    get_active_pairs,
    get_inactive_pairs,
    get_all_pairs,
    list_exchanges,
    get_exchange_info,
)
from .models import PairMetadata
from .serializers import PairMetadataSerializer

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Price ticker views
# ──────────────────────────────────────────────

@api_view(["GET"])
def price_exchanges_list(request):
    """List all supported exchanges for price data."""
    return Response({"exchanges": SUPPORTED_EXCHANGES})


@api_view(["GET"])
def price_ticker(request):
    """
    Fetch live price data from a CEX.

    Query params:
        exchange  (required) – e.g. binance-spot, bybit-futures, hyperliquid-spot
        symbol    (optional) – filter by symbol (partial match, case-insensitive)
                               e.g. BTC, ETHUSDT, SOL/USDC
    """
    exchange = request.query_params.get("exchange")
    symbol = request.query_params.get("symbol")

    if not exchange:
        return Response(
            {"error": "Missing required query param: exchange",
             "supported": SUPPORTED_EXCHANGES},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if exchange not in SUPPORTED_EXCHANGES:
        return Response(
            {"error": f"Unknown exchange: {exchange}",
             "supported": SUPPORTED_EXCHANGES},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        tickers = fetch_exchange_prices(exchange, symbol)
    except Exception as e:
        logger.exception("Failed to fetch prices from %s", exchange)
        return Response(
            {"error": f"Failed to fetch data from {exchange}: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({
        "exchange": exchange,
        "symbol_filter": symbol,
        "count": len(tickers),
        "data": tickers,
    })


# ──────────────────────────────────────────────
# Pairs views
# ──────────────────────────────────────────────

@api_view(["GET"])
def pairs_exchanges_list(request):
    """List all registered exchanges with their supported markets."""
    exchanges = list_exchanges()
    data = [get_exchange_info(ex) for ex in exchanges]
    return Response({"exchanges": data})


@api_view(["GET"])
def pairs_view(request):
    """
    Fetch active/inactive trading pairs from an exchange.

    Query params:
        exchange  (required) – binance | bybit | hyperliquid
        market    (required) – spot | futures
        status    (optional) – active | inactive  (omit for both)
        symbol    (optional) – filter by symbol (case-insensitive partial match)
    """
    exchange = request.query_params.get("exchange")
    market = request.query_params.get("market")
    pair_status = request.query_params.get("status")
    symbol_filter = request.query_params.get("symbol")

    available = list_exchanges()

    if not exchange:
        return Response(
            {"error": "Missing required query param: exchange", "available": available},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if exchange.lower() not in available:
        return Response(
            {"error": f"Unknown exchange: {exchange}", "available": available},
            status=status.HTTP_400_BAD_REQUEST,
        )

    info = get_exchange_info(exchange)
    supported_markets = info["supported_markets"]

    if not market:
        return Response(
            {"error": "Missing required query param: market", "supported": supported_markets},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if market not in supported_markets:
        return Response(
            {"error": f"Unsupported market '{market}' for {exchange}", "supported": supported_markets},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if pair_status and pair_status not in ("active", "inactive"):
        return Response(
            {"error": "status must be 'active' or 'inactive'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        if pair_status == "active":
            result = {"active": get_active_pairs(exchange, market), "inactive": []}
        elif pair_status == "inactive":
            result = {"active": [], "inactive": get_inactive_pairs(exchange, market)}
        else:
            result = get_all_pairs(exchange, market)
    except Exception as e:
        logger.exception("Failed to fetch pairs from %s %s", exchange, market)
        return Response(
            {"error": f"Failed to fetch pairs: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Optional symbol filter
    if symbol_filter:
        sym = symbol_filter.upper()
        result["active"] = [p for p in result["active"] if sym in p.get("symbol", "").upper() or sym in p.get("pair", "").upper()]
        result["inactive"] = [p for p in result["inactive"] if sym in p.get("symbol", "").upper() or sym in p.get("pair", "").upper()]

    return Response({
        "exchange": exchange,
        "market": market,
        "status_filter": pair_status,
        "symbol_filter": symbol_filter,
        "active_count": len(result["active"]),
        "inactive_count": len(result["inactive"]),
        "active": result["active"],
        "inactive": result["inactive"],
    })


# ──────────────────────────────────────────────
# Tracked pairs (DB-backed, populated by Celery)
# ──────────────────────────────────────────────

@api_view(["GET"])
def tracked_pairs(request):
    """
    Query DB-tracked trading pairs.

    Query params:
        exchange  (optional) – e.g. binance-futures, bybit-spot
        is_active (optional) – true | false
        symbol    (optional) – partial match (case-insensitive)
    """
    qs = PairMetadata.objects.all()

    exchange = request.query_params.get("exchange")
    is_active = request.query_params.get("is_active")
    symbol = request.query_params.get("symbol")

    if exchange:
        qs = qs.filter(exchange=exchange.lower())
    if is_active is not None:
        qs = qs.filter(is_active=is_active.lower() == "true")
    if symbol:
        qs = qs.filter(symbol__icontains=symbol)

    serializer = PairMetadataSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "results": serializer.data,
    })


@api_view(["POST"])
def trigger_sync(request):
    """Manually trigger a full sync of all exchanges."""
    from .tasks import sync_all_pairs
    result = sync_all_pairs.delay()
    return Response({
        "message": "Sync dispatched",
        "task_id": str(result.id),
    })
