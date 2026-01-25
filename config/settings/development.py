# Importar usando importación dinámica para compatibilidad con carga desde config/settings.py
import sys
import importlib.util
from pathlib import Path

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

# 1. Modo de depuración activo para ver errores detallados
DEBUG = True

# 2. Clave secreta insegura solo para desarrollo local
SECRET_KEY = 'django-insecure-local-dev-key-mici-sagec'

# 3. Permitir cualquier host en local
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# 4. Base de Datos Local (SQLite)
# Ideal para la Fase 2 de desarrollo antes de pasar a PostgreSQL en el MICI
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 5. Desactivar restricciones de seguridad para desarrollo
# Esto evita que necesites HTTPS (SSL) en tu propia computadora
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# 6. Configuración de Correo para Pruebas
# Los correos no se envían realmente, se imprimen en la consola de VS Code
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 7. Configuración de AXES para desarrollo
# Evita que te bloquee a ti mismo si fallas la contraseña probando
AXES_ENABLED = False 

# 8. Configuración de archivos estáticos y media locales
STATICFILES_DIRS = [BASE_DIR / "static"]
