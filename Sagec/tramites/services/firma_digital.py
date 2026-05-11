"""
Servicio de firma digital PAdES-B-B usando certificado .p12 del servidor.
"""
import os
from io import BytesIO
import pdfplumber
from django.conf import settings
from pyhanko import stamp
from pyhanko.pdf_utils import text
from pyhanko.sign import signers, fields
from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata, PdfSigner
from pyhanko.sign.fields import SigFieldSpec
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter


def _resolver_ruta_cert() -> str:
    """Resuelve la ruta del certificado contra BASE_DIR si es relativa."""
    path = settings.SIGNING_CERT_PATH
    if path and not os.path.isabs(path):
        path = os.path.join(settings.BASE_DIR, path)
    return path


def certificado_disponible() -> bool:
    """Verifica que el .p12 exista en la ruta configurada."""
    path = _resolver_ruta_cert()
    return bool(path) and os.path.isfile(path)


def _encontrar_posicion_firma(pdf_bytes: bytes) -> tuple:
    """
    Busca "Atentamente" y el nombre del firmante en el PDF para calcular
    la posición del sello de firma digital entre ambos.
    Retorna (page_index, x1, y1, x2, y2) en coordenadas PDF (origen abajo-izquierda).
    """
    pdf = pdfplumber.open(BytesIO(pdf_bytes))
    page_height = 792  # letter

    for i, page in enumerate(pdf.pages):
        page_height = page.height
        words = page.extract_words()

        atentamente_bottom = None
        firmante_top = None

        for word in words:
            if 'Atentamente' in word['text']:
                # bottom en coordenadas pdfplumber (top-down)
                atentamente_bottom = word['bottom']
            if atentamente_bottom and word['text'] in ('Directora', 'Director', '[NOMBRE'):
                firmante_top = word['top']
                break

        if atentamente_bottom is not None:
            # Convertir de pdfplumber (top-down) a PDF coords (bottom-up)
            if firmante_top is None:
                # Fallback: usar 2.2cm (~62pts) debajo de Atentamente
                firmante_top = atentamente_bottom + 62

            # Coordenadas PDF (y desde abajo)
            y_top = page_height - atentamente_bottom - 5   # 5pts debajo de "Atentamente,"
            y_bottom = page_height - firmante_top + 5       # 5pts arriba del nombre

            # x: alineado con el texto del documento (~142pts desde izquierda)
            x_left = 142
            x_right = 380

            pdf.close()
            return (i, x_left, y_bottom, x_right, y_top)

    pdf.close()
    # Fallback: última página, posición genérica
    total_pages = len(pdf.pages) if hasattr(pdf, 'pages') else 1
    return (total_pages - 1, 142, 620, 380, 680)


def firmar_pdf_con_certificado(pdf_bytes: bytes) -> bytes:
    """
    Lee el .p12 configurado, firma el PDF con PAdES-B-B y retorna los bytes firmados.
    Coloca el sello visual justo después de "Atentamente,".
    """
    cert_path = _resolver_ruta_cert()
    cert_password = settings.SIGNING_CERT_PASSWORD

    if not cert_path or not os.path.isfile(cert_path):
        raise FileNotFoundError(f'Certificado .p12 no encontrado en: {cert_path}')

    # Cargar el signer desde el archivo PKCS#12
    signer = signers.SimpleSigner.load_pkcs12(
        pfx_file=cert_path,
        passphrase=cert_password.encode('utf-8') if cert_password else None,
    )

    # Encontrar posición para el sello de firma
    page_idx, x1, y1, x2, y2 = _encontrar_posicion_firma(pdf_bytes)

    # Preparar el PDF para firma incremental
    writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))

    # Agregar campo de firma visible en el espacio después de "Atentamente,"
    fields.append_signature_field(
        writer,
        SigFieldSpec(
            sig_field_name='Firma_MICI',
            on_page=page_idx,
            box=(x1, y1, x2, y2),
        ),
    )

    # Metadatos de la firma
    signature_meta = PdfSignatureMetadata(
        field_name='Firma_MICI',
        subfilter=fields.SigSeedSubFilter.PADES,
    )

    # Estilo visual del sello de firma
    stamp_style = stamp.TextStampStyle(
        stamp_text='Firmado digitalmente por:\n%(signer)s\nFecha: %(ts)s',
        text_box_style=text.TextBoxStyle(),
        border_width=1,
    )

    # Firmar con sello visual
    pdf_signer = PdfSigner(
        signature_meta,
        signer=signer,
        stamp_style=stamp_style,
    )

    output = BytesIO()
    pdf_signer.sign_pdf(writer, output=output)

    return output.getvalue()
