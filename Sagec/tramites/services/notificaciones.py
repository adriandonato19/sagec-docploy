import logging
from pathlib import Path

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)

# Directorio base de la app tramites (para resolver rutas de PDFs)
_TRAMITES_DIR = Path(__file__).resolve().parent.parent


def enviar_notificacion_firma(tramite):
    """
    Envía el PDF firmado por correo al solicitante del trámite.
    Si el solicitante no tiene email registrado, registra un warning y retorna.
    Si el envío falla, registra el error sin propagar la excepción.
    """
    destinatario_email = tramite.solicitante.email
    if not destinatario_email:
        logger.warning(
            "Tramite %s firmado pero solicitante '%s' no tiene email configurado.",
            tramite.uuid,
            tramite.solicitante.username,
        )
        return

    tipo = tramite.get_tipo_documento_display()
    asunto = f"[SAGEC] {tipo} firmado - {tramite.numero_referencia}"

    context = {
        'tramite': tramite,
        'tipo': tipo,
        'solicitante': tramite.solicitante,
        'firmante': tramite.firmante,
    }

    texto_plano = render_to_string('tramites/email/documento_firmado.txt', context)
    texto_html = render_to_string('tramites/email/documento_firmado.html', context)

    mensaje = EmailMultiAlternatives(
        subject=asunto,
        body=texto_plano,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario_email],
    )
    mensaje.attach_alternative(texto_html, "text/html")

    # Adjuntar el PDF firmado si existe en disco
    if tramite.archivo_pdf_firmado and tramite.archivo_pdf_firmado.name:
        pdf_path = _TRAMITES_DIR / tramite.archivo_pdf_firmado.name
        try:
            with open(pdf_path, 'rb') as f:
                mensaje.attach(
                    f"{tramite.numero_referencia}.pdf",
                    f.read(),
                    'application/pdf',
                )
        except FileNotFoundError:
            logger.error(
                "PDF firmado no encontrado en disco para tramite %s: %s",
                tramite.uuid,
                pdf_path,
            )

    try:
        mensaje.send()
        logger.info(
            "Notificacion de firma enviada a '%s' para tramite %s.",
            destinatario_email,
            tramite.uuid,
        )
    except Exception as e:
        logger.error(
            "Error al enviar notificacion para tramite %s: %s",
            tramite.uuid,
            e,
        )
