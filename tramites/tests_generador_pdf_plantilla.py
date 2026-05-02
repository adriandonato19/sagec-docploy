"""Tests de integración: resolución de plantillas en la generación del PDF."""
from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase
from PIL import Image

from identidad.models import UsuarioMICI
from tramites.models import PlantillaDocumento, Tramite
from tramites.services.generador_pdf import (
    MARGEN_IZQUIERDO_MIN_RENDER,
    PLANTILLA_FALLBACK_ESTATICA,
    _clamp_margenes,
    _resolver_plantilla,
)


def _png_bytes(color=(20, 80, 160), size=(300, 60)):
    img = Image.new('RGB', size, color=color)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class ResolverPlantillaTests(TestCase):
    def setUp(self):
        self.director = UsuarioMICI.objects.create_user(
            username='dir-plantilla',
            email='dir.plantilla@mici.gob.pa',
            cedula='8-900-0001',
            institucion='MICI',
            rol=UsuarioMICI.DIRECTOR,
            password='ClaveSegura!2026',
            is_active=True,
        )
        self.solicitante = UsuarioMICI.objects.create_user(
            username='sol-plantilla',
            email='sol.plantilla@mici.gob.pa',
            cedula='8-900-0002',
            institucion='MICI',
            rol=UsuarioMICI.FISCAL,
            password='ClaveSegura!2026',
            is_active=True,
        )

    def crear_tramite(self, **overrides):
        defaults = {
            'tipo_documento': 'CERTIFICADO',
            'estado': Tramite.PENDIENTE,
            'numero_referencia': 'PLT-001',
            'empresa_snapshot': [],
            'solicitante': self.solicitante,
        }
        defaults.update(overrides)
        return Tramite.objects.create(**defaults)

    def crear_plantilla(self, tipo=PlantillaDocumento.AMBOS, activa=True, **overrides):
        plantilla = PlantillaDocumento(
            nombre=overrides.pop('nombre', 'Plantilla Test'),
            tipo_aplicable=tipo,
            creado_por=self.director,
            activa=activa,
            preview_visto=True,
            margen_superior_cm=overrides.pop('margen_superior_cm', 2.0),
            margen_inferior_cm=overrides.pop('margen_inferior_cm', 2.0),
            margen_izquierdo_cm=overrides.pop('margen_izquierdo_cm', 3.0),
            margen_derecho_cm=overrides.pop('margen_derecho_cm', 2.0),
        )
        plantilla.archivo_word.save('test.docx', ContentFile(b'fake'), save=False)
        plantilla.imagen_header.save('header.png', ContentFile(_png_bytes()), save=False)
        if overrides.pop('con_footer', False):
            plantilla.imagen_footer.save('footer.png', ContentFile(_png_bytes(color=(50, 200, 50))), save=False)
        plantilla.save()
        return plantilla

    def test_sin_plantilla_activa_usa_fallback_estatico(self):
        tramite = self.crear_tramite(estado=Tramite.BORRADOR)

        resuelta = _resolver_plantilla(tramite)

        self.assertEqual(resuelta, PLANTILLA_FALLBACK_ESTATICA)
        tramite.refresh_from_db()
        self.assertEqual(tramite.plantilla_snapshot, {})

    def test_plantilla_activa_para_tipo_se_aplica_y_congela_snapshot(self):
        plantilla = self.crear_plantilla(tipo=PlantillaDocumento.CERTIFICADO)
        tramite = self.crear_tramite(tipo_documento='CERTIFICADO')

        resuelta = _resolver_plantilla(tramite)

        self.assertEqual(resuelta['margen_izquierdo_cm'], 3.0)
        self.assertTrue(resuelta['imagen_header_path'].endswith('.png'))
        tramite.refresh_from_db()
        self.assertNotEqual(tramite.plantilla_snapshot, {})
        self.assertEqual(tramite.plantilla_snapshot['margen_izquierdo_cm'], 3.0)
        plantilla.delete()

    def test_plantilla_ambos_aplica_a_oficio_y_certificado(self):
        plantilla = self.crear_plantilla(tipo=PlantillaDocumento.AMBOS)

        cert = self.crear_tramite(tipo_documento='CERTIFICADO', numero_referencia='C-1')
        oficio = self.crear_tramite(tipo_documento='OFICIO', numero_referencia='O-1')

        cert_resuelta = _resolver_plantilla(cert)
        oficio_resuelta = _resolver_plantilla(oficio)

        self.assertEqual(cert_resuelta['margen_izquierdo_cm'], 3.0)
        self.assertEqual(oficio_resuelta['margen_izquierdo_cm'], 3.0)
        plantilla.delete()

    def test_plantilla_solo_oficio_no_aplica_a_certificado(self):
        plantilla = self.crear_plantilla(tipo=PlantillaDocumento.OFICIO)
        tramite = self.crear_tramite(tipo_documento='CERTIFICADO')

        resuelta = _resolver_plantilla(tramite)

        self.assertEqual(resuelta, PLANTILLA_FALLBACK_ESTATICA)
        tramite.refresh_from_db()
        self.assertEqual(tramite.plantilla_snapshot, {})
        plantilla.delete()

    def test_snapshot_existente_es_inmutable_aunque_cambie_la_plantilla_activa(self):
        plantilla = self.crear_plantilla(margen_izquierdo_cm=3.0)
        tramite = self.crear_tramite(tipo_documento='CERTIFICADO')

        # Primera generación congela snapshot con margen 3.0
        _resolver_plantilla(tramite)
        tramite.refresh_from_db()
        self.assertEqual(tramite.plantilla_snapshot['margen_izquierdo_cm'], 3.0)

        # El director cambia la plantilla
        plantilla.margen_izquierdo_cm = 5.0
        plantilla.save()

        # Generaciones posteriores siguen usando el snapshot original
        resuelta_2 = _resolver_plantilla(tramite)
        self.assertEqual(resuelta_2['margen_izquierdo_cm'], 3.0)
        plantilla.delete()

    def test_snapshot_existente_se_usa_aunque_no_haya_plantilla_activa(self):
        snapshot_legado = dict(PLANTILLA_FALLBACK_ESTATICA)
        snapshot_legado['margen_superior_cm'] = 9.99  # marcador identificable
        tramite = self.crear_tramite(plantilla_snapshot=snapshot_legado)

        resuelta = _resolver_plantilla(tramite)

        self.assertEqual(resuelta['margen_superior_cm'], 9.99)

    def test_solo_una_plantilla_activa_por_tipo(self):
        from django.db import transaction
        from django.db.utils import IntegrityError

        primera = self.crear_plantilla(
            tipo=PlantillaDocumento.CERTIFICADO,
            nombre='Primera',
        )
        # Crear una segunda activa del MISMO tipo debe violar el constraint.
        # Se envuelve en savepoint para que el rollback parcial no rompa la
        # transacción del test.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_plantilla(
                    tipo=PlantillaDocumento.CERTIFICADO,
                    nombre='Segunda',
                )
        primera.delete()

    def test_plantilla_inactiva_no_se_aplica(self):
        plantilla = self.crear_plantilla(activa=False)
        tramite = self.crear_tramite(tipo_documento='CERTIFICADO')

        resuelta = _resolver_plantilla(tramite)

        self.assertEqual(resuelta, PLANTILLA_FALLBACK_ESTATICA)
        plantilla.delete()


class ClampMargenesTests(TestCase):
    """El clamp protege el render de snapshots/plantillas con margen izquierdo
    insuficiente para alojar el sidebar de QR (2.2cm fijos)."""

    def test_clamp_eleva_margen_izquierdo_chico_al_minimo(self):
        snapshot = {
            'imagen_header_path': '/tmp/h.png',
            'imagen_footer_path': '',
            'margen_superior_cm': 1.8,
            'margen_inferior_cm': 2.8,
            'margen_izquierdo_cm': 0.5,
            'margen_derecho_cm': 1.8,
        }

        clamped = _clamp_margenes(snapshot)

        self.assertEqual(clamped['margen_izquierdo_cm'], MARGEN_IZQUIERDO_MIN_RENDER)
        # No mutó el original
        self.assertEqual(snapshot['margen_izquierdo_cm'], 0.5)

    def test_clamp_no_modifica_margen_izquierdo_valido(self):
        snapshot = dict(PLANTILLA_FALLBACK_ESTATICA)  # margen_izquierdo_cm=3.2

        clamped = _clamp_margenes(snapshot)

        self.assertEqual(clamped['margen_izquierdo_cm'], 3.2)

    def test_clamp_preserva_resto_de_campos(self):
        snapshot = {
            'imagen_header_path': '/tmp/h.png',
            'imagen_footer_path': '/tmp/f.png',
            'margen_superior_cm': 1.0,
            'margen_inferior_cm': 4.5,
            'margen_izquierdo_cm': 1.0,
            'margen_derecho_cm': 0.8,
        }

        clamped = _clamp_margenes(snapshot)

        self.assertEqual(clamped['imagen_header_path'], '/tmp/h.png')
        self.assertEqual(clamped['imagen_footer_path'], '/tmp/f.png')
        self.assertEqual(clamped['margen_superior_cm'], 1.0)
        self.assertEqual(clamped['margen_inferior_cm'], 4.5)
        self.assertEqual(clamped['margen_derecho_cm'], 0.8)
        self.assertEqual(clamped['margen_izquierdo_cm'], MARGEN_IZQUIERDO_MIN_RENDER)

    def test_clamp_no_falla_con_valor_none(self):
        # Defensa contra snapshots corruptos / incompletos: pasan through sin crash.
        self.assertIsNone(_clamp_margenes(None))
        self.assertEqual(_clamp_margenes({}), {})


class ResolverPlantillaConClampTests(TestCase):
    """El clamp se aplica DENTRO de _resolver_plantilla para snapshots legacy."""

    def setUp(self):
        self.solicitante = UsuarioMICI.objects.create_user(
            username='sol-clamp',
            email='sol.clamp@mici.gob.pa',
            cedula='8-900-0099',
            institucion='MICI',
            rol=UsuarioMICI.FISCAL,
            password='ClaveSegura!2026',
            is_active=True,
        )

    def test_snapshot_legacy_con_margen_chico_se_eleva_en_runtime(self):
        snapshot_legacy = {
            'imagen_header_path': 'static/img/logo_oficial.png',
            'imagen_footer_path': 'static/img/footer_certificado.png',
            'margen_superior_cm': 2.5,
            'margen_inferior_cm': 2.5,
            'margen_izquierdo_cm': 1.0,  # Valor inseguro de un trámite viejo
            'margen_derecho_cm': 2.5,
        }
        tramite = Tramite.objects.create(
            tipo_documento='OFICIO',
            estado=Tramite.PENDIENTE,
            numero_referencia='LEG-001',
            empresa_snapshot=[],
            solicitante=self.solicitante,
            plantilla_snapshot=snapshot_legacy,
        )

        resuelta = _resolver_plantilla(tramite)

        # Render seguro
        self.assertEqual(resuelta['margen_izquierdo_cm'], MARGEN_IZQUIERDO_MIN_RENDER)
        # El JSON guardado en BD NO se modifica (inmutabilidad documental)
        tramite.refresh_from_db()
        self.assertEqual(tramite.plantilla_snapshot['margen_izquierdo_cm'], 1.0)
