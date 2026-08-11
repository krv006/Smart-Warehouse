from datetime import date

from django.utils import timezone


def current_year_end():
    """Joriy yilning 31-dekabr sanasi."""
    return date(timezone.localdate().year, 12, 31)
