# SAGEC — Análisis de Escalabilidad y Recomendaciones

## Contexto Operacional

| Parámetro | Valor |
|-----------|-------|
| Trámites por día | ~50 |
| Usuarios internos (Trabajadores/Directores) | ~6 |
| Usuarios diarios totales (Fiscales + internos) | ~100 |
| PDFs generados por hora (estimado) | ~6 (hora pico) |
| PDFs simultáneos máximos esperados | 1–2 |
| Usuarios simultáneos en hora pico | 15–25 |

---

## Infraestructura Recomendada

**Un solo servidor interno** es suficiente para los próximos 10+ años a este volumen.

```
Servidor SAGEC (físico o VM)
├── CPU:  4 núcleos
├── RAM:  8 GB (16 GB recomendado)
├── SO:   Ubuntu 24.04 LTS o RHEL 9
├── Disco 1 (SO + App): 100 GB SSD
└── Disco 2 (Media + BD): 500 GB SSD
      └── /srv/sagec/media/pdfs/  ← capacidad para ~30 años de PDFs

Stack:
  Nginx :443  →  Gunicorn (4–6 workers)  →  Django
                                               ↓
                                        PostgreSQL 16
```

**Almacenamiento de PDFs estimado:**

| Años de operación | Trámites acumulados | Espacio PDFs (~300KB c/u) |
|:-----------------:|:-------------------:|:-------------------------:|
| 1 año | ~18,000 | ~5 GB |
| 5 años | ~90,000 | ~27 GB |
| 10 años | ~180,000 | ~54 GB |
| 20 años | ~365,000 | ~110 GB |

Un disco de 500 GB cubre décadas de operación holgadamente.

---

## Correcciones Prioritarias

### Prioridad 1 — Corregir antes de producción (afectan a todos los usuarios)

#### A. Reemplazar los 6 COUNT queries separados por uno solo
**Archivo:** `tramites/views.py` — `bandeja_admin_view`

Actualmente ejecuta 6 queries `COUNT(*)` independientes cada vez que se carga la bandeja.
Reemplazar con una sola agregación:

```python
from django.db.models import Count, Case, When, IntegerField

contadores = Tramite.objects.aggregate(
    TODOS=Count('id'),
    BORRADOR=Count(Case(When(estado='BORRADOR', then=1), output_field=IntegerField())),
    PENDIENTE=Count(Case(When(estado='PENDIENTE', then=1), output_field=IntegerField())),
    APROBADO=Count(Case(When(estado='APROBADO', then=1), output_field=IntegerField())),
    FIRMADO=Count(Case(When(estado='FIRMADO', then=1), output_field=IntegerField())),
    RECHAZADO=Count(Case(When(estado='RECHAZADO', then=1), output_field=IntegerField())),
)
```

#### B. Agregar `select_related` en vistas de lista
**Archivo:** `tramites/views.py` — `bandeja_admin_view`

Sin esto, listar 10 trámites genera 30+ queries (problema N+1):

```python
queryset = Tramite.objects.select_related('solicitante', 'revisor', 'firmante')
```

#### C. Agregar paginación en mis_certificados y mis_oficios
**Archivo:** `tramites/views.py` — `mis_certificados_view`, `mis_oficios_view`

Actualmente cargan TODOS los trámites del usuario en memoria sin límite.
Con 100 fiscales activos durante años, puede haber miles de registros por usuario.

#### D. Corregir race condition en numero_referencia
**Archivo:** `tramites/views.py` — `crear_tramite_view` (línea ~142)

```python
# Actual — rompe si 2 usuarios crean trámite al mismo tiempo:
numero_referencia=f"...-{Tramite.objects.count() + 1}"
```

Usar el ID del objeto después de `save()` o una secuencia de PostgreSQL.

---

### Prioridad 2 — Importantes para estabilidad en producción

#### E. Mover PDFs de `temp_pdfs/` a MEDIA_ROOT con estructura de fecha
**Archivo:** `tramites/models.py`

Los PDFs actualmente se guardan en `tramites/temp_pdfs/` (hardcodeado en views.py),
fuera del `MEDIA_ROOT` oficial. Si el código cambia de ubicación, los PDFs se pierden.

```python
# Cambiar en el modelo Tramite:
archivo_pdf = models.FileField(
    upload_to='pdfs/%Y/%m/',          # → media/pdfs/2026/02/archivo.pdf
)
archivo_pdf_firmado = models.FileField(
    upload_to='pdfs/firmados/%Y/%m/', # → media/pdfs/firmados/2026/02/archivo.pdf
)
```

Esto también evita directorios planos con miles de archivos que degradan el filesystem.

#### F. Configurar Nginx para servir PDFs directamente
**Archivo:** configuración Nginx del servidor

Un PDF de 300KB pasando por Django ocupa un worker por 0.5–2 segundos.
Nginx lo sirve en microsegundos sin tocar Django:

```nginx
location /media/ {
    alias /srv/sagec/media/;
    add_header X-Content-Type-Options nosniff;
}
```

#### G. Verificar timeout en llamadas a la API de Panamá Emprende
**Archivo:** `integracion/api_client.py`

Con ~100 fiscales consultando empresas durante el día, si la API externa tarda
o falla sin timeout configurado, los workers de Django quedan bloqueados
indefinitamente afectando a todos los usuarios.

Verificar que todas las llamadas `requests.get()` / `requests.post()` tengan:
```python
response = requests.get(url, timeout=10)  # segundos
```

---

### Prioridad 3 — No necesario a este volumen (revisar si escalan 10×)

| Tecnología | Cuándo considerarla |
|------------|-------------------|
| Celery + Redis (tareas asíncronas) | Si superan los 500 PDFs/día |
| Caché Redis | Si superan los 500 usuarios simultáneos |
| MinIO (object storage interno) | Si superan los 500,000 PDFs o necesitan replicación |
| Múltiples servidores / load balancer | Si superan los 300 usuarios concurrentes |
| ASGI / Django async | Si implementan WebSockets o notificaciones en tiempo real |

---

## Capacidad Estimada Actual vs. Con Correcciones

| Escenario | Sin corregir | Con correcciones P1+P2 |
|-----------|:-----------:|:----------------------:|
| Usuarios navegando simultáneamente | 15–30 | 80–150 |
| PDFs simultáneos (generación) | 2–3 | 3–5 (sin Celery) |
| PDFs/hora sostenidos | ~30 | ~50–80 |
| Riesgo de pérdida de PDFs | **Alto** (temp_pdfs/) | Bajo |
| Queries por carga de bandeja | 6+ | 1 |
| N+1 en lista de trámites | Sí (30+ queries) | No |

---

## Riesgos Actuales más Críticos

1. **Pérdida de PDFs** — están en `tramites/temp_pdfs/` fuera del MEDIA_ROOT oficial.
   Un deploy, refactor o cambio de servidor puede dejarlos inaccesibles.

2. **Workers bloqueados por API externa** — si `api_client.py` no tiene `timeout`,
   una falla de la API de Panamá Emprende puede colgar todos los workers de Django.

3. **Race condition en numero_referencia** — dos fiscales creando trámite simultáneamente
   pueden generar el mismo número de referencia.

---

*Documento generado: 2026-02-28*
*Basado en: ~50 trámites/día, ~6 usuarios internos, ~100 usuarios diarios totales*
