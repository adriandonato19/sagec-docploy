# SAGEC - Sistema Automatizado de Generación de Certificados

Government document generation and digital signature system for Panama's Ministry of Commerce and Industries (MICI).

## Tech Stack

- **Backend:** Django 5.0, Python 3.14+
- **Database:** PostgreSQL (production), SQLite (development)
- **Frontend:** Django templates + HTMX + django-widget-tweaks
- **PDF:** WeasyPrint (generation), pyhanko (digital signatures)
- **Security:** django-axes, django-csp, django-otp, django-two-factor-auth, django-encrypted-model-fields
- **Locale:** Spanish (Panama), timezone America/Panama

## Project Structure

```
config/              # Django settings (base, security, development), urls, wsgi/asgi
identidad/           # User identity & access control (UsuarioMICI extends AbstractUser)
integracion/         # External Panama API integration (adapters, services, mock data)
tramites/            # Core document workflow (Tramite state machine, PDF generation)
auditoria/           # Immutable audit logging (BitacoraEvento, signals)
templates/           # Global templates (base.html, components/)
static/              # Static assets (images)
```

## Key Commands

```bash
python manage.py runserver          # Start dev server
python manage.py makemigrations     # Create migrations
python manage.py migrate            # Apply migrations
python manage.py createsuperuser    # Create admin user
```

## Architecture Patterns


- **Scream Architecture:** Directories mirror business domains, not technical layers
- **Settings split:** `config/settings/base.py` (core), `security.py` (production), `development.py` (dev overrides)
- **Custom user model:** `identidad.UsuarioMICI` with roles: FISCAL, TRABAJADOR, DIRECTOR
- **State machine:** Tramite flows BORRADOR → PENDIENTE → APROBADO → FIRMADO (or RECHAZADO)
- **Data snapshots:** `empresa_snapshot` JSONField freezes API data at request time for document immutability
- **Service layer:** `tramites/services/generador_pdf.py`, `integracion/adapters.py`, `integracion/services.py`
- **Role-based access:** `@require_rol()` decorator in `identidad/decorators.py`
- **Audit trail:** Automatic logging via Django signals + explicit logging in views
- **HTMX-driven UI:** Server-side rendering with partial HTML fragment updates, no JS framework

## URL Structure

```
/login/, /logout/                   # Auth
/configuracion/                     # User profile + forced password change
/usuarios/                          # User management (Director only)
/consultar/                         # Main search interface
/hx/buscar-empresa/                 # HTMX reactive search endpoint
/tramites/solicitudes/              # Admin inbox
/tramites/certificados/             # User's certificates
/tramites/oficios/                  # User's official documents
/tramites/<uuid>/                   # Detail view
/tramites/<uuid>/aprobar|firmar|pdf # Actions
```

## Development Notes

- Environment variables via `.env` file and django-environ
- Session timeout: 15 minutes
- AXES: 5 failed login attempts = 1 hour lockout (disabled in dev)
- All UI text in Spanish
- El usuario `DIRECTOR` se crea solo con `python manage.py crear_director`
