from rest_framework import serializers

from .models import PairMetadata


class PairMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PairMetadata
        fields = ["id", "exchange", "symbol", "pair", "is_active", "created_at", "updated_at"]
