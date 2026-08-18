import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
COMMERCIAL_PROJECT_DIR = Path(os.environ.get("GOTOGYM_PROJECT_DIR", BASE_DIR.parent / "gotogym")).resolve()

if str(COMMERCIAL_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(COMMERCIAL_PROJECT_DIR))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "gotogym-admin-local-key")
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "products",
    "administracion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gotogym_admin_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "gotogym_admin_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": COMMERCIAL_PROJECT_DIR / "db_local.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

MEDIA_URL = "/media/"
MEDIA_ROOT = COMMERCIAL_PROJECT_DIR / "media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin_dashboard"
LOGOUT_REDIRECT_URL = "login"
