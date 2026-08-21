"""
Buxgalter (ACCOUNTANT) tasdiqlash tizimi.

Admin (Management) va Buxgalter bir xil imkoniyatlarga ega — FAQAT Buxgalter
kiritgan/tahrirlagan yozuv Adminga tasdiqlash uchun navbatga qo'yiladi
(`PendingChange`). Admin tasdiqlaganda `apply()` haqiqiy yozuvni yaratadi/
yangilaydi; rad etsa hech narsa o'zgarmaydi.

Qamrov (atayin cheklangan — stock/pul harakatlantiradigan murakkab amallar
bevosita ishlaydi, faqat quyidagilar navbatga tushadi):
    - Mijoz (Client) yaratish/tahrirlash
    - Xarajat (Expense) yaratish/tahrirlash

`ApprovalGatedMixin`ni istalgan `ModelViewSet`ga qo'shib, `approval_create_kind`/
`approval_update_kind` belgilash orqali yangi turlarga kengaytirish mumkin —
handler funksiyasini shu yerga (`APPROVAL_HANDLERS`) ro'yxatdan o'tkazish kifoya.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import (CharField, TextField, ForeignKey, SET_NULL,
                              DateTimeField, JSONField)
from django.utils import timezone
from rest_framework.response import Response

from apps.common.models import TimeStampedModel

APPROVAL_HANDLERS = {}


def register_handler(kind):
    def decorator(func):
        APPROVAL_HANDLERS[kind] = func
        return func
    return decorator


class PendingChange(TimeStampedModel):
    PENDING  = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = (
        (PENDING,  'Kutilmoqda'),
        (APPROVED, 'Tasdiqlandi'),
        (REJECTED, 'Rad etildi'),
    )

    kind          = CharField(max_length=40,
                              help_text="Amal turi — apps/common/approval.py: APPROVAL_HANDLERS")
    summary       = CharField(max_length=255)
    payload       = JSONField(default=dict, blank=True)
    requested_by  = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                               null=True, blank=True,
                               related_name='pending_changes_requested')
    reviewed_by   = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                               null=True, blank=True,
                               related_name='pending_changes_reviewed')
    status        = CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    review_note   = TextField(blank=True, null=True)
    reviewed_at   = DateTimeField(null=True, blank=True)
    error         = TextField(blank=True, null=True,
                              help_text="Tasdiqlashda xatolik chiqsa shu yerda saqlanadi")

    class Meta:
        db_table            = 'common_pending_change'
        ordering            = ('-created_at',)
        verbose_name        = "Tasdiqlash kutilayotgan o'zgarish"
        verbose_name_plural = "Tasdiqlash kutilayotgan o'zgarishlar"

    def __str__(self):
        return f'{self.kind} — {self.summary} [{self.status}]'

    @transaction.atomic
    def approve(self, user):
        handler = APPROVAL_HANDLERS.get(self.kind)
        if handler is None:
            raise ValueError(f"Noma'lum amal turi: {self.kind}")
        handler(self.payload, requested_by=self.requested_by)
        self.status      = self.APPROVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def reject(self, user, note=''):
        self.status      = self.REJECTED
        self.reviewed_by = user
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'review_note', 'reviewed_at'])


def _notify_management_new_pending_change(pending_change):
    from django.contrib.auth import get_user_model
    from apps.notifications.models import Notification
    User = get_user_model()
    title = "Buxgalter o'zgarishi — tasdiq kutilmoqda"
    message = (f'{pending_change.requested_by} tomonidan: {pending_change.summary}. '
               "Tasdiqlash/rad etish uchun ko'rib chiqing.")
    for manager in User.objects.filter(role=User.MANAGEMENT, is_active=True):
        Notification.objects.create(recipient=manager, title=title, message=message)


class ApprovalGatedMixin:
    """
    `request.user.requires_change_approval` bo'lsa (Buxgalter), `create`/
    `update`/`partial_update` haqiqiy saqlashni bajarmaydi — `PendingChange`
    yaratadi va 202 qaytaradi. Boshqa barcha foydalanuvchilar uchun odatdagidek
    ishlaydi.
    """
    approval_create_kind = None
    approval_update_kind = None

    def _gated(self):
        return bool(self.approval_create_kind and
                    getattr(self.request.user, 'requires_change_approval', False))

    def approval_summary(self, action, data, obj=None):
        model_name = self.get_queryset().model._meta.verbose_name
        if obj is not None:
            return f'{model_name} #{obj.pk} — tahrirlash'
        return f'{model_name} — yangi yozuv'

    def _queue_pending(self, kind, payload, summary):
        from apps.common.serializers import PendingChangeSerializer
        pc = PendingChange.objects.create(
            kind=kind, payload=payload, summary=summary,
            requested_by=self.request.user,
        )
        _notify_management_new_pending_change(pc)
        return Response(PendingChangeSerializer(pc).data, status=202)

    def create(self, request, *args, **kwargs):
        if self._gated():
            return self._queue_pending(
                self.approval_create_kind, request.data,
                self.approval_summary('create', request.data))
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if self.approval_update_kind and getattr(request.user, 'requires_change_approval', False):
            obj = self.get_object()
            payload = {'object_id': obj.pk, 'data': dict(request.data), 'partial': kwargs.get('partial', False)}
            return self._queue_pending(
                self.approval_update_kind, payload,
                self.approval_summary('update', request.data, obj))
        return super().update(request, *args, **kwargs)


# ── Handlerlar ────────────────────────────────────────────────────────────────

@register_handler('client_create')
def _apply_client_create(payload, *, requested_by):
    from apps.clients.serializers import ClientSerializer
    serializer = ClientSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save(created_by=requested_by)


@register_handler('client_update')
def _apply_client_update(payload, *, requested_by):
    from apps.clients.models import Client
    from apps.clients.serializers import ClientSerializer
    obj = Client.objects.get(pk=payload['object_id'])
    serializer = ClientSerializer(obj, data=payload['data'], partial=payload.get('partial', True))
    serializer.is_valid(raise_exception=True)
    serializer.save()


@register_handler('expense_create')
def _apply_expense_create(payload, *, requested_by):
    from apps.expenses.serializers import ExpenseSerializer
    serializer = ExpenseSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save()
    if requested_by and not obj.responsible:
        obj.responsible = requested_by
        obj.save(update_fields=['responsible'])


@register_handler('expense_update')
def _apply_expense_update(payload, *, requested_by):
    from apps.expenses.models import Expense
    from apps.expenses.serializers import ExpenseSerializer
    obj = Expense.objects.get(pk=payload['object_id'])
    serializer = ExpenseSerializer(obj, data=payload['data'], partial=payload.get('partial', True))
    serializer.is_valid(raise_exception=True)
    serializer.save()
