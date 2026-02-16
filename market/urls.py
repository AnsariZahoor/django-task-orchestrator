from django.urls import path
from . import views

app_name = "market"

urlpatterns = [
    # Price ticker
    path("prices/exchanges/", views.price_exchanges_list, name="price-exchanges"),
    path("prices/ticker/", views.price_ticker, name="price-ticker"),
    # Pairs (live API proxy)
    path("pairs/exchanges/", views.pairs_exchanges_list, name="pairs-exchanges"),
    path("pairs/", views.pairs_view, name="pairs"),
    # Tracked pairs (DB, populated by Celery Beat)
    path("tracked/pairs/", views.tracked_pairs, name="tracked-pairs"),
    path("tracked/sync/", views.trigger_sync, name="trigger-sync"),
]
