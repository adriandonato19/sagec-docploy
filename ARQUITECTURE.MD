Aquí tienes el archivo ARCHITECTURE.md definitivo. He integrado la sección de HTMX explicando su rol como gestor de estado en el cliente (similar a React) pero manteniendo la seguridad y simplicidad de Django.

Arquitectura del Sistema SAGEC (MICI)
Este documento detalla la estructura técnica del Sistema Automatizado de Generación de Certificados (SAGEC), optimizada para la seguridad gubernamental y una experiencia de usuario fluida.

1. Filosofía: Scream Architecture
La estructura del proyecto "grita" las funciones del negocio del MICI, organizando el código en contextos delimitados en lugar de capas técnicas genéricas.

Estructura de Módulos (/modulos)
identidad/: Gestión de usuarios y seguridad.

Roles: Fiscal (Externo), Trabajador (Operativo) y Director (Autoridad/Firmante).

integracion/: Adaptadores para la API de Panamá Emprende.

Procesa datos de RUC, Razón Social, Estatus y Ubicación.

tramites/: Núcleo del negocio. Gestiona el ciclo de vida de Certificados y Oficios.

auditoria/: Registro inmutable de acciones para cumplimiento legal y trazabilidad.

2. Interfaz de Usuario e Interactividad (HTMX)
Para ofrecer una experiencia moderna sin la complejidad y los riesgos de seguridad de un framework de JavaScript pesado (como React), se utiliza HTMX.

Estado del Lado del Servidor: A diferencia de React (useState), el estado real reside en el servidor Django. HTMX permite actualizar "pedazos" de la pantalla (ej. resultados de búsqueda) sin recargar la página.

Buscador Reactivo: Al ingresar un RUC, HTMX dispara una petición al módulo de integracion. El servidor devuelve el HTML de la tarjeta de información (con alertas de estatus como "CANCELADO" en rojo) y lo inyecta directamente.

Seguridad en la Interfaz: Todas las peticiones de HTMX están protegidas por el middleware de Django (CSRF tokens) y validadas por el rol del usuario en el backend antes de devolver cualquier fragmento de HTML.

3. Ciclo de Vida del Trámite (Estados)
El sistema implementa una máquina de estados estricta para garantizar la integridad documental:

BORRADOR: Captura inicial de datos de la API.

PENDIENTE: Solicitud enviada para revisión en el MICI.

APROBADO: Validada por un Trabajador; habilitada para firma.

FIRMADO: PDF final generado, bloqueado e inmutable.

RECHAZADO: Finalizado por inconsistencia de datos.

4. Estrategia de Seguridad: "Público pero Blindado"
Mecanismos para permitir acceso externo a Fiscales protegiendo la red institucional:

Autenticación Fuerte: Doble Factor (2FA) obligatorio para procesos de firma (Director).

Control de Acceso: Middleware de restricción por IP para redes gubernamentales conocidas.

Blindaje de Red: Uso forzado de HTTPS con encabezados HSTS y políticas de seguridad de contenido (CSP).

5. Generación de Documentos
Motor: WeasyPrint para renderizar plantillas HTML oficiales con los datos mapeados de la API.

Trazabilidad: Generación de hash SHA-256 por cada documento firmado para auditoría forense.

6. Pila Tecnológica
Backend: Django 5.0 (Puro).

Frontend: Django Templates + Tailwind CSS + HTMX.

Base de Datos: PostgreSQL (Producción) con Snapshots en JSONField.

Integración: Requests / Client API Panamá Emprende.