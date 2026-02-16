from django.db import models


class PairMetadata(models.Model):
    exchange = models.CharField(max_length=50, db_index=True)  # "binance-futures", "bybit-spot", etc.
    symbol = models.CharField(max_length=50)  # "BTC"
    pair = models.CharField(max_length=100)  # "BTCUSDT"
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exchange", "pair")
        ordering = ["exchange", "symbol"]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.exchange} {self.pair} [{status}]"
