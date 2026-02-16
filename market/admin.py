from django.contrib import admin

from .models import PairMetadata


@admin.register(PairMetadata)
class PairMetadataAdmin(admin.ModelAdmin):
    list_display = ("exchange", "symbol", "pair", "is_active", "created_at", "updated_at")
    list_filter = ("exchange", "is_active")
    search_fields = ("symbol", "pair")
    readonly_fields = ("created_at", "updated_at")
