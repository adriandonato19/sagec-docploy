from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from pathlib import Path
import uuid
import json

class Tramite(models.Model):
    # Definición de Estados
    BORRADOR = 'BORRADOR'       # El usuario consultó pero no ha enviado a aprobar
    PENDIENTE = 'PENDIENTE'     # Enviado para revisión del Trabajador/Director
    EN_REVISION = 'EN_REVISION'  # Solicitud aprobada, documento en revisión final
    APROBADO = 'APROBADO'       # Documento aprobado, pendiente de firma del Director
    FIRMADO = 'FIRMADO'         # El Director ya subió el documento con firma digital
    RECHAZADO = 'RECHAZADO'     # La solicitud fue denegada por datos incorrectos

    ESTADOS_CHOICES = [
        (BORRADOR, 'Borrador'),
        (PENDIENTE, 'Pendiente de Revisión'),
        (EN_REVISION, 'En revisión'),
        (APROBADO, 'Aprobado'),
        (FIRMADO, 'Firmado y Finalizado'),
        (RECHAZADO, 'Rechazado'),
    ]

    # Campos principales
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tipo_documento = models.CharField(max_length=20, choices=[('OFICIO', 'Oficio'), ('CERTIFICADO', 'Certificado')])
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default=BORRADOR)
    numero_referencia = models.CharField(max_length=50, blank=True, help_text="Número de referencia humano-legible")
    
    # Datos de la empresa (snapshot inmutable)
    empresa_snapshot = models.JSONField(default=list, help_text="Snapshot de datos de la empresa al momento de creación")
    numero_carpetilla = models.CharField(max_length=100, blank=True, help_text="Número de carpetilla (solo para oficios)")
    origen_consulta = models.CharField(max_length=100, blank=True, help_text="RUC o número de aviso consultado")
    noconsta_snapshot = models.JSONField(default=list, help_text="Lista de entradas de 'No Consta' escritas manualmente por el fiscal")

    # Trazabilidad (Módulo 3 y 4 de la propuesta)
    solicitante = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.PROTECT, related_name='solicitudes') 
    revisor = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisiones') 
    firmante = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.SET_NULL, null=True, blank=True, related_name='firmas') 
    
    # Campos adicionales para PDF y firma
    hash_seguridad = models.CharField(max_length=64, blank=True, help_text="SHA-256 del documento firmado")
    archivo_pdf = models.FileField(upload_to='pdfs/', null=True, blank=True, help_text="PDF original generado al crear el trámite")
    archivo_pdf_firmado = models.FileField(upload_to='pdfs/firmados/', null=True, blank=True, help_text="PDF firmado externamente y subido por el director")
    motivo_rechazo = models.TextField(blank=True, help_text="Motivo del rechazo si aplica")
    html_pdf_editado = models.TextField(blank=True, default='', help_text="HTML editado del PDF (si fue modificado)")
    
    # Campos adicionales del trámite
    destinatario = models.CharField(max_length=200, blank=True, help_text="Nombre del destinatario del documento (ej: Señor LUIS ABREGO)")
    proposito = models.TextField(blank=True, help_text="Propósito del trámite (ej: traspaso vehicular)")
    objetivo_solicitud = models.TextField(blank=True, help_text="Objetivo de la solicitud (ej: autenticación de certificado de operación)")
    fecha_solicitud = models.DateField(null=True, blank=True, help_text="Fecha en que el MICI recibió la solicitud")

    # Campos adicionales para oficios
    numero_oficio_externo = models.CharField(max_length=200, blank=True, help_text="Número de oficio externo (referencia del solicitante, ej: 7487/202500039050/sl)")
    titulo_destinatario = models.CharField(max_length=100, blank=True, help_text="Título del destinatario (ej: Licenciada, Señor)")
    cargo_destinatario = models.TextField(blank=True, help_text="Cargo del destinatario (ej: Fiscal Adjunta de la Fiscalía Anticorrupción...)")
    institucion_destinatario = models.CharField(max_length=200, blank=True, help_text="Institución del destinatario (ej: MINISTERIO PÚBLICO)")
    respuesta_solicitud = models.TextField(blank=True, help_text="Respuesta libre a la solicitud (llenada durante revisión)")

    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True) 
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    fecha_firma = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Trámite'
        verbose_name_plural = 'Trámites'
    
    def __str__(self):
        return f"{self.get_tipo_documento_display()} - {self.numero_referencia or str(self.uuid)[:8]}"
    
    def enviar(self):
        """Transición: BORRADOR -> PENDIENTE"""
        if self.estado != self.BORRADOR:
            raise ValidationError(f"No se puede enviar un trámite en estado {self.get_estado_display()}")
        self.estado = self.PENDIENTE
        self.fecha_envio = timezone.now()
        self.save()
    
    @property
    def empresas_snapshot_list(self):
        """Retorna empresa_snapshot como lista (maneja tanto dict como list)."""
        if isinstance(self.empresa_snapshot, list):
            return self.empresa_snapshot
        if isinstance(self.empresa_snapshot, dict) and self.empresa_snapshot:
            return [self.empresa_snapshot]
        return []

    @property
    def empresa_principal(self):
        """Retorna la primera empresa del snapshot para backward compatibility."""
        lista = self.empresas_snapshot_list
        return lista[0] if lista else {}

    def aprobar(self, revisor):
        """Transición: PENDIENTE -> EN_REVISION"""
        if self.estado != self.PENDIENTE:
            raise ValidationError(f"No se puede aprobar un trámite en estado {self.get_estado_display()}")
        if not revisor.puede_aprobar:
            raise ValidationError("El usuario no tiene permisos para aprobar")
        # Verificar que todas las preguntas estén respondidas
        preguntas_sin_responder = self.preguntas.filter(texto_respuesta='')
        if preguntas_sin_responder.exists():
            raise ValidationError("Todas las preguntas deben ser respondidas antes de aprobar.")
        self.estado = self.EN_REVISION
        self.revisor = revisor
        self.fecha_revision = timezone.now()
        self.save()

    def aprobar_pdf(self, revisor):
        """Transición: EN_REVISION -> APROBADO"""
        if self.estado != self.EN_REVISION:
            raise ValidationError(f"No se puede aprobar el PDF en estado {self.get_estado_display()}")
        if not revisor.puede_aprobar:
            raise ValidationError("El usuario no tiene permisos para aprobar el PDF")
        self.estado = self.APROBADO
        self.save(update_fields=['estado'])

    def limpiar_borrador_pdf(self):
        """Elimina el PDF temporal y limpia el HTML editado asociado."""
        if self.archivo_pdf and self.archivo_pdf.name:
            pdf_path = Path(__file__).parent / self.archivo_pdf.name
            if pdf_path.exists():
                pdf_path.unlink()
        self.archivo_pdf = None
        self.html_pdf_editado = ''

    def regresar(self, revisor):
        """Retrocede el trámite un paso en el flujo de revisión."""
        if not revisor.puede_aprobar:
            raise ValidationError("El usuario no tiene permisos para regresar el trámite")

        if self.estado == self.APROBADO:
            self.estado = self.EN_REVISION
            self.save(update_fields=['estado'])
            return

        if self.estado == self.EN_REVISION:
            self.limpiar_borrador_pdf()
            self.estado = self.PENDIENTE
            self.save(update_fields=['estado', 'archivo_pdf', 'html_pdf_editado'])
            return

        raise ValidationError(f"No se puede regresar un trámite en estado {self.get_estado_display()}")
    
    def rechazar(self, revisor, motivo):
        """Transición: PENDIENTE -> RECHAZADO"""
        if self.estado != self.PENDIENTE:
            raise ValidationError(f"No se puede rechazar un trámite en estado {self.get_estado_display()}")
        if not revisor.puede_aprobar:
            raise ValidationError("El usuario no tiene permisos para rechazar")
        if not motivo.strip():
            raise ValidationError("Debe indicar el motivo del rechazo")
        self.estado = self.RECHAZADO
        self.revisor = revisor
        self.motivo_rechazo = motivo.strip()
        self.fecha_revision = timezone.now()
        self.save()
    
    def marcar_firmado(self, firmante, hash_documento=None):
        """Transición: APROBADO -> FIRMADO
        
        Nota: El archivo_pdf_firmado debe ser guardado antes de llamar a este método
        usando tramite.archivo_pdf_firmado.save()
        """
        if self.estado != self.APROBADO:
            raise ValidationError(f"No se puede firmar un trámite en estado {self.get_estado_display()}")
        if not firmante.puede_firmar:
            raise ValidationError("El usuario no tiene permisos para firmar")
        self.estado = self.FIRMADO
        self.firmante = firmante
        self.fecha_firma = timezone.now()
        if hash_documento:
            self.hash_seguridad = hash_documento
        self.save()


class PreguntaOficio(models.Model):
    tramite = models.ForeignKey(Tramite, on_delete=models.CASCADE, related_name='preguntas')
    orden = models.PositiveIntegerField(default=0)
    texto_pregunta = models.TextField()
    texto_respuesta = models.TextField(blank=True)
    respondida_por = models.ForeignKey('identidad.UsuarioMICI', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"Pregunta {self.orden} - Trámite {self.tramite_id}"

    @property
    def esta_respondida(self):
        return bool(self.texto_respuesta.strip())
