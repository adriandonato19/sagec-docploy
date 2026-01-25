"""
Servicio para generar PDFs de trámites usando WeasyPrint.

$Reusable$
"""
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from weasyprint import HTML
from io import BytesIO
import hashlib
import qrcode
import base64
from datetime import datetime


def formatear_fecha_espanol(fecha):
    """
    Formatea una fecha al formato español completo.
    Ej: "3 de junio de 2025"
    
    $Reusable$
    """
    if not fecha:
        return ""
    
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    
    if isinstance(fecha, str):
        try:
            fecha = datetime.strptime(fecha, "%Y-%m-%d")
        except:
            return fecha
    
    return f"{fecha.day} de {meses[fecha.month]} de {fecha.year}"


def generar_qr_code(url_validacion):
    """
    Genera un código QR como imagen base64.
    
    Args:
        url_validacion: URL completa para validar el documento
    
    Returns:
        String con data URI de la imagen QR (base64)
    
    $Reusable$
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(url_validacion)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"


def generar_pdf_tramite(tramite):
    """
    Genera el PDF de un trámite usando WeasyPrint.
    Para certificados usa la plantilla oficial, para oficios usa la plantilla estándar.
    
    Args:
        tramite: Instancia de Tramite
    
    Returns:
        BytesIO con el contenido del PDF
    
    $Reusable$
    """
    # Obtener datos de empresa del snapshot
    empresa_data = tramite.empresa_snapshot if isinstance(tramite.empresa_snapshot, dict) else {}
    
    # Construir ubicación completa si no existe
    if 'ubicacion_completa' not in empresa_data:
        from integracion.adapters import construir_ubicacion_completa
        empresa_data['ubicacion_completa'] = construir_ubicacion_completa(empresa_data)
    
    # Determinar qué plantilla usar
    if tramite.tipo_documento == 'CERTIFICADO':
        template_name = 'tramites/pdf/certificado_oficial.html'
        
        # Generar código QR para certificados oficiales
        # URL de validación (en producción sería una URL pública)
        url_validacion = f"{settings.BASE_DIR}/validar/{tramite.uuid}"
        qr_code_data = generar_qr_code(url_validacion)
        
        # Formatear fechas en español
        fecha_emision_formateada = formatear_fecha_espanol(datetime.now())
        fecha_firma_formateada = formatear_fecha_espanol(tramite.fecha_firma) if tramite.fecha_firma else fecha_emision_formateada
        fecha_solicitud_formateada = formatear_fecha_espanol(tramite.fecha_solicitud) if tramite.fecha_solicitud else formatear_fecha_espanol(tramite.fecha_creacion)
        
        # Formatear fecha de inicio de operaciones de la empresa
        fecha_inicio_ops = empresa_data.get('fecha_inicio_operaciones')
        fecha_inicio_ops_formateada = formatear_fecha_espanol(fecha_inicio_ops) if fecha_inicio_ops else ""
        
        # Rutas a imágenes oficiales
        logo_path = settings.BASE_DIR / 'static' / 'img' / 'logo_oficial.png'
        footer_path = settings.BASE_DIR / 'static' / 'img' / 'footer_certificado.png'
        
        context = {
            'tramite': tramite,
            'empresa': empresa_data,
            'qr_code_data': qr_code_data,
            'fecha_emision_formateada': fecha_emision_formateada,
            'fecha_firma_formateada': fecha_firma_formateada,
            'fecha_solicitud_formateada': fecha_solicitud_formateada,
            'fecha_inicio_ops_formateada': fecha_inicio_ops_formateada,
            'logo_path': str(logo_path),
            'footer_path': str(footer_path),
        }
    else:
        # Para oficios, usar la plantilla estándar
        template_name = 'tramites/pdf/documento.html'
        context = {
            'tramite': tramite,
            'empresa': empresa_data,
        }
    
    # Renderizar plantilla HTML
    html_content = render_to_string(template_name, context)
    
    # Convertir HTML a PDF
    # Usar base_url para que WeasyPrint pueda cargar imágenes locales
    pdf_file = BytesIO()
    HTML(
        string=html_content,
        base_url=str(settings.BASE_DIR)
    ).write_pdf(pdf_file)
    pdf_file.seek(0)
    
    return pdf_file


def calcular_hash_pdf(pdf_bytes):
    """
    Calcula el hash SHA-256 de un PDF.
    
    Args:
        pdf_bytes: Bytes del archivo PDF
    
    Returns:
        String hexadecimal del hash SHA-256
    
    $Reusable$
    """
    return hashlib.sha256(pdf_bytes).hexdigest()
