import importlib.util
import os
from pathlib import Path

import environ

# Detectar si estamos siendo cargados dinámicamente (cuando __package__ es None)
# o si estamos siendo importados normalmente
settings_dir = Path(__file__).parent

# Cargar base.py
base_path = settings_dir / 'base.py'
base_spec = importlib.util.spec_from_file_location('config.settings.base', base_path)
base_module = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base_module)
# Copiar todas las variables de base.py (incluyendo BASE_DIR)
for attr_name in dir(base_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(base_module, attr_name)

# Asegurar que BASE_DIR esté disponible
if 'BASE_DIR' not in globals():
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Cargar security.py
security_path = settings_dir / 'security.py'
security_spec = importlib.util.spec_from_file_location('config.settings.security', security_path)
security_module = importlib.util.module_from_spec(security_spec)
security_spec.loader.exec_module(security_module)
# Copiar todas las variables de security.py
for attr_name in dir(security_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(security_module, attr_name)

env = environ.Env()
TRUE_VALUES = {'1', 'true', 'yes', 'on'}

# 1. Base de Datos: PostgreSQL en Railway cuando exista DATABASE_URL, SQLite local como fallback.
database_url = os.environ.get('DATABASE_URL')
use_database_url = os.environ.get('USE_DATABASE_URL')
if use_database_url is None:
    use_database_url = not DEBUG
else:
    use_database_url = use_database_url.strip().lower() in TRUE_VALUES

if database_url and use_database_url:
    DATABASES = {
        'default': env.db('DATABASE_URL'),
    }
    DATABASES['default']['CONN_MAX_AGE'] = 60
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# 2. Desactivar restricciones de seguridad en entorno de desarrollo/staging.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# 3. Configuración de Correo para Pruebas
# Los correos no se envían realmente, se imprimen en la consola de VS Code
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 4. Configuración de AXES para desarrollo
# Evita que te bloquee a ti mismo si fallas la contraseña probando
AXES_ENABLED = not DEBUG

# 5. Configuración de archivos estáticos y media locales
STATICFILES_DIRS = [BASE_DIR / "static"]
