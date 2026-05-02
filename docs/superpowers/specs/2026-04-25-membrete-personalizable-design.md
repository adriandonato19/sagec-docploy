# Membrete y Footer Personalizable — Design Spec

**Fecha:** 2026-04-25
**Autor:** Adrian Donato
**Estado:** Aprobado para implementación

---

## 1. Contexto y problema

Actualmente, los PDFs de Certificados y Oficios usan imágenes estáticas y fijas:

- Header: `static/img/logo_oficial.png`
- Footer: `static/img/footer_certificado.png`

Los márgenes de página están hardcodeados en `tramites/templates/tramites/pdf/oficio_oficial.html` y `certificado_oficial.html`. Cualquier cambio de diseño requiere intervención del desarrollador.

**Necesidad del negocio:** El Director del MICI debe poder cambiar el membrete y footer institucional sin asistencia técnica, subiendo un archivo Word (`.docx`) que contenga el diseño deseado. El sistema debe extraer header y footer del Word y aplicarlos automáticamente a los PDFs nuevos. Los trámites ya generados deben mantener su diseño original (inmutabilidad documental).

---

## 2. Alcance

### Incluido
- Subida de plantillas `.docx` por el Director
- Extracción automática de header y footer del Word
- Soporte para headers de imagen y headers de texto formateado
- Configuración de márgenes por plantilla
- Asignación de plantilla a Certificados, Oficios o ambos
- Preview obligatorio antes de activar
- Inmutabilidad de trámites ya generados (snapshot)
- Auditoría de creación, activación y eliminación
- Solo el rol Director gestiona plantillas

### Excluido
- Edición visual del Word desde el sistema
- Múltiples plantillas activas simultáneamente para el mismo tipo
- Versionado/rollback automático
- Conversión de cuerpo del documento Word (solo header/footer)
- Soporte para `.doc` legacy o `.odt`

---

## 3. Decisiones clave

| Decisión | Elegida | Alternativa rechazada |
|---|---|---|
| Origen del diseño | Word (.docx) | Editor visual integrado |
| Forma de almacenar header/footer | Imágenes PNG extraídas | HTML/CSS convertido del Word |
| Inmutabilidad | Snapshot por trámite | Vincular a plantilla viva |
| Activación | Manual con preview previo | Automática al subir |
| Márgenes | Editables, defaults del Word | Fijos del sistema |
| Eliminación | Solo plantillas inactivas | Permitida siempre |

---

## 4. Modelo de datos

### Nuevo modelo: `PlantillaDocumento` (en `tramites/models.py`)

```python
class PlantillaDocumento(models.Model):
    CERTIFICADO = 'CERTIFICADO'
    OFICIO = 'OFICIO'
    AMBOS = 'AMBOS'
    TIPO_CHOICES = [
        (CERTIFICADO, 'Solo Certificados'),
        (OFICIO, 'Solo Oficios'),
        (AMBOS, 'Certificados y Oficios'),
    ]

    nombre = models.CharField(max_length=120)
    tipo_aplicable = models.CharField(max_length=20, choices=TIPO_CHOICES)

    archivo_word = models.FileField(upload_to='plantillas/word/')
    imagen_header = models.ImageField(upload_to='plantillas/headers/')
    imagen_footer = models.ImageField(upload_to='plantillas/footers/', blank=True, null=True)

    margen_superior_cm = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('2.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))]
    )
    margen_inferior_cm = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('2.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))]
    )
    margen_izquierdo_cm = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('2.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))]
    )
    margen_derecho_cm = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('2.5'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))]
    )

    activa = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        'identidad.UsuarioMICI', on_delete=models.PROTECT, related_name='plantillas_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_activacion = models.DateTimeField(null=True, blank=True)
    preview_visto = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha_creacion']
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_aplicable'],
                condition=models.Q(activa=True),
                name='una_plantilla_activa_por_tipo'
            ),
        ]
```

### Cambio en `Tramite` (en `tramites/models.py`)

```python
plantilla_snapshot = models.JSONField(default=dict, blank=True)
# Estructura:
# {
#   'imagen_header_path': str,
#   'imagen_footer_path': str | '',
#   'margen_superior_cm': float,
#   'margen_inferior_cm': float,
#   'margen_izquierdo_cm': float,
#   'margen_derecho_cm': float,
# }
```

---

## 5. Flujo de extracción del .docx

### Servicio nuevo: `tramites/services/extractor_plantilla.py`

```python
def extraer_plantilla_desde_docx(archivo_docx) -> dict:
    """
    Extrae header, footer y márgenes de un archivo .docx.

    Returns:
        {
            'imagen_header_bytes': bytes,           # PNG
            'imagen_footer_bytes': bytes | None,    # PNG, opcional
            'margen_superior_cm': float,
            'margen_inferior_cm': float,
            'margen_izquierdo_cm': float,
            'margen_derecho_cm': float,
        }

    Raises:
        ValidationError si el .docx es inválido o no tiene header.
    """
```

### Algoritmo

1. **Abrir documento** con `python-docx`: `Document(archivo_docx)`
2. **Acceder primera sección**: `section = document.sections[0]`
3. **Procesar header** (`section.header`):
   - Buscar imágenes inline (`InlineShape`) en runs del header
   - Si hay imagen → extraer blob (`part.image.blob`) y guardar como PNG
   - Si solo hay texto → construir HTML simple (mantener fuente, alineación, color básico) y renderizar a PNG con WeasyPrint @ 200 DPI
   - Si está vacío → `raise ValidationError("Header obligatorio")`
4. **Procesar footer** (`section.footer`): mismo flujo, pero opcional (devuelve `None` si vacío)
5. **Leer márgenes**: convertir EMU a cm
   ```python
   margen_superior_cm = section.top_margin / 360000  # EMU a cm
   ```
6. **Retornar dict**

### Validaciones del archivo

| Validación | Acción si falla |
|---|---|
| Extensión `.docx` | Rechazar con mensaje |
| Tamaño ≤ 5 MB | Rechazar con mensaje |
| Documento abre sin error | Mostrar "Archivo Word corrupto" |
| Tiene al menos una sección | Mostrar "Documento sin secciones válidas" |
| Header no vacío | Mostrar "Configura un encabezado en el Word" |

---

## 6. Integración en generación de PDF

### Cambio en `generar_html_tramite()` (`tramites/services/generador_pdf.py`)

Agregar función `_resolver_plantilla(tramite)`:

```python
def _resolver_plantilla(tramite):
    # 1. Snapshot existente → usarlo (inmutabilidad)
    if tramite.plantilla_snapshot:
        return tramite.plantilla_snapshot

    # 2. Plantilla activa para el tipo
    from tramites.models import PlantillaDocumento
    tipo = tramite.tipo_documento  # 'CERTIFICADO' u 'OFICIO'
    plantilla = PlantillaDocumento.objects.filter(
        activa=True,
        tipo_aplicable__in=[tipo, 'AMBOS']
    ).first()

    if plantilla and plantilla.imagen_header and Path(plantilla.imagen_header.path).exists():
        snapshot = {
            'imagen_header_path': str(plantilla.imagen_header.path),
            'imagen_footer_path': str(plantilla.imagen_footer.path) if plantilla.imagen_footer else '',
            'margen_superior_cm': float(plantilla.margen_superior_cm),
            'margen_inferior_cm': float(plantilla.margen_inferior_cm),
            'margen_izquierdo_cm': float(plantilla.margen_izquierdo_cm),
            'margen_derecho_cm': float(plantilla.margen_derecho_cm),
        }
        tramite.plantilla_snapshot = snapshot
        tramite.save(update_fields=['plantilla_snapshot'])
        return snapshot

    # 3. Fallback estático
    return {
        'imagen_header_path': str(settings.BASE_DIR / 'static' / 'img' / 'logo_oficial.png'),
        'imagen_footer_path': str(settings.BASE_DIR / 'static' / 'img' / 'footer_certificado.png'),
        'margen_superior_cm': 2.5,
        'margen_inferior_cm': 2.5,
        'margen_izquierdo_cm': 2.5,
        'margen_derecho_cm': 2.5,
    }
```

Inyectar al `context`:
```python
context['plantilla'] = _resolver_plantilla(tramite)
```

### Cambios en plantillas HTML

`tramites/templates/tramites/pdf/oficio_oficial.html` y `certificado_oficial.html`:

- Reemplazar `{{ logo_path }}` por `{{ plantilla.imagen_header_path }}`
- Reemplazar `{{ footer_path }}` por `{{ plantilla.imagen_footer_path }}`
- Reemplazar `@page { margin: ... }` fijo por:
  ```css
  @page {
    margin-top: {{ plantilla.margen_superior_cm }}cm;
    margin-bottom: {{ plantilla.margen_inferior_cm }}cm;
    margin-left: {{ plantilla.margen_izquierdo_cm }}cm;
    margin-right: {{ plantilla.margen_derecho_cm }}cm;
  }
  ```

### Cambio en `editar_pdf.html`

El editor TipTap muestra header/footer "no editables". Cambiar:
- `{% static 'img/logo_oficial.png' %}` → URL servida desde la plantilla activa o snapshot del trámite
- Lo mismo para el footer

Crear vista helper que devuelva la URL de la imagen header/footer aplicable al trámite.

---

## 7. Interfaz de gestión (Director)

### URLs nuevas (`tramites/urls.py`)

```python
path('configuracion/plantillas/', views.listar_plantillas_view, name='listar_plantillas'),
path('configuracion/plantillas/nueva/', views.subir_plantilla_view, name='subir_plantilla'),
path('configuracion/plantillas/<int:id>/', views.detalle_plantilla_view, name='detalle_plantilla'),
path('configuracion/plantillas/<int:id>/preview/', views.preview_plantilla_view, name='preview_plantilla'),
path('configuracion/plantillas/<int:id>/activar/', views.activar_plantilla_view, name='activar_plantilla'),
path('configuracion/plantillas/<int:id>/eliminar/', views.eliminar_plantilla_view, name='eliminar_plantilla'),
```

Todas las vistas decoradas con `@require_rol(UsuarioMICI.DIRECTOR)`.

### Pantallas

**1. Listado** (`tramites/templates/tramites/plantillas/lista.html`):
- Tabla: nombre, tipo aplicable, estado, fecha de creación, creador, acciones
- Botón "Subir nueva plantilla"
- Acciones por fila: Ver detalle/preview, Activar, Eliminar

**2. Subir plantilla** (`tramites/templates/tramites/plantillas/subir.html`):
- Form: `nombre` (CharField), `tipo_aplicable` (radio), `archivo_word` (FileField)
- Submit ejecuta extracción del .docx
- Si extracción falla → mostrar error en el form
- Si éxito → redirigir a detalle/preview

**3. Detalle + preview** (`tramites/templates/tramites/plantillas/detalle.html`):
- Iframe con el PDF preview generado con datos dummy
- Inputs editables: 4 márgenes (precargados desde el .docx)
- Botón "Regenerar preview" (HTMX, regenera el iframe)
- Botón "Activar plantilla" (deshabilitado hasta `preview_visto=True`)
- Botón "Volver al listado"
- Al cargar la página por primera vez se setea `preview_visto=True`

**4. Activación** — modal de confirmación:
- "Esto reemplazará la plantilla activa actual para [tipo]. Los trámites nuevos usarán esta plantilla. ¿Continuar?"
- Acción ejecuta dentro de `transaction.atomic()`:
  - Desactiva la plantilla activa anterior del mismo tipo
  - Activa la nueva
  - Setea `fecha_activacion = now()`

**5. Eliminación**:
- Solo permitido si `activa=False`
- Borra archivos físicos (Word, header PNG, footer PNG)

### Servicio de preview

```python
def generar_preview_plantilla(plantilla: PlantillaDocumento) -> bytes:
    """
    Crea un Tramite no persistido con datos dummy y genera el PDF
    aplicando la plantilla pasada como argumento.
    """
```

El trámite dummy incluye datos realistas: empresa ficticia, RUC genérico, preguntas de ejemplo, fechas actuales.

### Navegación

Agregar entrada "Plantillas de documentos" en el menú lateral de `templates/base.html`, visible solo para `usuario.rol == 'DIRECTOR'`.

---

## 8. Migración de datos

### Migración nueva: `tramites/migrations/00XX_plantilla_documento.py`

- Crear tabla `PlantillaDocumento`
- Agregar campo `plantilla_snapshot` a `Tramite`

### Migración de datos: `tramites/migrations/00XX_poblar_plantilla_snapshot.py`

```python
def poblar_snapshots_legados(apps, schema_editor):
    Tramite = apps.get_model('tramites', 'Tramite')
    snapshot_legado = {
        'imagen_header_path': 'static/img/logo_oficial.png',
        'imagen_footer_path': 'static/img/footer_certificado.png',
        'margen_superior_cm': 2.5,
        'margen_inferior_cm': 2.5,
        'margen_izquierdo_cm': 2.5,
        'margen_derecho_cm': 2.5,
    }
    Tramite.objects.filter(plantilla_snapshot={}).exclude(estado='BORRADOR').update(
        plantilla_snapshot=snapshot_legado
    )
```

Trámites en BORRADOR no reciben snapshot — al generarles PDF tomarán la plantilla activa del momento (o fallback estático).

---

## 9. Auditoría

Agregar a `auditoria/models.BitacoraEvento.tipo_evento`:

- `PLANTILLA_CREADA`
- `PLANTILLA_ACTIVADA`
- `PLANTILLA_ELIMINADA`

Cada vista de gestión llama explícitamente a `BitacoraEvento.objects.create()` con: usuario, tipo de evento, descripción (incluye nombre de plantilla y tipo aplicable), timestamp.

---

## 10. Casos borde

| Caso | Comportamiento |
|---|---|
| Sin plantilla activa | Fallback a imágenes estáticas actuales |
| Plantilla activa con archivo borrado del disco | Log warning, fallback a estáticas |
| Header del Word es texto formateado | Renderizar a PNG con WeasyPrint @ 200 DPI |
| Header del Word vacío | Rechazar al subir |
| Footer del Word vacío | Aceptar, footer queda en blanco |
| Concurrencia al activar | `transaction.atomic()` y constraint único |
| Director borra plantilla activa | Bloquear con mensaje "Desactivar primero" |
| Trámite con snapshot pero archivo borrado del disco | Log warning y usar fallback estático |

---

## 11. Testing

### Tests unitarios

**`tests/test_extractor_plantilla.py`**
- Extrae imagen de header desde .docx con imagen
- Extrae header de texto y lo renderiza a PNG válido
- Rechaza .docx sin header
- Rechaza archivos no-.docx
- Rechaza archivos > 5 MB
- Lee márgenes del Word correctamente (conversión EMU → cm)
- Footer opcional: devuelve None si está vacío

**`tests/test_plantilla_documento.py`**
- Constraint: solo una plantilla activa por tipo
- `AMBOS` activa para ambos tipos en consultas
- Activación desactiva la anterior del mismo tipo (transacción)
- Validación de rangos de márgenes (0.5 - 5.0)

**`tests/test_generador_pdf_con_plantilla.py`**
- PDF nuevo usa plantilla activa
- Trámite con `plantilla_snapshot` ignora cambios en plantilla activa
- Sin plantilla activa → usa imágenes estáticas
- Snapshot se congela en primera generación
- Snapshot persiste tras múltiples generaciones

**`tests/test_vistas_plantilla.py`**
- Solo Director accede a las URLs de gestión (otros roles → 403)
- Botón "Activar" requiere `preview_visto=True`
- Eliminación bloqueada si plantilla activa
- Auditoría registra eventos correctamente

---

## 12. Orden de implementación

1. Modelo `PlantillaDocumento` + migración de schema
2. Campo `plantilla_snapshot` en `Tramite` + migración de datos legados
3. Servicio `extractor_plantilla.py` + tests
4. Refactor `generar_html_tramite()` y plantillas HTML para usar plantilla dinámica
5. Vistas + templates de gestión (Director)
6. Servicio de preview con trámite dummy
7. Auditoría + validaciones de formulario
8. Actualizar `editar_pdf.html` para reflejar plantilla activa
9. Tests de integración end-to-end
10. Verificación manual con `.docx` de muestra del MICI

---

## 13. Dependencias nuevas

Agregar a `requirements.txt`:

```
python-docx>=1.1.0
Pillow>=10.0.0   # ya debería estar por WeasyPrint, verificar
```

---

## 14. Archivos afectados

### Nuevos
- `tramites/services/extractor_plantilla.py`
- `tramites/templates/tramites/plantillas/lista.html`
- `tramites/templates/tramites/plantillas/subir.html`
- `tramites/templates/tramites/plantillas/detalle.html`
- `tramites/migrations/00XX_plantilla_documento.py`
- `tramites/migrations/00XX_poblar_plantilla_snapshot.py`
- `tests/test_extractor_plantilla.py`
- `tests/test_plantilla_documento.py`
- `tests/test_generador_pdf_con_plantilla.py`
- `tests/test_vistas_plantilla.py`

### Modificados
- `tramites/models.py` — modelo `PlantillaDocumento`, campo `plantilla_snapshot`
- `tramites/views.py` — vistas de gestión + helper de URL de plantilla
- `tramites/urls.py` — 6 URLs nuevas
- `tramites/services/generador_pdf.py` — `_resolver_plantilla()` + integración
- `tramites/templates/tramites/pdf/oficio_oficial.html` — variables dinámicas
- `tramites/templates/tramites/pdf/certificado_oficial.html` — variables dinámicas
- `tramites/templates/tramites/editar_pdf.html` — header/footer dinámicos
- `templates/base.html` — entrada de menú "Plantillas de documentos"
- `auditoria/models.py` — nuevos `tipo_evento`
- `requirements.txt` — `python-docx`
