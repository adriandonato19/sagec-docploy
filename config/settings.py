"""
Django settings wrapper for SAGEC (MICI).

Este archivo actúa como wrapper que carga la configuración desde config/settings/development.py
para que python manage.py runserver funcione sin flags adicionales.

En producción, cambiar este import a 'config.settings.production' o usar DJANGO_SETTINGS_MODULE.
"""

# Importar todas las configuraciones desde development.py usando importlib
# para evitar conflictos entre config/settings.py (archivo) y config/settings/ (directorio)
import importlib.util
from pathlib import Path

# Ruta al archivo development.py
development_path = Path(__file__).parent / 'settings' / 'development.py'
spec = importlib.util.spec_from_file_location('config.settings.development', development_path)
development_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(development_module)

# Copiar todas las variables del módulo development al namespace actual
for attr_name in dir(development_module):
    if not attr_name.startswith('_'):
        globals()[attr_name] = getattr(development_module, attr_name)
