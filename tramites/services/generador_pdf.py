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
from pathlib import Path
import hashlib
import logging
import qrcode
import base64
from datetime import datetime

from integracion.services import normalizar_noconsta_entries

logger = logging.getLogger(__name__)


PLANTILLA_FALLBACK_ESTATICA = {
    'imagen_header_path': 'static/img/logo_oficial.png',
    'imagen_footer_path': 'static/img/footer_certificado.png',
    'imagen_marca_agua_path': '',
    'imagen_header_ancho_cm': None,
    'imagen_header_alto_cm': None,
    'imagen_footer_ancho_cm': None,
    'imagen_footer_alto_cm': None,
    'imagen_marca_agua_ancho_cm': None,
    'imagen_marca_agua_alto_cm': None,
    'cuerpo_plantilla_html': '',
    'margen_superior_cm': 1.8,
    'margen_inferior_cm': 2.8,
    'margen_izquierdo_cm': 3.2,
    'margen_derecho_cm': 1.8,
}

# El sidebar de verificación (QR + código) ocupa 2.2cm fijos pegados al borde
# izquierdo de la hoja. Para que nunca invada el área de contenido necesitamos
# al menos 2.5cm de margen izquierdo (2.2 sidebar + 0.3 gap). Snapshots viejos
# o registros legacy con un valor menor se elevan a este mínimo en runtime,
# sin modificar la BD (preserva inmutabilidad documental del JSON guardado).
MARGEN_IZQUIERDO_MIN_RENDER = 2.5

# Ancho útil de la página carta menos los márgenes laterales hardcodeados
# del template (3.2cm izquierdo + 1.8cm derecho). Si una imagen del docx
# trae un wp:extent mayor, escalamos hacia abajo manteniendo aspect ratio
# para que el footer/header no se desborde.
ANCHO_CONTENIDO_MAX_CM = 19.39


def _to_float(valor):
    """Convierte Decimal/None/str a float; None se preserva."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _capar_dimensiones(ancho, alto, ancho_max=ANCHO_CONTENIDO_MAX_CM):
    """Reduce (ancho, alto) proporcionalmente si ancho > ancho_max."""
    if ancho is None or alto is None or ancho <= ancho_max:
        return ancho, alto
    factor = ancho_max / ancho
    return round(ancho_max, 2), round(alto * factor, 2)


def _clamp_margenes(snapshot):
    """Aplica defensas seguras al dict que se pasa al template.

    - margen_izquierdo_cm < MARGEN_IZQUIERDO_MIN_RENDER se eleva al mínimo
      (sidebar de QR ocupa 2.2cm fijos a la izquierda).
    - imagen_header/footer cuyo ancho excede ANCHO_CONTENIDO_MAX_CM se
      reduce proporcionalmente para no desbordarse fuera de la página.

    No muta el dict original — devuelve una copia. El JSON congelado en
    `Tramite.plantilla_snapshot` queda intacto.

    $Reusable$
    """
    if not snapshot:
        return snapshot
    seguro = dict(snapshot)
    actual = float(seguro.get('margen_izquierdo_cm', 0) or 0)
    if actual < MARGEN_IZQUIERDO_MIN_RENDER:
        seguro['margen_izquierdo_cm'] = MARGEN_IZQUIERDO_MIN_RENDER

    h_ancho, h_alto = _capar_dimensiones(
        seguro.get('imagen_header_ancho_cm'),
        seguro.get('imagen_header_alto_cm'),
    )
    seguro['imagen_header_ancho_cm'] = h_ancho
    seguro['imagen_header_alto_cm'] = h_alto

    f_ancho, f_alto = _capar_dimensiones(
        seguro.get('imagen_footer_ancho_cm'),
        seguro.get('imagen_footer_alto_cm'),
    )
    seguro['imagen_footer_ancho_cm'] = f_ancho
    seguro['imagen_footer_alto_cm'] = f_alto

    return seguro


def _resolver_plantilla(tramite):
    """Determina qué plantilla de membrete/footer aplica al trámite.

    Orden de resolución (preserva inmutabilidad documental):
        1. Si el trámite ya tiene `plantilla_snapshot`, se usa tal cual.
        2. Si existe una `PlantillaDocumento` activa para el tipo del trámite
           (o tipo `AMBOS`), se construye un snapshot a partir de ella, se
           congela en el trámite y se devuelve.
        3. Fallback a las imágenes estáticas históricas.

    En todos los casos, antes de devolver, se aplica `_clamp_margenes` para
    garantizar que el render nunca tape contenido con el sidebar.

    $Reusable$
    """
    if tramite.plantilla_snapshot:
        return _clamp_margenes(tramite.plantilla_snapshot)

    from tramites.models import PlantillaDocumento

    if tramite.tipo_documento == PlantillaDocumento.CERTIFICADO:
        plantilla = PlantillaDocumento.objects.filter(activa_certificado=True).first()
    else:
        plantilla = PlantillaDocumento.objects.filter(activa_oficio=True).first()

    if plantilla and plantilla.imagen_header and Path(plantilla.imagen_header.path).exists():
        snapshot = {
            'imagen_header_path': str(plantilla.imagen_header.path),
            'imagen_footer_path': (
                str(plantilla.imagen_footer.path)
                if plantilla.imagen_footer and Path(plantilla.imagen_footer.path).exists()
                else ''
            ),
            'imagen_marca_agua_path': (
                str(plantilla.imagen_marca_agua.path)
                if plantilla.imagen_marca_agua and Path(plantilla.imagen_marca_agua.path).exists()
                else ''
            ),
            'imagen_header_ancho_cm': _to_float(plantilla.imagen_header_ancho_cm),
            'imagen_header_alto_cm': _to_float(plantilla.imagen_header_alto_cm),
            'imagen_footer_ancho_cm': _to_float(plantilla.imagen_footer_ancho_cm),
            'imagen_footer_alto_cm': _to_float(plantilla.imagen_footer_alto_cm),
            'imagen_marca_agua_ancho_cm': _to_float(plantilla.imagen_marca_agua_ancho_cm),
            'imagen_marca_agua_alto_cm': _to_float(plantilla.imagen_marca_agua_alto_cm),
            'margen_superior_cm': float(plantilla.margen_superior_cm),
            'margen_inferior_cm': float(plantilla.margen_inferior_cm),
            'margen_izquierdo_cm': float(plantilla.margen_izquierdo_cm),
            'margen_derecho_cm': float(plantilla.margen_derecho_cm),
        }
        if tramite.pk:
            tramite.plantilla_snapshot = snapshot
            tramite.save(update_fields=['plantilla_snapshot'])
        return _clamp_margenes(snapshot)

    return _clamp_margenes(dict(PLANTILLA_FALLBACK_ESTATICA))


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


def generar_html_tramite(tramite):
    """
    Genera el HTML renderizado de un trámite (sin convertir a PDF).

    Args:
        tramite: Instancia de Tramite

    Returns:
        String con el HTML renderizado

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

    preguntas = list(tramite.preguntas.all()) if tramite.pk else []

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

    # Plantilla de membrete/footer (snapshot inmutable o plantilla activa o fallback estático)
    plantilla = _resolver_plantilla(tramite)

    # Entradas de No Consta con compatibilidad hacia snapshots legados.
    noconsta_entries = normalizar_noconsta_entries(tramite.noconsta_snapshot)

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
        'plantilla': plantilla,
        'noconsta_entries': noconsta_entries,
    }

    return render_to_string(template_name, context)


def generar_pdf_desde_html(html_content):
    """
    Convierte HTML renderizado a PDF usando WeasyPrint.

    Args:
        html_content: String con el HTML a convertir

    Returns:
        BytesIO con el contenido del PDF

    $Reusable$
    """
    base_url = str(settings.BASE_DIR)
    pdf_buffer = BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer


def generar_pdf_tramite(tramite):
    """
    Genera el PDF de un trámite usando WeasyPrint.
    Si el trámite tiene HTML editado, usa ese; si no, genera el HTML desde la plantilla.

    Args:
        tramite: Instancia de Tramite

    Returns:
        BytesIO con el contenido del PDF

    $Reusable$
    """
    if tramite.html_pdf_editado:
        html_content = tramite.html_pdf_editado
    else:
        html_content = generar_html_tramite(tramite)

    return generar_pdf_desde_html(html_content)


def sanitizar_html_para_weasyprint(html_content):
    """
    Limpia el HTML producido por TipTap para compatibilidad con WeasyPrint.

    - Convierte <mark> con data-color a <span style="background-color:...">
    - Asegura que las tablas tengan border-collapse
    - Elimina atributos data-* y clases internas de ProseMirror
    - Normaliza br vacíos de TipTap

    $Reusable$
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')

    # Convertir <mark> a <span style="background-color:..."> para WeasyPrint
    for mark in soup.find_all('mark'):
        span = soup.new_tag('span')
        # TipTap Highlight pone el color en data-color o como style
        color = mark.get('data-color')
        existing_style = mark.get('style', '')
        if color:
            span['style'] = f'background-color: {color}; {existing_style}'.strip('; ')
        elif 'background' in existing_style:
            span['style'] = existing_style
        else:
            span['style'] = 'background-color: #FFFF00'
        span.extend(list(mark.children))
        mark.replace_with(span)

    # Asegurar estilos de borde en tablas
    for table in soup.find_all('table'):
        existing = table.get('style', '')
        if 'border-collapse' not in existing:
            table['style'] = f'border-collapse: collapse; width: 100%; {existing}'.strip()

    for cell in soup.find_all(['td', 'th']):
        existing = cell.get('style', '')
        if 'border' not in existing:
            cell['style'] = f'border: 1px solid #000; padding: 4px 8px; {existing}'.strip()

    # Eliminar atributos data-* de TipTap
    for tag in soup.find_all(True):
        attrs_to_remove = [a for a in list(tag.attrs) if a.startswith('data-')]
        for attr in attrs_to_remove:
            del tag[attr]

    # Eliminar clases internas de ProseMirror
    for tag in soup.find_all(True):
        if tag.get('class'):
            clases_limpias = [c for c in tag['class'] if not c.startswith('ProseMirror')]
            if clases_limpias:
                tag['class'] = clases_limpias
            else:
                del tag['class']

    # TipTap serializa párrafos vacíos como <p></p> (sin <br>).
    # En el navegador tienen altura gracias a un <br> interno que TipTap
    # inyecta en el DOM, pero getHTML() no lo incluye.
    # WeasyPrint colapsa los <p> vacíos a altura cero, así que agregamos
    # un <br/> para que conserven una línea visible en el PDF.
    for p in soup.find_all('p'):
        if not p.get_text(strip=True) and not p.find():
            p.append(soup.new_tag('br'))

    return str(soup)


def extraer_contenido_editable(html_completo):
    """Extrae innerHTML de .document-container del HTML del PDF."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_completo, 'html.parser')
    container = soup.select_one('.document-container')
    if not container:
        raise ValueError("No se encontró .document-container en el HTML")
    return container.decode_contents()


def reinyectar_contenido_editado(html_original, contenido_editado):
    """Reemplaza innerHTML de .document-container con contenido editado.
    Aplica sanitización para compatibilidad con WeasyPrint antes de reinyectar.
    """
    from bs4 import BeautifulSoup
    contenido_sanitizado = sanitizar_html_para_weasyprint(contenido_editado)
    soup = BeautifulSoup(html_original, 'html.parser')
    container = soup.select_one('.document-container')
    if not container:
        raise ValueError("No se encontró .document-container en el HTML")
    container.clear()
    edited_soup = BeautifulSoup(contenido_sanitizado, 'html.parser')
    for child in list(edited_soup.children):
        container.append(child)
    return str(soup)


def generar_preview_plantilla(plantilla):
    """Genera un PDF de preview con datos ficticios aplicando la plantilla dada.

    No persiste el trámite ni guarda el PDF en disco — todo en memoria.

    Args:
        plantilla: instancia de `PlantillaDocumento` ya guardada en BD.

    Returns:
        bytes con el contenido del PDF de preview.

    $Reusable$
    """
    from pathlib import Path
    from tramites.models import Tramite

    snapshot_preview = _clamp_margenes({
        'imagen_header_path': str(plantilla.imagen_header.path),
        'imagen_footer_path': (
            str(plantilla.imagen_footer.path)
            if plantilla.imagen_footer and Path(plantilla.imagen_footer.path).exists()
            else ''
        ),
        'imagen_marca_agua_path': (
            str(plantilla.imagen_marca_agua.path)
            if plantilla.imagen_marca_agua and Path(plantilla.imagen_marca_agua.path).exists()
            else ''
        ),
        'imagen_header_ancho_cm': _to_float(plantilla.imagen_header_ancho_cm),
        'imagen_header_alto_cm': _to_float(plantilla.imagen_header_alto_cm),
        'imagen_footer_ancho_cm': _to_float(plantilla.imagen_footer_ancho_cm),
        'imagen_footer_alto_cm': _to_float(plantilla.imagen_footer_alto_cm),
        'imagen_marca_agua_ancho_cm': _to_float(plantilla.imagen_marca_agua_ancho_cm),
        'imagen_marca_agua_alto_cm': _to_float(plantilla.imagen_marca_agua_alto_cm),
        'margen_superior_cm': float(plantilla.margen_superior_cm),
        'margen_inferior_cm': float(plantilla.margen_inferior_cm),
        'margen_izquierdo_cm': float(plantilla.margen_izquierdo_cm),
        'margen_derecho_cm': float(plantilla.margen_derecho_cm),
    })

    tipo_documento = (
        'CERTIFICADO'
        if plantilla.tipo_aplicable in ('CERTIFICADO', 'AMBOS')
        else 'OFICIO'
    )

    empresas_demo = [
        {
            'razon_social': 'INDUSTRIAS PANAMEÑAS DE EJEMPLO, S.A.',
            'razon_comercial': 'INDUSTRIAS PANAMEÑAS DEMO',
            'numero_aviso': '123456-1-789012-2024-345678',
            'numero_licencia': 'LIC-2024-001',
            'representante_legal': 'MARÍA EJEMPLO PÉREZ',
            'cedula_representante': '8-123-456',
            'ruc': '123456-1-789012',
            'dv': '99',
            'fecha_inicio_operaciones_formateada': '15 de marzo de 2024',
            'ubicacion_completa': 'Provincia de Panamá, Distrito de Panamá, Corregimiento de Bella Vista, Calle 50, Edificio Demo, Piso 3',
            'estatus': 'Vigente',
        },
        {
            'razon_social': 'COMERCIAL DEMOSTRACIÓN, S.A.',
            'razon_comercial': 'COMERCIAL DEMO',
            'numero_aviso': '654321-1-210987-2023-876543',
            'representante_legal': 'CARLOS PRUEBA GARCÍA',
            'cedula_representante': '8-654-321',
            'ruc': '654321-1-210987',
            'estatus': 'Vigente',
        },
    ]

    tramite_dummy = Tramite(
        tipo_documento=tipo_documento,
        numero_referencia='999',
        empresa_snapshot=empresas_demo,
        noconsta_snapshot=[],
        plantilla_snapshot=snapshot_preview,
        destinatario='LICENCIADO EJEMPLO DE PREVIEW',
        titulo_destinatario='Licenciado',
        objetivo_solicitud='certificación del estado de operaciones de las empresas registradas en el sistema Panamá Emprende',
        institucion_destinatario='INSTITUCIÓN DE EJEMPLO',
        cargo_destinatario='Director General',
        numero_oficio_externo='DEMO-2026-001',
        numero_carpetilla='C-2026-DEMO',
        respuesta_solicitud=(
            'Este documento es una vista previa de cómo se verá un trámite real con la '
            'plantilla seleccionada. El contenido aquí mostrado es ficticio y solo sirve '
            'para validar márgenes, ubicación del membrete, pie de página y código QR de '
            'verificación. Los datos reales se completarán al momento de emitir el documento. '
            'Tenga en cuenta que el sistema preserva el diseño original de cada trámite ya '
            'emitido, por lo que cambios en esta plantilla no afectarán documentos previos.'
        ),
    )

    html = generar_html_tramite(tramite_dummy)
    return generar_pdf_desde_html(html).getvalue()


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
