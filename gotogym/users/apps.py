<<<<<<< HEAD
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
=======
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Register signal handlers
        from . import signals

>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
