 Contexto                                                                                                                                                        │
     │                                                                                                                                                                 │
     │ Se quiere saber si es posible agregar un botón que aplique una firma digital con validez legal en Panamá directamente desde SAGEC, sin depender de herramientas │
     │  externas. El sistema ya tiene pyhanko[crypto] instalado pero sin usar. El flujo actual requiere que el Director firme externamente y suba el PDF.              │
     │                                                                                                                                                                 │
     │ Respuesta: SÍ es técnicamente posible. Pyhanko puede embeber una firma PAdES en el PDF generado por WeasyPrint. La validez legal depende de un prerequisito     │
     │ administrativo.                                                                                                                                                 │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Prerequisito Legal (no técnico)                                                                                                                                 │
     │                                                                                                                                                                 │
     │ Para que la firma sea legalmente válida en Panamá (Ley 51 del 22 de julio de 2008):                                                                             │
     │                                                                                                                                                                 │
     │ - El MICI debe obtener un certificado digital institucional del Registro Público de Panamá (Dirección Nacional de Firma Electrónica) o de un proveedor          │
     │ acreditado por la AIG.                                                                                                                                          │
     │ - El certificado llega como archivo .p12 / .pfx (PKCS#12) con contraseña, conteniendo el certificado X.509 y la clave privada.                                  │
     │ - Sin ese certificado la firma solo sería un hash SHA-256 (integridad), no una firma criptográfica con identidad verificable.                                   │
     │ - El archivo .p12 nunca va al repositorio — se guarda en el servidor y se referencia desde .env.                                                                │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Cómo Funcionaría el Botón "Firmar con Certificado"                                                                                                              │
     │                                                                                                                                                                 │
     │ Director (rol DIRECTOR) abre trámite en estado APROBADO                                                                                                         │
     │   → Hace clic en "Firmar con Certificado Digital"                                                                                                               │
     │   → Server-side: pyhanko lee el PDF ya generado                                                                                                                 │
     │   → pyhanko embebe firma PAdES-B-B con el .p12 del MICI                                                                                                         │
     │   → PDF firmado se guarda en temp_pdfs/firmados/                                                                                                                │
     │   → tramite.marcar_firmado() → estado = FIRMADO                                                                                                                 │
     │   → BitacoraEvento registra el evento                                                                                                                           │
     │                                                                                                                                                                 │
     │ El PDF resultante contiene la firma criptográfica embebida. Adobe Acrobat Reader (y otros lectores PAdES) mostrarán el panel de firmas con la identidad del     │
     │ MICI y la validez del certificado.                                                                                                                              │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Archivos a Crear / Modificar                                                                                                                                    │
     │                                                                                                                                                                 │
     │ ┌─────────────────────────────────────────┬──────────────────────────────────────────────────────────┐                                                          │
     │ │                 Archivo                 │                          Cambio                          │                                                          │
     │ ├─────────────────────────────────────────┼──────────────────────────────────────────────────────────┤                                                          │
     │ │ tramites/services/firma_digital.py      │ Nuevo — servicio que usa pyhanko para firmar             │                                                          │
     │ ├─────────────────────────────────────────┼──────────────────────────────────────────────────────────┤                                                          │
     │ │ tramites/views.py — firmar_view         │ Agregar rama accion=firmar_con_certificado               │                                                          │
     │ ├─────────────────────────────────────────┼──────────────────────────────────────────────────────────┤                                                          │
     │ │ tramites/templates/tramites/firmar.html │ Botón "Firmar con Certificado Digital" + fallback manual │                                                          │
     │ ├─────────────────────────────────────────┼──────────────────────────────────────────────────────────┤                                                          │
     │ │ config/settings/base.py                 │ SIGNING_CERT_PATH y SIGNING_CERT_PASSWORD desde .env     │                                                          │
     │ └─────────────────────────────────────────┴──────────────────────────────────────────────────────────┘                                                          │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Detalle: firma_digital.py (nuevo servicio)                                                                                                                      │
     │                                                                                                                                                                 │
     │ # tramites/services/firma_digital.py                                                                                                                            │
     │ from pyhanko.sign import signers, fields                                                                                                                        │
     │ from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata                                                                                                │
     │ from pyhanko.pdf_utils.reader import PdfFileReader                                                                                                              │
     │ from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter                                                                                       │
     │ import io                                                                                                                                                       │
     │ from django.conf import settings                                                                                                                                │
     │                                                                                                                                                                 │
     │ def firmar_pdf_con_certificado(pdf_bytes: bytes) -> bytes:                                                                                                      │
     │     """                                                                                                                                                         │
     │     Embebe firma PAdES-B-B en el PDF usando el certificado .p12 institucional.                                                                                  │
     │     Requiere SIGNING_CERT_PATH y SIGNING_CERT_PASSWORD en settings/env.                                                                                         │
     │     """                                                                                                                                                         │
     │     signer = signers.SimpleSigner.load_pkcs12(                                                                                                                  │
     │         pfx_file=settings.SIGNING_CERT_PATH,                                                                                                                    │
     │         passphrase=settings.SIGNING_CERT_PASSWORD.encode(),                                                                                                     │
     │     )                                                                                                                                                           │
     │     buf = io.BytesIO(pdf_bytes)                                                                                                                                 │
     │     writer = IncrementalPdfFileWriter(buf)                                                                                                                      │
     │     fields.append_signature_field(                                                                                                                              │
     │         writer,                                                                                                                                                 │
     │         sig_field_spec=fields.SigFieldSpec("Firma_MICI", on_page=0)                                                                                             │
     │     )                                                                                                                                                           │
     │     out = io.BytesIO()                                                                                                                                          │
     │     signers.sign_pdf(                                                                                                                                           │
     │         writer,                                                                                                                                                 │
     │         signature_meta=PdfSignatureMetadata(field_name="Firma_MICI"),                                                                                           │
     │         signer=signer,                                                                                                                                          │
     │         output=out,                                                                                                                                             │
     │     )                                                                                                                                                           │
     │     out.seek(0)                                                                                                                                                 │
     │     return out.read()                                                                                                                                           │
     │                                                                                                                                                                 │
     │ def certificado_disponible() -> bool:                                                                                                                           │
     │     """True si hay un certificado configurado en settings."""                                                                                                   │
     │     return bool(getattr(settings, 'SIGNING_CERT_PATH', None))                                                                                                   │
     │                                                                                                                                                                 │
     │ Detalle: Cambio en firmar_view                                                                                                                                  │
     │                                                                                                                                                                 │
     │ Dentro del bloque if request.method == 'POST':, agregar rama para la firma con certificado, antes de la lógica actual de upload:                                │
     │                                                                                                                                                                 │
     │ if request.POST.get('accion') == 'firmar_con_certificado':                                                                                                      │
     │     from .services.firma_digital import firmar_pdf_con_certificado                                                                                              │
     │     from pathlib import Path                                                                                                                                    │
     │     pdf_path = Path(__file__).parent / tramite.archivo_pdf.name                                                                                                 │
     │     pdf_bytes = pdf_path.read_bytes()                                                                                                                           │
     │     pdf_firmado = firmar_pdf_con_certificado(pdf_bytes)                                                                                                         │
     │     hash_documento = calcular_hash_pdf(pdf_firmado)                                                                                                             │
     │     pdf_filename = f'tramite_{tramite.uuid}_firmado.pdf'                                                                                                        │
     │     firmado_dir = Path(__file__).parent / 'temp_pdfs' / 'firmados'                                                                                              │
     │     firmado_dir.mkdir(parents=True, exist_ok=True)                                                                                                              │
     │     (firmado_dir / pdf_filename).write_bytes(pdf_firmado)                                                                                                       │
     │     tramite.archivo_pdf_firmado.name = f'temp_pdfs/firmados/{pdf_filename}'                                                                                     │
     │     tramite.marcar_firmado(request.user, hash_documento=hash_documento)                                                                                         │
     │     registrar_evento(...)  # igual que el flujo actual                                                                                                          │
     │     messages.success(request, 'Documento firmado digitalmente con certificado institucional.')                                                                  │
     │     return redirect('tramites:detalle', id=tramite.uuid)                                                                                                        │
     │                                                                                                                                                                 │
     │ Detalle: Cambios en firmar.html                                                                                                                                 │
     │                                                                                                                                                                 │
     │ - Si certificado_disponible() → mostrar botón prominente "Firmar con Certificado Digital" (POST con accion=firmar_con_certificado)                              │
     │ - Mantener la sección "Subir PDF Firmado" como alternativa/fallback (siempre visible)                                                                           │
     │                                                                                                                                                                 │
     │ Detalle: Settings                                                                                                                                               │
     │                                                                                                                                                                 │
     │ # config/settings/base.py                                                                                                                                       │
     │ SIGNING_CERT_PATH = env('SIGNING_CERT_PATH', default=None)                                                                                                      │
     │ SIGNING_CERT_PASSWORD = env('SIGNING_CERT_PASSWORD', default='')                                                                                                │
     │                                                                                                                                                                 │
     │ # .env                                                                                                                                                          │
     │ SIGNING_CERT_PATH=/ruta/segura/certificado_mici.p12                                                                                                             │
     │ SIGNING_CERT_PASSWORD=contraseña_del_certificado                                                                                                                │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Seguridad                                                                                                                                                       │
     │                                                                                                                                                                 │
     │ - El .p12 en .gitignore, permisos 400 en el servidor                                                                                                            │
     │ - Contraseña solo en .env, nunca en código                                                                                                                      │
     │ - El flujo manual de upload sigue disponible como fallback                                                                                                      │
     │ - La vista ya está protegida con @require_rol(UsuarioMICI.DIRECTOR)                                                                                             │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Para Desarrollo/Pruebas (Sin Certificado Real)                                                                                                                  │
     │                                                                                                                                                                 │
     │ Se puede generar un certificado autofirmado para probar la integración técnica:                                                                                 │
     │ openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes                                                                               │
     │ openssl pkcs12 -export -out certificado_prueba.p12 -inkey key.pem -in cert.pem                                                                                  │
     │ Adobe Reader mostrará "firma no confiable" (certificado autofirmado), pero técnicamente funciona. Con el certificado real del Registro Público mostrará "firma  │
     │ válida".                                                                                                                                                        │
     │                                                                                                                                                                 │
     │ ---                                                                                                                                                             │
     │ Verificación                                                                                                                                                    │
     │                                                                                                                                                                 │
     │ 1. Generar certificado autofirmado .p12 → configurar en .env                                                                                                    │
     │ 2. Aprobar un trámite → ir a "Firmar"                                                                                                                           │
     │ 3. Clic en "Firmar con Certificado Digital"                                                                                                                     │
     │ 4. Abrir PDF resultante en Adobe Acrobat → panel de firmas debe aparecer                                                                                        │
     │ 5. Con certificado del Registro Público: firma muestra identidad del MICI y validez  