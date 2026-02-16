"""
Celery tasks for syncing trading pairs from exchanges into PairMetadata.
"""

import logging

from celery import shared_task, group
from django.conf import settings
from django.utils import timezone

from .models import PairMetadata
from .crypto_pairs import get_all_pairs

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def sync_exchange_pairs(self, exchange: str, market: str):
    """
    Fetch pairs for one exchange+market combo, upsert into PairMetadata.

    - New pairs → insert
    - Status changed → update is_active
    - Pairs in DB but gone from API → mark inactive
    """
    exchange_key = f"{exchange}-{market}"  # e.g. "binance-futures"

    try:
        result = get_all_pairs(exchange, market)
        api_active = result.get("active", [])
        api_inactive = result.get("inactive", [])

        # Build lookup: pair_name → is_active from API
        api_pairs = {}
        for p in api_active:
            api_pairs[p["pair"]] = {"symbol": p["symbol"], "is_active": True}
        for p in api_inactive:
            api_pairs[p["pair"]] = {"symbol": p["symbol"], "is_active": False}

        # Existing DB rows for this exchange
        db_pairs = {
            pm.pair: pm
            for pm in PairMetadata.objects.filter(exchange=exchange_key)
        }

        to_create = []
        to_update = []

        for pair_name, api_data in api_pairs.items():
            db_pair = db_pairs.pop(pair_name, None)

            if db_pair is None:
                to_create.append(PairMetadata(
                    exchange=exchange_key,
                    symbol=api_data["symbol"],
                    pair=pair_name,
                    is_active=api_data["is_active"],
                ))
            elif db_pair.is_active != api_data["is_active"]:
                db_pair.is_active = api_data["is_active"]
                to_update.append(db_pair)

        # Pairs in DB but not in API anymore → mark inactive
        for pair_name, db_pair in db_pairs.items():
            if db_pair.is_active:
                db_pair.is_active = False
                to_update.append(db_pair)

        if to_create:
            PairMetadata.objects.bulk_create(to_create)
        if to_update:
            PairMetadata.objects.bulk_update(to_update, ["is_active", "updated_at"])

        logger.info(
            "Synced %s: %d active, %d inactive, +%d new, ~%d updated",
            exchange_key, len(api_active), len(api_inactive),
            len(to_create), len(to_update),
        )

        return {
            "exchange": exchange_key,
            "active": len(api_active),
            "inactive": len(api_inactive),
            "created": len(to_create),
            "updated": len(to_update),
        }

    except Exception as exc:
        logger.exception("Failed to sync %s", exchange_key)
        raise self.retry(exc=exc)


@shared_task
def sync_all_pairs():
    """Fan-out: dispatch sync for every configured exchange+market in parallel."""
    combos = settings.PAIR_SYNC_EXCHANGES
    job = group(
        sync_exchange_pairs.s(combo["exchange"], combo["market"])
        for combo in combos
    )
    result = job.apply_async()
    logger.info("Dispatched %d pair sync tasks", len(combos))
    return {"dispatched": len(combos), "group_id": str(result.id)}
