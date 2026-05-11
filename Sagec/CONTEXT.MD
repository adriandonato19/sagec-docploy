Este es el Plan Maestro de Desarrollo para el SAGEC (MICI), diseñado específicamente para cumplir con la arquitectura Scream Architecture (donde la estructura de carpetas "grita" la funcionalidad del negocio y no el framework), utilizando Django Puro y bajo la estrategia de seguridad "Público pero Blindado".
Este plan cubre exclusivamente la Etapa de Desarrollo (Coding).
1. Filosofía Arquitectónica: Scream Architecture en Django
En lugar de tener carpetas genéricas como core, utils o main, organizaremos el proyecto por Contextos Delimitados (Bounded Contexts). Al ver la estructura, cualquier desarrollador sabrá que el sistema gestiona trámites, firmas y auditoría, no solo que es un proyecto MVC.
Estructura de Directorios Propuesta

Plaintext


sagec/
├── manage.py
├── config/                     # Configuraciones del proyecto (settings, wsgi, asgi)
│   ├── settings/
│   │   ├── base.py
│   │   ├── security.py         # Configuración de headers, CSP, SSL
│   │   └── production.py
│   └── urls.py
│
├── requerimientos.txt          # Dependencias (Libraries)
│
│
├── identidad/              # CONTEXTO: Gestión de Usuarios y Seguridad
│   ├── models.py           # UsuarioMICI (Solicitante, Firmante, Fiscal)
│   ├── services.py         # Lógica de 2FA, Bloqueo de IPs
│   ├── middleware.py       # El "Escudo": IP Whitelist, Session Timeout
│   └── views.py            # Login, Logout, Perfil
│
├── tramites/               # CONTEXTO: Solicitudes y Certificados (Core Business)
│   ├── models.py           # Solicitud, Certificado, Oficio
│   ├── services/
│   │   ├── generador_pdf.py # Motor WeasyPrint/ReportLab
│   │   └── firma_digital.py # Lógica de hash y sellado
│   ├── forms.py            # Validaciones de formularios (RUC, DV)
│   └── views.py            # Bandeja de entrada, Vistas de detalle
│
├── integracion/            # CONTEXTO: Conexión Externa (Panamá Emprende)
│   ├── client.py           # Cliente HTTP para consumir la API externa
│   └── adapters.py         # Transforma el JSON de la API a modelos internos
│
└── auditoria/              # CONTEXTO: Trazabilidad y Seguridad Forense
    ├── models.py           # LogsInmutables
    └── signals.py          # Escucha cambios en 'tramites' y graba logs


2. Librerías Clave (Stack Tecnológico)
Para cumplir con la "Máxima Seguridad" y el manejo de PDFs, estas son las dependencias esenciales que debes instalar:
Seguridad:
django-axes: Protección contra fuerza bruta en el login.
django-otp & django-two-factor-auth: Para implementar el 2FA obligatorio de Fiscales y Firmantes.
django-csp: Para gestionar Content Security Policy (evitar XSS).
django-encrypted-model-fields: Para cifrar datos sensibles en la BD (ej. tokens de API).
Negocio:
weasyprint: Para generar los PDFs de los certificados y oficios (convierte HTML/CSS a PDF, permitiendo diseños exactos).
requests: Para conectar con la API de Panamá Emprende.
Utilidades:
django-environ: Para manejar variables de entorno (Secret Keys no hardcodeadas).
3. Detalle de Implementación por Módulo
A. Módulo identidad (El Portero Blindado)
Este módulo implementa tu estrategia "Público pero Blindado".
Modelos (models.py):
UsuarioMICI: Hereda de AbstractUser. Campos extra: rol (Solicitante, Firmante, Fiscal), departamento, ip_autorizada (opcional).
Middleware (middleware.py):
IPRestrictionMiddleware: Verifica si el usuario entrante (especialmente Fiscal) viene de una IP gubernamental o VPN conocida. Si no, lanza 403 Forbidden antes de cargar la vista.
SessionTimeoutMiddleware: Fuerza el logout tras 15 minutos de inactividad.
Servicios (services.py):
Lógica para verificar que el correo sea estrictamente .gob.pa.
B. Módulo integracion (El Puente de Datos)
Aquí procesamos la imagen que me enviaste. No guardamos todo, pero consultamos todo.
Adaptador (adapters.py):
Función mapear_datos_aviso(json_response): Recibe el JSON de la API y lo limpia.
Mapeo de campos (según tu imagen):
numero_aviso <- aviso_operacion
ruc_emisor <- ruc + dv
razon_social <- razon_social
ubicacion_completa <- Concatenación de provincia, distrito, corregimiento, calle, casa, edificio, local.
estatus_legal <- estado_sucursal (IMPORTANTE: Si dice "CANCELADO", el sistema debe marcarlo en rojo en la UI).
C. Módulo tramites (El Corazón del SAGEC)
Aquí ocurre la lógica de negocio descrita en la propuesta.
Modelos (models.py):
DocumentoBase: Clase abstracta con uuid, fecha_creacion, hash_seguridad.
Certificado(DocumentoBase): Guarda una instantánea (Snapshot) de los datos de la empresa en el momento de la consulta.
¿Por qué? Si la empresa cambia de dueño mañana, el certificado emitido hoy debe reflejar el dueño de hoy. Usa un JSONField para guardar la respuesta completa de la API como respaldo.
Oficio(DocumentoBase): Campos extra: numero_oficio_externo (referencia del MP), texto_cuerpo (dinámico).
Servicio de PDF (services/generador_pdf.py):
Usa plantillas HTML de Django para diseñar el certificado.
Inyecta los datos.
Renderiza con WeasyPrint a un objeto binario en memoria (no guardar en disco hasta que esté firmado).
Servicio de Firma (services/firma_digital.py):
Función sellar_documento(usuario, documento_id):
Genera el PDF final.
Calcula el SHA-256 del archivo.
Guarda el hash en la BD.
Cambia estado a FIRMADO.
D. Módulo auditoria (La Caja Negra)
Cumple con el requisito de trazabilidad de la propuesta.
Modelos (models.py):
BitacoraEvento:
actor: Usuario que hizo la acción.
accion: (LOGIN, CONSULTA_API, GENERACION_PDF, FIRMA, DESCARGA).
recurso_afectado: ID del certificado.
ip_origen: IP real del cliente.
timestamp: auto_now_add=True.
Signals:
Usar señales de Django (post_save) para que cada vez que se cree un Certificado, automáticamente se cree una entrada en la Bitácora sin que el programador tenga que recordarlo en la vista.
4. Flujo de Desarrollo Sugerido (Sprints)
Semana 1 (Core & Auth):
Configurar config/settings/security.py.
Crear modulos/identidad.
Implementar Login con 2FA y restricción de IPs.
Entregable: Un login aburrido pero impenetreble.
Semana 2 (Integración & Datos):
Crear modulos/integracion.
Conectar con API (o Mock si no la tienes aún).
Crear la vista de "Búsqueda" que muestre los datos de la imagen (RUC, Aviso, etc.).
Entregable: Buscador funcional de empresas.
Semana 3 (Lógica de Trámites & PDF):
Crear modulos/tramites.
Diseñar la plantilla HTML del Oficio y Certificado.
Implementar WeasyPrint.
Crear la "Bandeja de Trámites" (Tu flujo de usuario corregido).
Semana 4 (Firma & Auditoría):
Implementar el botón de "Firmar" (cambio de estado + hash).
Configurar modulos/auditoria y Signals.
Pruebas de penetración internas (intentar descargar un PDF sin permiso).
Resumen de Seguridad en Código
En tus views.py, NUNCA uses Certificado.objects.get(id=pk).
Usa siempre validación de contexto:

Python


# Ejemplo de seguridad en capa de servicio
def descargar_certificado(usuario, uuid_cert):
    # 1. Validar que el certificado existe
    cert = get_object_or_404(Certificado, uuid=uuid_cert)
    
    # 2. Validar propiedad o rol (Scream Architecture)
    if not permiso_servicio.puede_ver_documento(usuario, cert):
        registrar_intento_fallido(usuario, "Intento acceso no autorizado")
        raise PermissionDenied
        
    # 3. Servir
    return generar_respuesta_pdf(cert)


Este plan alinea tu código Django con los requisitos de la propuesta Brain Solutions, garantizando que la estructura del proyecto refleje la seriedad institucional del MICI.
