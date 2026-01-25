Mapa de Rutas - SAGEC (MICI)
Este documento define la estructura de URLs del sistema y las restricciones de acceso por rol: Fiscal, Trabajador y Director.
1. Módulo de Identidad (/auth/)
Gestiona el acceso, registro y perfiles de usuario.
Ruta
URL
Acceso
Propósito
login
/login/
Público
Email (.gob.pa), Password, Captcha y 2FA.
register
/registro/
Público
Formulario de registro con validación de cédula.
logout
/logout/
Autenticado
Cierre de sesión y limpieza de cookies.
perfil
/configuracion/
Todos
Edición de datos y cambio de contraseña.
lista_usuarios
/usuarios/
Director
Gestión de usuarios y log de actividad.

2. Módulo de Integración (/consultas/)
Consultas a la API de Panamá Emprende y vistas de resultados.
Ruta
URL
Acceso
Propósito
buscador
/consultar/
Todos
Panel principal de búsqueda (RUC/Cédula).
api_search
/hx/buscar-empresa/
Todos
HTMX: Devuelve la tarjeta con datos de la empresa.

3. Módulo de Trámites (/tramites/)
El corazón del flujo de aprobación y firma.
Ruta
URL
Acceso
Propósito
bandeja_admin
/solicitudes/
Trabajador, Director
Lista global de trámites entrantes.
mis_certificados
/certificados/
Todos
Lista de certificados pedidos por el usuario actual.
mis_oficios
/oficios/
Todos
Lista de oficios pedidos por el usuario actual.
detalle
/<uuid:id>/
Todos
Ver detalles, estatus y previsualización.
aprobar
/<uuid:id>/aprobar/
Trabajador, Director
Validar trámite y pasarlo a "Aprobado".
firmar
/<uuid:id>/firmar/
Director
Subida de documento firmado y sellado final.
descargar
/<uuid:id>/pdf/
Todos
Descarga del documento final firmado.

