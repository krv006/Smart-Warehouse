def apply_date_range(qs, request, field='created_at'):
    """Filter queryset by optional date_from / date_to query params (YYYY-MM-DD)."""
    params = request.query_params
    if params.get('date_from'):
        qs = qs.filter(**{f'{field}__gte': params['date_from']})
    if params.get('date_to'):
        qs = qs.filter(**{f'{field}__lte': params['date_to']})
    return qs
