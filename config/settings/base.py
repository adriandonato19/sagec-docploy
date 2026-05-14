import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Rutas del Proyecto (Ajustadas para la nueva estructura)
# BASE_DIR apunta ahora a la raíz del proyecto (donde está manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(name, default=''):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]

# 2. Aplicaciones (Core + Apps del Negocio)
# Aquí se refleja tu Scream Architecture
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

LOCAL_APPS = [
    'identidad',   # Gestión de usuarios gubernamentales
    'tramites',    # Núcleo: Certificados y Oficios
    'integracion', # Conexión con Panamá Emprende
    'auditoria',   # Trazabilidad inmutable
]

# Librerías de seguridad y utilidades sugeridas
THIRD_PARTY_APPS = [
    'django_otp',           # Para el 2FA obligatorio
    'django_otp.plugins.otp_totp',
    'axes',                 # Protección contra fuerza bruta
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# 3. Middleware (Ordenado por seguridad)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'identidad.middleware.ForcePasswordChangeMiddleware',
    'django_otp.middleware.OTPMiddleware', # 2FA para el MICI
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',      # Monitor de intentos de login
]

ROOT_URLCONF = 'config.urls'

# 4. Plantillas (Configuradas para buscar en tus módulos)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Carpeta global para layouts base
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-dev-key-mici-sagec')
DEBUG = _env_bool('DEBUG', default=True)
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0')
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 5. Validación de Contraseñas (Estándar Institucional)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, # Seguridad extra
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 6. Internacionalización (Localizado para Panamá)
LANGUAGE_CODE = 'es-pa'
TIME_ZONE = 'America/Panama'
USE_I18N = True
USE_TZ = True

# 7. Archivos Estáticos
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media' # Aquí se guardarán temporalmente los PDFs
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# 8. Modelo de Usuario Personalizado
# Define que el sistema use tu modelo de identidad para roles de fiscal/firmante
AUTH_USER_MODEL = 'identidad.UsuarioMICI'

# Configuración de URLs de autenticación
LOGIN_URL = 'identidad:login'  # O '/login/'
LOGIN_REDIRECT_URL = 'consultar_tramite'  # A donde ir después de loguearse
LOGOUT_REDIRECT_URL = 'identidad:login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 9. API Panamá Emprende
PANAMA_EMPRENDE_API_URL = 'https://api.panamaemprende.gob.pa/api/consulta/multiple/{busqueda}'
PANAMA_EMPRENDE_USER = os.environ.get('PANAMA_EMPRENDE_USER', '')
PANAMA_EMPRENDE_PASSWORD = os.environ.get('PANAMA_EMPRENDE_PASSWORD', '')

# 10. Firma Digital
SIGNING_CERT_PATH = os.environ.get('SIGNING_CERT_PATH', '')
SIGNING_CERT_PASSWORD = os.environ.get('SIGNING_CERT_PASSWORD', '')

# 11. Correo electrónico
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.maileroo.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'SAGEC MICI <no-reply@mici.gob.pa>')
