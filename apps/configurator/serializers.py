from rest_framework.serializers import (ModelSerializer, Serializer, ValidationError,
                                        PrimaryKeyRelatedField, IntegerField,
                                        DecimalField, CharField, ListField, DictField)

from apps.clients.models import Client
from apps.configurator.models import ServerConfiguration, ConfigurationItem
from apps.warehouse.models import Product


class ConfigurationItemSerializer(ModelSerializer):
    product_name = CharField(source='product.name', read_only=True)
    subtotal     = DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model  = ConfigurationItem
        fields = ('id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal')


class ServerConfigurationSerializer(ModelSerializer):
    items           = ConfigurationItemSerializer(many=True, read_only=True)
    total           = DecimalField(max_digits=14, decimal_places=2, read_only=True)
    created_by_name = CharField(source='created_by.__str__', read_only=True)

    class Meta:
        model  = ServerConfiguration
        fields = ('id', 'name', 'client', 'created_by', 'created_by_name',
                  'comment', 'items', 'total', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_by', 'created_by_name', 'items',
                            'total', 'created_at', 'updated_at')


class ConfigurationItemInputSerializer(Serializer):
    product  = PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = IntegerField(min_value=1, default=1)
    unit_price = DecimalField(max_digits=14, decimal_places=2, required=False,
                              allow_null=True)


class ServerConfigurationCreateSerializer(Serializer):
    """Konfiguratsiyani bir amalda (nomi + qatorlari) yaratish/tahrirlash."""
    name    = CharField(required=False, allow_blank=True, default='')
    client  = PrimaryKeyRelatedField(queryset=Client.objects.all(),
                                     required=False, allow_null=True)
    comment = CharField(required=False, allow_blank=True, allow_null=True)
    items   = ConfigurationItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise ValidationError("Kamida bitta mahsulot tanlanishi kerak.")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context['request']
        configuration = ServerConfiguration.objects.create(
            created_by=request.user, **validated_data)
        for item in items_data:
            ConfigurationItem.objects.create(configuration=configuration, **item)
        return configuration

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                ConfigurationItem.objects.create(configuration=instance, **item)
        return instance

    def to_representation(self, instance):
        return ServerConfigurationSerializer(instance, context=self.context).data
