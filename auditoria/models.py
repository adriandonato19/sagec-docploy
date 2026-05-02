from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class BitacoraEvento(models.Model):
    """
    Modelo para registrar eventos inmutables del sistema.
    Cumple con el requisito de trazabilidad forense.
    """
    # Tipos de eventos
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    CONSULTA_API = 'CONSULTA_API'
    CREACION_TRAMITE = 'CREACION_TRAMITE'
    CAMBIO_ESTADO = 'CAMBIO_ESTADO'
    APROBACION = 'APROBACION'
    RECHAZO = 'RECHAZO'
    FIRMA = 'FIRMA'
    DESCARGA = 'DESCARGA'
    GESTION_USUARIO = 'GESTION_USUARIO'
    SECUENCIA_AJUSTADA = 'SECUENCIA_AJUSTADA'
    PLANTILLA_CREADA = 'PLANTILLA_CREADA'
    PLANTILLA_ACTIVADA = 'PLANTILLA_ACTIVADA'
    PLANTILLA_ELIMINADA = 'PLANTILLA_ELIMINADA'

    TIPOS_EVENTO = [
        (LOGIN, 'Inicio de Sesión'),
        (LOGOUT, 'Cierre de Sesión'),
        (CONSULTA_API, 'Consulta a API Externa'),
        (CREACION_TRAMITE, 'Creación de Trámite'),
        (CAMBIO_ESTADO, 'Cambio de Estado'),
        (APROBACION, 'Aprobación de Trámite'),
        (RECHAZO, 'Rechazo de Trámite'),
        (FIRMA, 'Firma de Documento'),
        (DESCARGA, 'Descarga de Documento'),
        (GESTION_USUARIO, 'Gestión de Usuario'),
        (SECUENCIA_AJUSTADA, 'Ajuste de Secuencia'),
        (PLANTILLA_CREADA, 'Plantilla Creada'),
        (PLANTILLA_ACTIVADA, 'Plantilla Activada'),
        (PLANTILLA_ELIMINADA, 'Plantilla Eliminada'),
    ]
    
    # Campos principales
    tipo_evento = models.CharField(max_length=20, choices=TIPOS_EVENTO)
    actor = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.PROTECT, related_name='eventos_auditoria')
    ip_origen = models.GenericIPAddressField(help_text="IP del cliente que realizó la acción")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Recurso afectado (genérico para poder referenciar cualquier modelo)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    recurso_afectado = GenericForeignKey('content_type', 'object_id')
    
    # Detalles adicionales
    descripcion = models.TextField(blank=True, help_text="Descripción detallada del evento")
    metadata = models.JSONField(default=dict, blank=True, help_text="Datos adicionales en formato JSON")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Evento de Auditoría'
        verbose_name_plural = 'Eventos de Auditoría'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['tipo_evento']),
            models.Index(fields=['actor']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_evento_display()} - {self.actor.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class ConsultaSecuencia(models.Model):
    """
    Registro secuencial de cada consulta de empresa.
    Audita: qué se buscó, cuándo, quién, cuántos resultados, y a qué trámite se asoció.
    """
    numero = models.AutoField(primary_key=True)
    consulta = models.CharField(max_length=200)
    resultados_encontrados = models.PositiveIntegerField(default=0)
    resultados_detalle = models.JSONField(default=list, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        'identidad.UsuarioMICI', on_delete=models.PROTECT,
        related_name='consultas_secuencia'
    )
    ip_origen = models.GenericIPAddressField()
    tramite = models.ForeignKey(
        'tramites.Tramite', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consultas_asociadas'
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Consulta Secuencial'
        verbose_name_plural = 'Consultas Secuenciales'

    def __str__(self):
        return f"#{self.numero} - {self.consulta} - {self.usuario.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
