import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Rutas del Proyecto (Ajustadas para la nueva estructura)
# BASE_DIR apunta ahora a la raíz del proyecto (donde está manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / '.env')

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
PANAMA_EMPRENDE_USER = os.environ.get('X-USER', '')
PANAMA_EMPRENDE_PASSWORD = os.environ.get('X-PASSWORD', '')