"""
Signals para registrar automáticamente eventos de auditoría.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from tramites.models import Tramite
from auditoria.models import BitacoraEvento


@receiver(post_save, sender=Tramite)
def registrar_creacion_tramite(sender, instance, created, **kwargs):
    """
    Registra automáticamente la creación de un trámite.
    Nota: Este signal solo captura la creación, no los cambios de estado.
    Los cambios de estado se registran explícitamente desde las vistas.
    """
    if created:
        # Obtener IP desde el request si está disponible
        # Por ahora usamos un valor por defecto, pero en producción debería venir del request
        ip_origen = '0.0.0.0'  # Se actualizará desde las vistas cuando sea posible
        
        BitacoraEvento.objects.create(
            tipo_evento=BitacoraEvento.CREACION_TRAMITE,
            actor=instance.solicitante,
            ip_origen=ip_origen,
            content_type_id=None,  # Se puede mejorar para referenciar el trámite
            object_id=instance.pk,
            descripcion=f"Creación de {instance.get_tipo_documento_display()} - {instance.numero_referencia or instance.uuid}",
            metadata={
                'tipo_documento': instance.tipo_documento,
                'estado_inicial': instance.estado,
                'origen_consulta': instance.origen_consulta,
            }
        )

