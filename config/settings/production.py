import importlib.util
import os
from pathlib import Path

import environ

settings_dir = Path(__file__).parent

base_path = settings_dir / 'base.py'
base_spec = importlib.util.spec_from_file_location('config.settings.base', base_path)
base_module = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base_module)
for attr_name in dir(base_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(base_module, attr_name)

security_path = settings_dir / 'security.py'
security_spec = importlib.util.spec_from_file_location('config.settings.security', security_path)
security_module = importlib.util.module_from_spec(security_spec)
security_spec.loader.exec_module(security_module)
for attr_name in dir(security_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(security_module, attr_name)

if 'BASE_DIR' not in globals():
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Fail fast on missing secrets rather than run with insecure defaults.
if not os.environ.get('SECRET_KEY'):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('SECRET_KEY environment variable is required in production.')

env = environ.Env()

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('DATABASE_URL environment variable is required in production.')

DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# HTTPS-dependent settings. Set HTTPS_ENABLED=true once TLS termination is configured
# (Traefik domain + cert). Without TLS the Secure cookie flag prevents login over HTTP.
_https = os.environ.get('HTTPS_ENABLED', '').strip().lower() in ('1', 'true', 'yes')
SESSION_COOKIE_SECURE = _https
CSRF_COOKIE_SECURE = _https
SECURE_SSL_REDIRECT = _https
SECURE_HSTS_SECONDS = 31536000 if _https else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _https
SECURE_HSTS_PRELOAD = _https

AXES_ENABLED = True

# collectstatic needs the source dir at build time
STATICFILES_DIRS = [BASE_DIR / 'static']
