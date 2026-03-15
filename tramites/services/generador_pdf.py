"""
Servicio para generar PDFs de trámites usando WeasyPrint.

$Reusable$
"""
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from weasyprint import HTML
from pypdf import PdfWriter, PdfReader
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
    
    # Normalizar empresa_snapshot a lista
    snapshot = tramite.empresa_snapshot
    if isinstance(snapshot, list):
        empresas_list = snapshot
    elif isinstance(snapshot, dict) and snapshot:
        empresas_list = [snapshot]
    else:
        empresas_list = []

    # Construir ubicación completa y formatear fechas para cada empresa
    from integracion.adapters import construir_ubicacion_completa
    for emp in empresas_list:
        if 'ubicacion_completa' not in emp:
            emp['ubicacion_completa'] = construir_ubicacion_completa(emp)
        # Formatear fecha de inicio de operaciones por empresa
        fecha_inicio = emp.get('fecha_inicio_operaciones')
        if fecha_inicio:
            emp['fecha_inicio_operaciones_formateada'] = formatear_fecha_espanol(fecha_inicio)

    preguntas = list(tramite.preguntas.all())

    # Seleccionar plantilla según tipo de documento
    if tramite.tipo_documento == 'OFICIO':
        template_name = 'tramites/pdf/oficio_oficial.html'
    else:
        template_name = 'tramites/pdf/certificado_oficial.html'

    # Generar código QR
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
        'empresas': empresas_list,
        'preguntas': preguntas,
        'qr_code_data': qr_code_data,
        'fecha_emision_formateada': fecha_emision_formateada,
        'fecha_firma_formateada': fecha_firma_formateada,
        'fecha_solicitud_formateada': fecha_solicitud_formateada,
        'fecha_inicio_ops_formateada': fecha_inicio_ops_formateada,
        'logo_path': str(logo_path),
        'footer_path': str(footer_path),
    }
    
    # Renderizar plantilla HTML del documento principal
    html_content = render_to_string(template_name, context)

    # Convertir HTML a PDF
    base_url = str(settings.BASE_DIR)
    oficio_pdf = BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(oficio_pdf)
    oficio_pdf.seek(0)

    # Si es OFICIO y hay empresas, generar aviso de operación como PDF separado y fusionar
    if tramite.tipo_documento == 'OFICIO' and empresas_list:
        aviso_html = render_to_string(
            'tramites/pdf/aviso_operacion_standalone.html', context
        )
        aviso_pdf = BytesIO()
        HTML(string=aviso_html, base_url=base_url).write_pdf(aviso_pdf)
        aviso_pdf.seek(0)

        # Fusionar ambos PDFs
        writer = PdfWriter()
        for reader in [PdfReader(oficio_pdf), PdfReader(aviso_pdf)]:
            for page in reader.pages:
                writer.add_page(page)

        merged = BytesIO()
        writer.write(merged)
        merged.seek(0)
        return merged

    return oficio_pdf


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
