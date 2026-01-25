"""
Servicio de auditoría para registrar eventos inmutables.

$Reusable$
"""
from django.contrib.contenttypes.models import ContentType
from .models import BitacoraEvento


def registrar_evento(tipo_evento, actor, ip_origen, recurso=None, descripcion='', metadata=None):
    """
    Registra un evento en la bitácora de auditoría.
    
    Args:
        tipo_evento: Tipo de evento (constante de BitacoraEvento)
        actor: Usuario que realizó la acción
        ip_origen: IP del cliente
        recurso: Objeto afectado (opcional, cualquier modelo)
        descripcion: Descripción del evento
        metadata: Diccionario con datos adicionales
    
    $Reusable$
    """
    content_type = None
    object_id = None
    
    if recurso:
        content_type = ContentType.objects.get_for_model(recurso)
        object_id = recurso.pk
    
    BitacoraEvento.objects.create(
        tipo_evento=tipo_evento,
        actor=actor,
        ip_origen=ip_origen,
        content_type=content_type,
        object_id=object_id,
        descripcion=descripcion,
        metadata=metadata or {}
    )


def obtener_ip_cliente(request):
    """
    Obtiene la IP real del cliente desde el request.
    Considera proxies y headers X-Forwarded-For.
    
    $Reusable$
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip

