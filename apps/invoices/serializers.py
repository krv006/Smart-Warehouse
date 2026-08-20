from decimal import Decimal

from django.db import transaction
from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        PrimaryKeyRelatedField,
                                        SerializerMethodField)

from apps.invoices.expense_sync import sync_invoice_expense
from apps.invoices.models import ElectronicInvoice, ExecutorType, InvoiceLineItem, VatPercent
from apps.invoices.services import sync_invoice_contract_registry
from apps.warehouse.models import Product, ProductUnit  # Category vaqtincha ishlatilmaydi


class InvoiceLineItemSerializer(ModelSerializer):
    unit_display = SerializerMethodField()
    vat_percent_display = SerializerMethodField()
    # Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
    # category = PrimaryKeyRelatedField(queryset=Category.objects.all(),
    #                                   required=False, allow_null=True,
    #                                   write_only=True)

    class Meta:
        model = InvoiceLineItem
        fields = (
            'id', 'line_number', 'product', 'product_name',
            'identification_code', 'barcode', 'unit', 'unit_display',
            'quantity', 'unit_price', 'selling_price', 'delivery_amount',
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
    executor_name = SerializerMethodField()
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
            'client', 'client_name', 'executor_type', 'executor_client', 'executor_name',
            'reverse_calculation',
            'content_title', 'content_body', 'comment',
            'lines', 'total_delivery', 'total_vat', 'grand_total',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def get_executor_name(self, obj):
        if obj.executor_type == ExecutorType.CLIENT and obj.executor_client:
            return str(obj.executor_client)
        return None

    def validate(self, attrs):
        executor_type = attrs.get(
            'executor_type',
            getattr(self.instance, 'executor_type', ExecutorType.COMPANY_PROFILE),
        )
        executor_client = attrs.get(
            'executor_client',
            getattr(self.instance, 'executor_client', None),
        )
        if executor_type == ExecutorType.CLIENT and not executor_client:
            raise ValidationError({'executor_client': 'Bajaruvchi korxonani tanlang.'})
        if executor_type == ExecutorType.COMPANY_PROFILE:
            attrs['executor_client'] = None
        client = attrs.get('client', getattr(self.instance, 'client', None))
        exec_client = attrs.get('executor_client', getattr(self.instance, 'executor_client', None))
        if (
            executor_type == ExecutorType.CLIENT
            and client
            and exec_client
            and client.pk == exec_client.pk
        ):
            raise ValidationError({
                'executor_client': 'Bajaruvchi va buyurtmachi bir xil bo‘lmasin.',
                'client': 'Bajaruvchi va buyurtmachi bir xil bo‘lmasin.',
            })
        return attrs

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

    def _resolve_line_product(self, line_data):
        """Qatordagi tovarni omborda topadi; bo'lmasa YANGI mahsulot yaratadi.

        Yangi mahsulot holati `import` bo'lib qo'shiladi — ombor ro'yxatida
        u "Import" deb ko'rsatiladi.
        """
        from apps.warehouse.models import ProductOrigin
        from apps.warehouse.product_utils import (create_import_product, find_product,
                                                   normalize_product_serial)

        if isinstance(line_data.get('product'), Product):
            return line_data
        name = (line_data.get('product_name') or '').strip()
        if not name:
            return line_data
        # `_check_duplicate_new_serials` (validate_lines) shu qatordagi
        # seriya raqamini allaqachon qidirgan bo'lishi mumkin — topilgan
        # bo'lsa qayta so'rov yubormasdan o'sha natijadan foydalanamiz.
        serial = normalize_product_serial(line_data.get('identification_code'))
        cached = getattr(self, '_serial_product_cache', {}).get(serial) if serial else None
        product = cached or find_product(
            name=name,
            serial_number=line_data.get('identification_code'),
            barcode=line_data.get('barcode'),
        )
        if product is None:
            product = create_import_product({
                'name': name,
                'serial_number': line_data.get('identification_code'),
                'barcode': line_data.get('barcode'),
                'unit': line_data.get('unit'),
                'vat_percent': line_data.get('vat_percent'),
                # qatordagi «Narxi» — KELISH narxi, «Sotuv narxi» — ketish
                'purchase_price': line_data.get('unit_price') or None,
                'selling_price': line_data.get('selling_price') or None,
            }, origin=ProductOrigin.IMPORT)
            # Yangi mahsulot import bo'limiga ham tushishi kerak — hujjat
            # saqlangandan keyin zakaz (import) yozuvi ochiladi
            if not hasattr(self, '_auto_import_lines'):
                self._auto_import_lines = []
            self._auto_import_lines.append({
                'product': product,
                'quantity': line_data.get('quantity') or 1,
                'unit_price': line_data.get('unit_price') or None,
                'selling_price': line_data.get('selling_price') or None,
                'vat_percent': line_data.get('vat_percent') or 'none',
            })
        line_data['product'] = product
        return line_data

    def _create_auto_imports(self, invoice):
        """Buyurtmada yangi ochilgan mahsulotlar uchun import (zakaz) yozuvi.

        Qatordagi «Narxi» — kelish narxi (`unit_price`), «Sotuv narxi» —
        `selling_price`. To'lov holati "to'lanmagan" bo'lib boshlanadi;
        keyingisini operator import bo'limida yuritadi.
        """
        import uuid

        from apps.orders.models import (ProductContract, Zakaz, ZakazHistory,
                                        register_contract)

        lines = getattr(self, '_auto_import_lines', [])
        if not lines:
            return set()
        user = self.context['request'].user
        batch_id = uuid.uuid4()
        asos = (f'Buyurtma №{invoice.contract_number or "—"} qatoridagi yangi '
                f'mahsulot — import bo\'limiga avtomatik qo\'shildi.')
        for line in lines:
            zakaz = Zakaz.objects.create(
                product=line['product'],
                zakaz_type=Zakaz.MANUAL,
                quantity=line['quantity'],
                unit_price=line['unit_price'],
                selling_price=line['selling_price'],
                vat_percent=line['vat_percent'],
                status=Zakaz.NEW,
                payment_status=Zakaz.UNPAID,
                contract_number=invoice.contract_number,
                contract_date=invoice.contract_date,
                import_batch=batch_id,
                comment=asos,
                created_by=user if user.is_authenticated else None,
            )
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=zakaz.created_by,
                action=ZakazHistory.CREATED, new_status=Zakaz.NEW,
                contract_number=invoice.contract_number,
                contract_date=invoice.contract_date,
                asos=asos,
            )
            register_contract(
                zakaz.product, ProductContract.ZAKAZ_CREATED,
                contract_number=invoice.contract_number,
                contract_date=invoice.contract_date,
                asos=asos, zakaz=zakaz, user=zakaz.created_by,
            )
        product_ids = {line['product'].pk for line in lines if line.get('product')}
        self._auto_import_lines = []
        return product_ids

    def _apply_product_defaults(self, line_data):
        product = line_data.get('product')
        if isinstance(product, Product):
            line_data['product_name'] = product.name
            line_data['identification_code'] = product.serial_number or line_data.get('identification_code', '')
            line_data['barcode'] = product.barcode or line_data.get('barcode', '')
            line_data['unit'] = product.unit or line_data.get('unit') or ProductUnit.PIECE
            if line_data.get('unit_price') in (None, '', 0):
                # «Narxi» — KELISH narxi
                price = product.purchase_price or product.delivery_price
                if price is not None:
                    line_data['unit_price'] = price
            if line_data.get('selling_price') in (None, '') and product.selling_price is not None:
                line_data['selling_price'] = product.selling_price
            if line_data.get('vat_percent') in (None, '', VatPercent.NONE) and product.vat_percent:
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
        self._check_duplicate_new_serials(lines)
        return lines

    def _check_duplicate_new_serials(self, lines):
        """Bitta so'rov ichida bir xil seriya raqami ikki xil nom bilan
        kelmasin — aks holda ikkinchi qator birinchi qator yaratgan
        mahsulotga jimgina bog'lanib, o'z nomi/mahsuloti yo'qoladi (chunki
        qatorlar ketma-ket saqlanadi va keyingi qator seriya bo'yicha
        avvalgisini topib oladi).
        """
        from apps.warehouse.product_utils import find_product, normalize_product_serial

        # `_resolve_line_product` (create/update) shu seriya bo'yicha
        # topilgan mahsulotni qayta so'ramasdan shu keshdan olishi uchun.
        self._serial_product_cache = {}
        seen = {}
        for index, line in enumerate(lines, start=1):
            if isinstance(line.get('product'), Product):
                continue  # FK aniq berilgan — chalkashlik yo'q
            serial = normalize_product_serial(line.get('identification_code'))
            if not serial:
                continue
            existing = find_product(serial_number=serial)
            self._serial_product_cache[serial] = existing
            if existing:
                continue  # omborda ALLAQACHON mavjud mahsulot
            name = (line.get('product_name') or '').strip().lower()
            if serial in seen and seen[serial][0] != name:
                raise ValidationError(
                    f'{index}-qator: "{serial}" seriya raqami '
                    f'{seen[serial][1]}-qatorda boshqa mahsulot nomi '
                    f'("{line.get("product_name")}" ≠ oldingi qator) bilan '
                    f'ishlatilgan — bitta seriya raqami bitta mahsulotga tegishli '
                    f'bo\'lishi kerak.')
            seen.setdefault(serial, (name, index))

    @transaction.atomic
    def create(self, validated_data):
        from apps.common.contracts import allocate_contract_number

        self._auto_import_lines = []
        lines_data = validated_data.pop('lines', [])
        reverse = validated_data.get('reverse_calculation', False)
        if not (validated_data.get('contract_number') or '').strip():
            # Har kun uchun alohida o'suvchi tartib raqam: 1/1308, 2/1308, ...
            validated_data['contract_number'] = allocate_contract_number(
                validated_data.get('contract_date'))
        invoice = ElectronicInvoice.objects.create(
            created_by=self.context['request'].user,
            **validated_data,
        )
        for idx, raw in enumerate(lines_data, start=1):
            line_data = dict(raw)
            line_data.pop('id', None)
            line_data['line_number'] = line_data.get('line_number') or idx
            line_data = self._resolve_line_product(line_data)
            line_data = self._apply_product_defaults(line_data)
            line_data = self._compute_line(line_data, reverse)
            InvoiceLineItem.objects.create(invoice=invoice, **line_data)
        sync_invoice_contract_registry(invoice, created=True,
                                       user=self.context['request'].user)
        self._create_auto_imports(invoice)
        sync_invoice_expense(invoice, user=self.context['request'].user)
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        self._auto_import_lines = []
        lines_data = validated_data.pop('lines', None)
        old_reverse = instance.reverse_calculation
        reverse = validated_data.get('reverse_calculation', old_reverse)
        invoice = super().update(instance, validated_data)

        if lines_data is not None:
            existing_lines = {line.pk: line for line in invoice.lines.all()}
            keep_ids = []
            for idx, raw in enumerate(lines_data, start=1):
                line_data = dict(raw)
                line_id = line_data.pop('id', None)
                line_data['line_number'] = line_data.get('line_number') or idx
                line_data = self._resolve_line_product(line_data)
                line_data = self._apply_product_defaults(line_data)
                line_data = self._compute_line(line_data, reverse)
                if line_id:
                    line = existing_lines.get(line_id)
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
        self._create_auto_imports(invoice)
        sync_invoice_expense(invoice, user=self.context['request'].user)
        return invoice
