from decimal import Decimal

from django.db import transaction
from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        SerializerMethodField)

from apps.invoices.models import ElectronicInvoice, InvoiceLineItem, VatPercent
from apps.invoices.services import sync_invoice_contract_registry
from apps.warehouse.models import Product


class InvoiceLineItemSerializer(ModelSerializer):
    unit_display = SerializerMethodField()
    vat_percent_display = SerializerMethodField()

    class Meta:
        model = InvoiceLineItem
        fields = (
            'id', 'line_number', 'product', 'product_name',
            'identification_code', 'barcode', 'unit', 'unit_display',
            'quantity', 'unit_price', 'delivery_amount',
            'vat_percent', 'vat_percent_display', 'vat_amount', 'total_amount',
        )
        read_only_fields = ('id',)

    def get_unit_display(self, obj):
        return obj.get_unit_display()

    def get_vat_percent_display(self, obj):
        return obj.get_vat_percent_display()


class ElectronicInvoiceSerializer(ModelSerializer):
    lines = InvoiceLineItemSerializer(many=True, required=False)
    client_name = SerializerMethodField()
    document_type_display = SerializerMethodField()
    total_delivery = SerializerMethodField()
    total_vat = SerializerMethodField()
    grand_total = SerializerMethodField()
    created_by_name = SerializerMethodField()

    class Meta:
        model = ElectronicInvoice
        fields = (
            'id', 'document_type', 'document_type_display', 'name',
            'contract_number', 'place_signed', 'contract_date', 'valid_until',
            'client', 'client_name', 'reverse_calculation',
            'content_title', 'content_body', 'comment',
            'lines', 'total_delivery', 'total_vat', 'grand_total',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def get_document_type_display(self, obj):
        return obj.get_document_type_display()

    def get_total_delivery(self, obj):
        if not self.context.get('can_view_prices', True):
            return None
        return obj.total_delivery

    def get_total_vat(self, obj):
        if not self.context.get('can_view_prices', True):
            return None
        return obj.total_vat

    def get_grand_total(self, obj):
        if not self.context.get('can_view_prices', True):
            return None
        return obj.grand_total

    def get_created_by_name(self, obj):
        return str(obj.created_by) if obj.created_by else None

    def _apply_product_defaults(self, line_data):
        product = line_data.get('product')
        if isinstance(product, Product):
            if not line_data.get('product_name'):
                line_data['product_name'] = product.name
            if not line_data.get('barcode') and product.barcode:
                line_data['barcode'] = product.barcode
            if not line_data.get('identification_code'):
                line_data['identification_code'] = product.serial_number
            if not line_data.get('unit'):
                line_data['unit'] = product.unit
            if line_data.get('unit_price') in (None, '', 0):
                price = product.selling_price or product.delivery_price
                if price is not None:
                    line_data['unit_price'] = price
            if line_data.get('vat_percent') in (None, '') and product.vat_percent:
                line_data['vat_percent'] = product.vat_percent
        return line_data

    def _compute_line(self, line_data, reverse):
        delivery, vat, total = InvoiceLineItem.compute_line(
            line_data.get('quantity', 1),
            line_data.get('unit_price', 0),
            line_data.get('vat_percent', VatPercent.NONE),
            delivery_amount=line_data.get('delivery_amount'),
            vat_amount=line_data.get('vat_amount'),
            total_amount=line_data.get('total_amount'),
            reverse=reverse,
        )
        line_data['delivery_amount'] = delivery
        line_data['vat_amount'] = vat
        line_data['total_amount'] = total
        return line_data

    def validate_lines(self, lines):
        if self.instance is None and not lines:
            raise ValidationError('Kamida bitta mahsulot qatori kiritilishi kerak.')
        return lines

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        reverse = validated_data.get('reverse_calculation', False)
        invoice = ElectronicInvoice.objects.create(
            created_by=self.context['request'].user,
            **validated_data,
        )
        for idx, raw in enumerate(lines_data, start=1):
            line_data = dict(raw)
            line_data.pop('id', None)
            line_data['line_number'] = line_data.get('line_number') or idx
            line_data = self._apply_product_defaults(line_data)
            line_data = self._compute_line(line_data, reverse)
            InvoiceLineItem.objects.create(invoice=invoice, **line_data)
        sync_invoice_contract_registry(invoice, created=True,
                                       user=self.context['request'].user)
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        old_reverse = instance.reverse_calculation
        reverse = validated_data.get('reverse_calculation', old_reverse)
        invoice = super().update(instance, validated_data)

        if lines_data is not None:
            keep_ids = []
            for idx, raw in enumerate(lines_data, start=1):
                line_data = dict(raw)
                line_id = line_data.pop('id', None)
                line_data['line_number'] = line_data.get('line_number') or idx
                line_data = self._apply_product_defaults(line_data)
                line_data = self._compute_line(line_data, reverse)
                if line_id:
                    line = invoice.lines.filter(pk=line_id).first()
                    if line:
                        for key, val in line_data.items():
                            setattr(line, key, val)
                        line.save()
                        keep_ids.append(line.pk)
                else:
                    obj = InvoiceLineItem.objects.create(invoice=invoice, **line_data)
                    keep_ids.append(obj.pk)
            invoice.lines.exclude(pk__in=keep_ids).delete()
        elif reverse != old_reverse:
            for line in invoice.lines.all():
                computed = self._compute_line({
                    'quantity': line.quantity,
                    'unit_price': line.unit_price,
                    'vat_percent': line.vat_percent,
                    'delivery_amount': line.delivery_amount,
                    'vat_amount': line.vat_amount,
                    'total_amount': line.total_amount,
                }, reverse)
                for key, val in computed.items():
                    setattr(line, key, val)
                line.save()
        sync_invoice_contract_registry(invoice, created=False,
                                       user=self.context['request'].user)
        return invoice
