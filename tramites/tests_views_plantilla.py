"""Tests E2E de las views de gestión de PlantillaDocumento (Director)."""
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.context import BaseContext
from django.test import TestCase, override_settings


# Workaround Django 5.0 + Python 3.14: BaseContext.__copy__ llama a
# super().__copy__() que ya no existe en object → AttributeError al
# instrumentar el render de plantillas en tests. Reemplazamos por una
# implementación equivalente que clona dicts manualmente.
def _basecontext_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _basecontext_copy
from django.urls import reverse
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image

from auditoria.models import BitacoraEvento
from identidad.models import UsuarioMICI
from tramites.models import PlantillaDocumento


def _png_bytes(color=(20, 80, 160), size=(300, 60)):
    img = Image.new('RGB', size, color=color)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _docx_uploaded(nombre='test.docx'):
    """Genera un .docx mínimo válido con header textual y devuelve un SimpleUploadedFile."""
    doc = Document()
    header_p = doc.sections[0].header.paragraphs[0]
    header_p.text = 'MINISTERIO DE COMERCIO E INDUSTRIAS'
    header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in header_p.runs:
        run.bold = True
    buf = BytesIO()
    doc.save(buf)
    return SimpleUploadedFile(
        nombre,
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )


@override_settings(ALLOWED_HOSTS=['*'])
class PlantillaViewsAccessControlTests(TestCase):
    def setUp(self):
        self.director = UsuarioMICI.objects.create_user(
            username='director-pl', email='dir-pl@mici.gob.pa',
            cedula='8-100-0001', institucion='MICI',
            rol=UsuarioMICI.DIRECTOR, password='ClaveSegura!2026', is_active=True,
        )
        self.fiscal = UsuarioMICI.objects.create_user(
            username='fiscal-pl', email='fis-pl@mici.gob.pa',
            cedula='8-100-0002', institucion='MICI',
            rol=UsuarioMICI.FISCAL, password='ClaveSegura!2026', is_active=True,
        )

    def test_anonimo_es_redirigido_a_login(self):
        response = self.client.get(reverse('tramites:listar_plantillas'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_fiscal_no_puede_listar_plantillas(self):
        self.client.force_login(self.fiscal)
        response = self.client.get(reverse('tramites:listar_plantillas'))
        # @require_rol redirige a una página de no-autorizado o devuelve 403
        self.assertNotEqual(response.status_code, 200)

    def test_director_puede_listar_plantillas(self):
        self.client.force_login(self.director)
        response = self.client.get(reverse('tramites:listar_plantillas'))
        self.assertEqual(response.status_code, 200)


@override_settings(ALLOWED_HOSTS=['*'])
class PlantillaCRUDIntegrationTests(TestCase):
    def setUp(self):
        self.director = UsuarioMICI.objects.create_user(
            username='dir-crud', email='dir.crud@mici.gob.pa',
            cedula='8-200-0001', institucion='MICI',
            rol=UsuarioMICI.DIRECTOR, password='ClaveSegura!2026', is_active=True,
        )
        self.client.force_login(self.director)

    def crear_plantilla_directa(self, **overrides):
        plantilla = PlantillaDocumento(
            nombre=overrides.pop('nombre', 'Plantilla X'),
            tipo_aplicable=overrides.pop('tipo_aplicable', PlantillaDocumento.CERTIFICADO),
            creado_por=self.director,
            activa_certificado=overrides.pop('activa_certificado', False),
            activa_oficio=overrides.pop('activa_oficio', False),
            preview_visto=overrides.pop('preview_visto', False),
            margen_superior_cm=2.0, margen_inferior_cm=2.0,
            margen_izquierdo_cm=3.0, margen_derecho_cm=2.0,
        )
        plantilla.archivo_word.save('x.docx', ContentFile(b'fake'), save=False)
        plantilla.imagen_header.save('h.png', ContentFile(_png_bytes()), save=False)
        plantilla.save()
        return plantilla

    def test_subir_plantilla_crea_registro_y_evento_bitacora(self):
        response = self.client.post(
            reverse('tramites:subir_plantilla'),
            data={
                'nombre': 'Plantilla nueva 2026',
                'tipo_aplicable': PlantillaDocumento.CERTIFICADO,
                'archivo_word': _docx_uploaded(),
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        plantilla = PlantillaDocumento.objects.get(nombre='Plantilla nueva 2026')
        self.assertFalse(plantilla.activa)
        self.assertFalse(plantilla.preview_visto)
        self.assertTrue(plantilla.imagen_header.name)

        evento = BitacoraEvento.objects.filter(tipo_evento=BitacoraEvento.PLANTILLA_CREADA).first()
        self.assertIsNotNone(evento)
        self.assertEqual(evento.actor, self.director)
        self.assertEqual(evento.object_id, plantilla.pk)

    def test_detalle_get_marca_preview_visto(self):
        plantilla = self.crear_plantilla_directa()
        self.assertFalse(plantilla.preview_visto)

        response = self.client.get(
            reverse('tramites:detalle_plantilla', args=[plantilla.id])
        )
        self.assertEqual(response.status_code, 200)
        plantilla.refresh_from_db()
        self.assertTrue(plantilla.preview_visto)

    def test_toggle_activar_sin_preview_visto_falla(self):
        plantilla = self.crear_plantilla_directa(preview_visto=False)
        response = self.client.post(
            reverse('tramites:toggle_activacion_plantilla', args=[plantilla.id, 'CERTIFICADO']),
            data={'accion': 'activar'},
        )
        self.assertEqual(response.status_code, 302)
        plantilla.refresh_from_db()
        self.assertFalse(plantilla.activa_certificado)
        self.assertFalse(
            BitacoraEvento.objects.filter(tipo_evento=BitacoraEvento.PLANTILLA_ACTIVADA).exists()
        )

    def test_toggle_activar_cert_desactiva_anterior_y_registra_bitacora(self):
        anterior = self.crear_plantilla_directa(
            nombre='Anterior', preview_visto=True, activa_certificado=True,
        )
        nueva = self.crear_plantilla_directa(
            nombre='Nueva', preview_visto=True,
        )

        response = self.client.post(
            reverse('tramites:toggle_activacion_plantilla', args=[nueva.id, 'CERTIFICADO']),
            data={'accion': 'activar'},
        )
        self.assertEqual(response.status_code, 302)

        anterior.refresh_from_db()
        nueva.refresh_from_db()
        self.assertFalse(anterior.activa_certificado)
        self.assertTrue(nueva.activa_certificado)
        self.assertIsNotNone(nueva.fecha_activacion)

        evento = BitacoraEvento.objects.get(tipo_evento=BitacoraEvento.PLANTILLA_ACTIVADA)
        self.assertEqual(evento.object_id, nueva.pk)
        self.assertIn(anterior.pk, evento.metadata.get('desactivadas_ids', []))

    def test_toggle_activar_oficio_no_afecta_certificado(self):
        cert_activa = self.crear_plantilla_directa(
            nombre='Cert Activa', preview_visto=True, activa_certificado=True,
        )
        nueva_oficio = self.crear_plantilla_directa(
            nombre='Nueva Oficio', preview_visto=True,
        )

        response = self.client.post(
            reverse('tramites:toggle_activacion_plantilla', args=[nueva_oficio.id, 'OFICIO']),
            data={'accion': 'activar'},
        )
        self.assertEqual(response.status_code, 302)

        cert_activa.refresh_from_db()
        nueva_oficio.refresh_from_db()
        self.assertTrue(cert_activa.activa_certificado)  # no fue tocada
        self.assertTrue(nueva_oficio.activa_oficio)

    def test_toggle_desactivar_deja_flag_en_false(self):
        plantilla = self.crear_plantilla_directa(
            nombre='Activa Cert', preview_visto=True, activa_certificado=True,
        )

        response = self.client.post(
            reverse('tramites:toggle_activacion_plantilla', args=[plantilla.id, 'CERTIFICADO']),
            data={'accion': 'desactivar'},
        )
        self.assertEqual(response.status_code, 302)

        plantilla.refresh_from_db()
        self.assertFalse(plantilla.activa_certificado)

    def test_toggle_tipo_invalido_retorna_400(self):
        plantilla = self.crear_plantilla_directa(preview_visto=True)
        response = self.client.post(
            reverse('tramites:toggle_activacion_plantilla', args=[plantilla.id, 'AMBOS']),
            data={'accion': 'activar'},
        )
        self.assertEqual(response.status_code, 400)

    def test_eliminar_activa_bloqueado(self):
        plantilla = self.crear_plantilla_directa(preview_visto=True, activa_certificado=True)
        response = self.client.post(
            reverse('tramites:eliminar_plantilla', args=[plantilla.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlantillaDocumento.objects.filter(pk=plantilla.pk).exists())
        self.assertFalse(
            BitacoraEvento.objects.filter(tipo_evento=BitacoraEvento.PLANTILLA_ELIMINADA).exists()
        )

    def test_eliminar_inactiva_borra_y_registra_bitacora(self):
        plantilla = self.crear_plantilla_directa(activa=False)
        plantilla_id = plantilla.pk
        nombre = plantilla.nombre

        response = self.client.post(
            reverse('tramites:eliminar_plantilla', args=[plantilla.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlantillaDocumento.objects.filter(pk=plantilla_id).exists())

        evento = BitacoraEvento.objects.get(tipo_evento=BitacoraEvento.PLANTILLA_ELIMINADA)
        self.assertEqual(evento.metadata.get('plantilla_id'), plantilla_id)
        self.assertEqual(evento.metadata.get('nombre'), nombre)
