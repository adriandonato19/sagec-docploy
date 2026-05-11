# Importar base.py dinámicamente para compatibilidad
import importlib.util
from pathlib import Path

settings_dir = Path(__file__).parent
base_path = settings_dir / 'base.py'
base_spec = importlib.util.spec_from_file_location('config.settings.base', base_path)
base_module = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base_module)
# Copiar todas las variables de base.py
for attr_name in dir(base_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(base_module, attr_name)

# 1. Blindaje de Sesiones y Cookies
# Esto evita que las sesiones sean robadas en redes públicas/gubernamentales
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# Tiempo de vida de la sesión (ej. 15 minutos de inactividad como hablamos)
SESSION_COOKIE_AGE = 900 
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# 2. Seguridad de HTTP Strict Transport Security (HSTS)
# Obliga al navegador a usar siempre HTTPS
SECURE_HSTS_SECONDS = 31536000 # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True # Redirige todo tráfico HTTP a HTTPS

# 3. Protección contra Ataques Comunes (XSS, Clickjacking)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY' # Evita que el SAGEC sea cargado en un iframe

# 4. Configuración de AXES (Protección contra Fuerza Bruta)
# Bloquea al usuario tras varios intentos fallidos
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1 # Hora de bloqueo
AXES_LOCKOUT_TEMPLATE = 'seguridad/bloqueo.html'
AXES_RESET_ON_SUCCESS = True

# 5. Configuración de Doble Factor (2FA) - django-otp
# Obligatorio para Fiscales y Firmantes según tu flujo
OTP_TOTP_ISSUER = 'SAGEC MICI'

# 6. Content Security Policy (CSP)
# Define de dónde puede cargar recursos el sistema (solo de sí mismo)
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com", "'unsafe-inline'")
# 'unsafe-inline' requerido para: importmap de TipTap, bloques <script> inline del sistema,
# y scripts de Tailwind CDN. Los CDN externos se listan explícitamente.
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.tailwindcss.com",
    "https://unpkg.com",
    "https://esm.sh",
)
CSP_CONNECT_SRC = ("'self'", "https://esm.sh")  # esm.sh resuelve sub-dependencias en runtime
CSP_IMG_SRC = ("'self'", "data:") # Permitir imágenes base64 para los logos del MICI

# 7. Restricción de IP (Estrategia C)
# Lista blanca de IPs institucionales (aquí pondrás las del MICI/Ministerio Público)
ALLOWED_ADMIN_IPS = [
    '127.0.0.1', # Local
    # 'IP_MICI_AQUI',
    # 'IP_MINISTERIO_PUBLICO_AQUI',
]
