import logging
import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 15  # seconds

# --- API Endpoints ---
EXCHANGE_CONFIG = {
    "bybit-spot": {
        "url": "https://api.bybit.com/v5/market/tickers?category=spot",
        "method": "GET",
    },
    "bybit-futures": {
        "url": "https://api.bybit.com/v5/market/tickers?category=linear",
        "method": "GET",
    },
    "binance-spot": {
        "url": "https://api.binance.com/api/v3/ticker/24hr",
        "method": "GET",
    },
    "binance-futures": {
        "url": "https://fapi.binance.com/fapi/v1/ticker/24hr",
        "method": "GET",
    },
    "hyperliquid-spot": {
        "url": "https://api.hyperliquid.xyz/info",
        "method": "POST",
        "payload": {"type": "spotMetaAndAssetCtxs"},
    },
    "hyperliquid-futures": {
        "url": "https://api.hyperliquid.xyz/info",
        "method": "POST",
        "payload": {"type": "metaAndAssetCtxs"},
    },
}

SUPPORTED_EXCHANGES = list(EXCHANGE_CONFIG.keys())


# ──────────────────────────────────────────────
# Extractors  (raw JSON → normalised dicts)
# ──────────────────────────────────────────────

def _extract_bybit(data):
    results = []
    for item in data.get("result", {}).get("list", []):
        symbol = item.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        price = float(item.get("lastPrice", 0))
        prev_price = float(item.get("prevPrice24h", 0))
        change = price - prev_price
        change_pct = float(item.get("price24hPcnt", 0)) * 100
        results.append({
            "symbol": symbol,
            "price": price,
            "change": round(change, 8),
            "change_pct": round(change_pct, 4),
            "volume_usd": float(item.get("turnover24h", 0)),
            "volume_native": float(item.get("volume24h", 0)),
        })
    return results


def _extract_binance(data):
    results = []
    for item in data:
        symbol = item.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        results.append({
            "symbol": symbol,
            "price": float(item.get("lastPrice", 0)),
            "change": float(item.get("priceChange", 0)),
            "change_pct": float(item.get("priceChangePercent", 0)),
            "volume_usd": float(item.get("quoteVolume", 0)),
            "volume_native": float(item.get("volume", 0)),
        })
    return results


def _extract_hyperliquid_futures(data):
    results = []
    for universe_item, ctx_item in zip(data[0]["universe"], data[1]):
        price = float(ctx_item["markPx"])
        prev_price = float(ctx_item["prevDayPx"])
        change = price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0
        results.append({
            "symbol": universe_item["name"] + "-USD",
            "price": price,
            "change": round(change, 8),
            "change_pct": round(change_pct, 4),
            "volume_usd": float(ctx_item["dayNtlVlm"]),
            "volume_native": float(ctx_item["dayBaseVlm"]),
        })
    return results


def _extract_hyperliquid_spot(data):
    results = []
    tokens = data[0]["tokens"]
    token_map = {t["index"]: t["name"] for t in tokens}
    base_to_quote = {}
    for pair in data[0]["universe"]:
        base_idx = pair["tokens"][0]
        quote_idx = pair["tokens"][1]
        base_to_quote[base_idx] = token_map.get(quote_idx, "USDC")

    for token_item, ctx_item in zip(tokens[1:], data[1]):
        base = token_item["name"]
        quote = base_to_quote.get(token_item["index"], "USDC")
        price = float(ctx_item["markPx"])
        prev_price = float(ctx_item["prevDayPx"])
        change = price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0
        results.append({
            "symbol": f"{base}/{quote}",
            "price": price,
            "change": round(change, 8),
            "change_pct": round(change_pct, 4),
            "volume_usd": float(ctx_item["dayNtlVlm"]),
            "volume_native": float(ctx_item["dayBaseVlm"]),
        })
    return results


EXTRACTOR_MAP = {
    "bybit-spot": _extract_bybit,
    "bybit-futures": _extract_bybit,
    "binance-spot": _extract_binance,
    "binance-futures": _extract_binance,
    "hyperliquid-spot": _extract_hyperliquid_spot,
    "hyperliquid-futures": _extract_hyperliquid_futures,
}


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def fetch_exchange_prices(exchange: str, symbol=None):
    """
    Fetch live price data from an exchange.

    Args:
        exchange: One of SUPPORTED_EXCHANGES
        symbol:   Optional symbol filter (case-insensitive, partial match).
                  e.g. "BTC", "BTCUSDT", "ETH/USDC"

    Returns:
        List of normalised ticker dicts.
    """
    cfg = EXCHANGE_CONFIG[exchange]
    extract = EXTRACTOR_MAP[exchange]

    client = httpx.Client(timeout=TIMEOUT)
    try:
        if cfg["method"] == "POST":
            resp = client.post(
                cfg["url"],
                json=cfg["payload"],
                headers={"Content-Type": "application/json"},
            )
        else:
            resp = client.get(cfg["url"])
        resp.raise_for_status()
        raw = resp.json()
    finally:
        client.close()

    tickers = extract(raw)

    if symbol:
        symbol_upper = symbol.upper()
        tickers = [
            t for t in tickers
            if symbol_upper in t["symbol"].upper()
        ]

    return tickers
