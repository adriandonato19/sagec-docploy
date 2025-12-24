from django.db import models
import uuid

class Tramite(models.Model):
    # Definición de Estados
    BORRADOR = 'BORRADOR'       # El usuario consultó pero no ha enviado a aprobar
    PENDIENTE = 'PENDIENTE'     # Enviado para revisión del Trabajador/Director
    APROBADO = 'APROBADO'       # Validado por un Trabajador, listo para firma del Director
    FIRMADO = 'FIRMADO'         # El Director ya subió el documento con firma digital
    RECHAZADO = 'RECHAZADO'     # La solicitud fue denegada por datos incorrectos

    ESTADOS_CHOICES = [
        (BORRADOR, 'Borrador'),
        (PENDIENTE, 'Pendiente de Revisión'),
        (APROBADO, 'Aprobado para Firma'),
        (FIRMADO, 'Firmado y Finalizado'),
        (RECHAZADO, 'Rechazado'),
    ]

    # Campos principales
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tipo_documento = models.CharField(max_length=20, choices=[('OFICIO', 'Oficio'), ('CERTIFICADO', 'Certificado')])
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default=BORRADOR)
    
    # Trazabilidad (Módulo 3 y 4 de la propuesta)
    solicitante = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.PROTECT, related_name='solicitudes') 
    revisor = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisiones') 
    firmante = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.SET_NULL, null=True, blank=True, related_name='firmas') 
    
    fecha_creacion = models.DateTimeField(auto_now_add=True) 
    fecha_firma = models.DateTimeField(null=True, blank=True) 