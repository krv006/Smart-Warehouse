from django.db.models import Q
from rest_framework.filters import BaseFilterBackend

from apps.clients.encryption import decrypt
from apps.clients.models import Client

_ENCRYPTED_SEARCH_FIELDS = (
    'full_name',
    'first_name',
    'last_name',
    'middle_name',
    'pinfl',
    'inn',
    'passport_number',
    'director_jshshr',
    'director_fish',
)


def _normalize(value: str) -> str:
    return str(value).strip().lower()


def _compact(value: str) -> str:
    return ''.join(_normalize(value).split())


def _matches(term: str, compact_term: str, value: str | None) -> bool:
    if not value:
        return False
    plain = _normalize(value)
    if not plain:
        return False
    if term in plain:
        return True
    if compact_term and compact_term in _compact(value):
        return True
    return False


def _client_search_values(client: Client) -> list[str]:
    values: list[str] = []
    for field in _ENCRYPTED_SEARCH_FIELDS:
        plain = decrypt(getattr(client, field, None))
        if plain:
            values.append(plain)

    if client.client_type == Client.INDIVIDUAL:
        parts = [
            decrypt(client.last_name),
            decrypt(client.first_name),
            decrypt(client.middle_name),
        ]
        combined = ' '.join(part for part in parts if part).strip()
        if combined:
            values.append(combined)

    if client.company_name:
        values.append(client.company_name)
    if client.email:
        values.append(client.email)

    return values


class ClientSearchFilter(BaseFilterBackend):
    """Shifrlangan mijoz maydonlari bo'yicha qidiruv (F.I.Sh, INN, JSHSHIR, passport)."""

    search_param = 'search'

    def filter_queryset(self, request, queryset, view):
        term = request.query_params.get(self.search_param, '').strip()
        if not term:
            return queryset

        term_lower = _normalize(term)
        compact_term = _compact(term)

        db_ids = set(
            queryset.filter(
                Q(company_name__icontains=term) | Q(email__icontains=term)
            ).values_list('id', flat=True)
        )

        matched_ids = list(db_ids)
        scan_qs = queryset.exclude(id__in=db_ids) if db_ids else queryset
        for client in scan_qs.iterator(chunk_size=500):
            if any(_matches(term_lower, compact_term, value) for value in _client_search_values(client)):
                matched_ids.append(client.id)

        if not matched_ids:
            return queryset.none()
        return queryset.filter(id__in=matched_ids)
