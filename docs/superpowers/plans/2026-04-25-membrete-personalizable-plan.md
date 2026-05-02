# Plan de Implementación — Membrete y Footer Personalizable

**Fecha:** 2026-04-25
**Spec base:** `docs/superpowers/specs/2026-04-25-membrete-personalizable-design.md`

---

## Resumen

Implementación dividida en **9 fases** secuenciales. Cada fase es independiente, deja el sistema funcional y se puede verificar antes de pasar a la siguiente. Durante todas las fases anteriores a la 4, el sistema sigue usando las imágenes estáticas actuales (sin regresión).

---

## Fase 1 — Dependencias y modelo de datos

**Objetivo:** Agregar el modelo `PlantillaDocumento` y el campo `plantilla_snapshot` sin romper nada existente.

### Tareas

1. Agregar `python-docx>=1.1.0` a `requirements.txt`
2. Instalar dependencia: `pip install python-docx`
3. Editar `tramites/models.py`:
   - Importar `MinValueValidator`, `MaxValueValidator`, `Decimal`
   - Agregar clase `PlantillaDocumento` (ver spec §4)
   - Agregar campo `plantilla_snapshot = JSONField(default=dict, blank=True)` a `Tramite`
4. Generar migración: `python manage.py makemigrations tramites`
5. Crear migración manual de datos `tramites/migrations/00XX_poblar_plantilla_snapshot.py` con `RunPython` que pobla snapshot legado en trámites existentes (ver spec §8)
6. Aplicar migraciones: `python manage.py migrate`

### Verificación

- Django shell: `from tramites.models import PlantillaDocumento; PlantillaDocumento.objects.count()` → 0
- Trámites existentes (no BORRADOR) tienen `plantilla_snapshot` poblado
- Trámites en BORRADOR tienen `plantilla_snapshot = {}`
- Servidor de desarrollo arranca sin errores

### Riesgos

- Migración pesada si hay muchos trámites históricos → mitigado: `update()` masivo, no es por fila

---

## Fase 2 — Servicio de extracción del .docx

**Objetivo:** Función pura que recibe un `.docx` y devuelve un dict con header, footer y márgenes. Sin tocar vistas ni modelos aún.

### Tareas

1. Crear `tramites/services/extractor_plantilla.py`
2. Implementar `extraer_plantilla_desde_docx(archivo_docx) -> dict`:
   - Validar extensión y tamaño (raise `ValidationError`)
   - Abrir con `python-docx`
   - Procesar header (imagen o texto-a-PNG)
   - Procesar footer (opcional)
   - Leer márgenes (EMU → cm)
3. Implementar helper privado `_renderizar_texto_a_png(html_text) -> bytes` usando WeasyPrint @ 200 DPI
4. Implementar helper privado `_extraer_imagen_de_seccion(seccion) -> bytes | None`

### Verificación

- Crear `.docx` de prueba manual con header de imagen → dict con bytes válidos
- Crear `.docx` con header de texto → PNG renderizado
- `.docx` sin header → `ValidationError`
- Archivo no `.docx` → `ValidationError`

### Riesgos

- Renderizado de texto pierde fuente exacta del Word → aceptable, fallback a fuentes web seguras

---

## Fase 3 — Tests unitarios del extractor

**Objetivo:** Cobertura completa del extractor antes de integrarlo en vistas.

### Tareas

1. Crear `tests/test_extractor_plantilla.py`
2. Crear fixtures `.docx` en `tests/fixtures/plantillas/`:
   - `con_imagen.docx`
   - `con_texto.docx`
   - `sin_header.docx`
   - `corrupto.docx` (truncado)
3. Implementar tests listados en spec §11

### Verificación

- `python manage.py test tests.test_extractor_plantilla` → todos verdes

---

## Fase 4 — Integración en generación de PDF

**Objetivo:** Hacer que `generar_html_tramite()` use la plantilla activa o el snapshot. Sin UI todavía — la plantilla se crearía manualmente vía Django shell para probar.

### Tareas

1. Editar `tramites/services/generador_pdf.py`:
   - Agregar `_resolver_plantilla(tramite)` (ver spec §6)
   - Modificar `generar_html_tramite()` para inyectar `plantilla` al context
   - Mantener `logo_path` y `footer_path` en el context **temporalmente** por compatibilidad
2. Editar `tramites/templates/tramites/pdf/oficio_oficial.html`:
   - Reemplazar `{{ logo_path }}` por `{{ plantilla.imagen_header_path }}`
   - Reemplazar `{{ footer_path }}` por `{{ plantilla.imagen_footer_path }}`
   - Reemplazar `@page { margin: ... }` fijo por valores dinámicos
3. Mismo cambio en `certificado_oficial.html`
4. Eliminar `logo_path` y `footer_path` del context una vez verificado

### Verificación

- Sin `PlantillaDocumento` activa → PDF se genera con imágenes estáticas (idéntico al actual)
- Crear `PlantillaDocumento` manual desde shell con imágenes de prueba → PDF nuevo usa esas imágenes
- Trámite con `plantilla_snapshot` poblado → ignora cambios en plantilla activa

### Riesgos

- Path absoluto en `imagen_header_path` puede romper en producción si cambia `MEDIA_ROOT` → mitigado: snapshot guarda path absoluto resuelto al momento de generar

---

## Fase 5 — Tests de integración del generador

**Objetivo:** Validar el comportamiento de `_resolver_plantilla` y la inmutabilidad.

### Tareas

1. Crear `tests/test_generador_pdf_con_plantilla.py`
2. Implementar tests listados en spec §11 (cuatro escenarios principales)

### Verificación

- `python manage.py test tests.test_generador_pdf_con_plantilla` → todos verdes

---

## Fase 6 — Vistas y URLs del Director

**Objetivo:** Director puede subir, ver, activar y eliminar plantillas vía UI.

### Tareas

1. Editar `tramites/urls.py` — agregar 6 URLs (ver spec §7)
2. Editar `tramites/views.py` — implementar:
   - `listar_plantillas_view`
   - `subir_plantilla_view` — POST llama a `extraer_plantilla_desde_docx`, crea `PlantillaDocumento` con archivos
   - `detalle_plantilla_view` — GET, marca `preview_visto=True`
   - `preview_plantilla_view` — GET, devuelve PDF inline
   - `activar_plantilla_view` — POST, transacción atómica
   - `eliminar_plantilla_view` — POST, valida `activa=False`
3. Todas las vistas con `@require_rol(UsuarioMICI.DIRECTOR)`
4. Crear formulario `PlantillaDocumentoForm` en `tramites/forms.py` (o sección equivalente)

### Verificación

- Solo Director accede (otros roles → 403)
- Subida exitosa redirige a detalle
- Activación desactiva la anterior

---

## Fase 7 — Templates HTML del Director

**Objetivo:** Pantallas funcionales y estilizadas consistentes con el resto del sistema.

### Tareas

1. Crear `tramites/templates/tramites/plantillas/lista.html`
2. Crear `tramites/templates/tramites/plantillas/subir.html`
3. Crear `tramites/templates/tramites/plantillas/detalle.html`:
   - Iframe con preview
   - Form de márgenes con HTMX para regenerar preview
   - Botón "Activar" deshabilitado hasta `preview_visto=True`
4. Editar `templates/base.html` — agregar entrada de menú "Plantillas de documentos" (visible solo Director)

### Verificación

- Manual: subir `.docx`, ver preview, ajustar márgenes, regenerar, activar
- Manual: nuevo trámite usa la plantilla activa
- Manual: trámite ya generado mantiene su diseño

---

## Fase 8 — Servicio de preview con trámite dummy

**Objetivo:** Generar PDF de muestra usando datos ficticios para preview antes de activar.

### Tareas

1. Agregar a `tramites/services/generador_pdf.py`:
   ```python
   def generar_preview_plantilla(plantilla: PlantillaDocumento) -> bytes:
   ```
2. Construir trámite no persistido con:
   - Empresa ficticia (RUC `999999-99-999999`, nombre "Empresa Demo S.A.")
   - Preguntas de ejemplo
   - Fechas actuales
   - Tipo según `plantilla.tipo_aplicable` (si AMBOS, generar uno de cada)
3. Llamar a `generar_pdf_desde_html()` aplicando el snapshot temporal de la plantilla pasada

### Verificación

- `preview_plantilla_view` devuelve PDF válido visible en iframe
- Preview refleja cambios de márgenes en tiempo real (vía regeneración HTMX)

---

## Fase 9 — Auditoría, validaciones finales y editor TipTap

**Objetivo:** Cerrar el feature con auditoría, validaciones y consistencia en el editor.

### Tareas

1. Editar `auditoria/models.py` — agregar `tipo_evento`:
   - `PLANTILLA_CREADA`
   - `PLANTILLA_ACTIVADA`
   - `PLANTILLA_ELIMINADA`
2. Generar migración para `auditoria`
3. En cada vista de gestión de plantillas, llamar `BitacoraEvento.objects.create()` con datos relevantes
4. Editar `tramites/templates/tramites/editar_pdf.html`:
   - Reemplazar URL hardcoded del logo y footer por una que sirva la imagen de la plantilla aplicable al trámite (snapshot si existe, plantilla activa si no, fallback estático)
   - Crear vista helper `imagen_plantilla_view(tramite_id, tipo)` que devuelve `FileResponse` con la imagen correcta
5. Crear `tests/test_vistas_plantilla.py` con todos los tests listados en spec §11
6. Verificación end-to-end manual:
   - Subir `.docx` real del MICI
   - Activar
   - Crear trámite nuevo → usa nueva plantilla
   - Editar PDF en TipTap → header/footer correctos
   - Trámite anterior → mantiene diseño viejo

### Verificación

- Suite completa: `python manage.py test` → todos verdes
- Bitácora registra eventos al crear/activar/eliminar plantilla
- Editor TipTap muestra header/footer correcto según plantilla del trámite

---

## Checkpoints de aprobación

Sugiero pausar y verificar contigo al terminar:

- **Fin de Fase 1:** Modelo en BD, migraciones aplicadas
- **Fin de Fase 4:** PDFs siguen idénticos sin plantilla activa, plantilla manual desde shell ya funciona
- **Fin de Fase 7:** UI completa funcionando con datos reales
- **Fin de Fase 9:** Feature completo, listo para QA

---

## Estimación grosera

- Fases 1-3: backend puro, ~1 día
- Fases 4-5: integración PDF, ~0.5 día
- Fases 6-8: UI Director, ~1.5 días
- Fase 9: pulido y E2E, ~0.5 día

**Total: ~3.5 días de trabajo enfocado**

---

## Riesgos transversales

| Riesgo | Mitigación |
|---|---|
| `python-docx` no extrae imagen de header complejo | Detectar y mostrar mensaje claro al Director, sugerir simplificar el Word |
| WeasyPrint renderiza texto-a-PNG con fuentes incorrectas | Usar `font-family: Arial, sans-serif` como fallback predecible |
| Trámites en BORRADOR cambian de plantilla si Director activa otra | Diseño intencional — solo trámites generados (no en BORRADOR) tienen snapshot |
| Director sube Word con header demasiado grande | Validar dimensiones del PNG resultante; sugerir reducción |
| Conflicto entre snapshot y plantilla cuando se elimina la plantilla activa | Bloquear eliminación si está activa; al eliminar inactiva, los snapshots ya tienen path absoluto y siguen funcionando |
