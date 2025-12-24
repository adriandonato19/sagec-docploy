from .base import *

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