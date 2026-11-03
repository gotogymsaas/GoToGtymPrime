"""A password-link limit shared by every worker, independent of optional caches."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.utils import timezone

from . import conf
from .models import LinkAttemptWindow


def consume_attempt(user):
    try:
        with transaction.atomic():
            # An existing row serializes even the first counter creation on PostgreSQL.
            get_user_model()._default_manager.select_for_update().only('pk').get(pk=user.pk)
            now = timezone.now()
            window, _ = LinkAttemptWindow.objects.get_or_create(
                user=user, defaults={'expires_at': now + timedelta(seconds=conf.get('LINK_ATTEMPTS_WINDOW_SECONDS'))},
            )
            if window.expires_at <= now:
                window.attempts = 0
                window.expires_at = now + timedelta(seconds=conf.get('LINK_ATTEMPTS_WINDOW_SECONDS'))
            if window.attempts >= conf.get('LINK_MAX_ATTEMPTS'):
                return False
            window.attempts += 1
            window.save(update_fields=['attempts', 'expires_at'])
            return True
    except (DatabaseError, get_user_model().DoesNotExist):
        return False  # An unavailable limiter never permits another password guess.


def reset_attempts(user):
    with transaction.atomic():
        get_user_model()._default_manager.select_for_update().only('pk').get(pk=user.pk)
        LinkAttemptWindow.objects.filter(user=user).delete()
