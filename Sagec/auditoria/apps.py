from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditoria'
    
    def ready(self):
        """Conectar signals cuando la app esté lista."""
        import auditoria.signals  # noqa