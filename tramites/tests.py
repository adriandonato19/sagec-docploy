from io import BytesIO
from unittest.mock import mock_open, patch

from django.core.exceptions import ValidationError
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from identidad.models import UsuarioMICI

from .models import Tramite
from .views import detalle_view, firmar_view


class TramitesWorkflowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.solicitante = self.crear_usuario(
            username='fiscal',
            email='fiscal@mici.gob.pa',
            cedula='8-000-1001',
            rol=UsuarioMICI.FISCAL,
        )
        self.trabajador = self.crear_usuario(
            username='trabajador',
            email='trabajador@mici.gob.pa',
            cedula='8-000-1002',
            rol=UsuarioMICI.TRABAJADOR,
        )
        self.director = self.crear_usuario(
            username='director',
            email='director@mici.gob.pa',
            cedula='8-000-1003',
            rol=UsuarioMICI.DIRECTOR,
        )

    def crear_usuario(self, **overrides):
        defaults = {
            'first_name': 'Usuario',
            'last_name': 'Prueba',
            'institucion': 'MICI',
            'password': 'ClaveSegura!2026',
            'is_active': True,
        }
        defaults.update(overrides)
        password = defaults.pop('password')
        return UsuarioMICI.objects.create_user(password=password, **defaults)

    def crear_tramite(self, **overrides):
        defaults = {
            'tipo_documento': 'CERTIFICADO',
            'estado': Tramite.BORRADOR,
            'numero_referencia': 'TRM-001',
            'empresa_snapshot': [],
            'solicitante': self.solicitante,
        }
        defaults.update(overrides)
        return Tramite.objects.create(**defaults)

    def preparar_request(self, path, user):
        request = self.factory.get(path)
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = user
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def test_aprobar_pasa_a_en_revision(self):
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE)

        tramite.aprobar(self.trabajador)
        tramite.refresh_from_db()

        self.assertEqual(tramite.estado, Tramite.EN_REVISION)
        self.assertEqual(tramite.revisor, self.trabajador)
        self.assertIsNotNone(tramite.fecha_revision)

    def test_aprobar_pdf_pasa_a_aprobado(self):
        tramite = self.crear_tramite(
            estado=Tramite.EN_REVISION,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
        )

        tramite.aprobar_pdf(self.trabajador)
        tramite.refresh_from_db()

        self.assertEqual(tramite.estado, Tramite.APROBADO)
        self.assertEqual(tramite.revisor, self.trabajador)

    def test_aprobar_pdf_falla_fuera_de_en_revision(self):
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE)

        with self.assertRaises(ValidationError):
            tramite.aprobar_pdf(self.trabajador)

    def test_marcar_firmado_exige_estado_aprobado(self):
        tramite = self.crear_tramite(estado=Tramite.EN_REVISION)

        with self.assertRaises(ValidationError):
            tramite.marcar_firmado(self.director)

    def test_regresar_aprobado_vuelve_a_en_revision(self):
        tramite = self.crear_tramite(
            estado=Tramite.APROBADO,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )

        tramite.regresar(self.trabajador)
        tramite.refresh_from_db()

        self.assertEqual(tramite.estado, Tramite.EN_REVISION)
        self.assertEqual(tramite.archivo_pdf.name, 'temp_pdfs/demo.pdf')
        self.assertEqual(tramite.html_pdf_editado, '<div class="document-container">PDF</div>')

    @patch('tramites.models.Path.unlink')
    @patch('tramites.models.Path.exists', return_value=True)
    def test_regresar_en_revision_vuelve_a_pendiente_y_limpia_borrador(self, mock_exists, mock_unlink):
        del mock_exists
        tramite = self.crear_tramite(
            estado=Tramite.EN_REVISION,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )

        tramite.regresar(self.trabajador)
        tramite.refresh_from_db()

        self.assertEqual(tramite.estado, Tramite.PENDIENTE)
        self.assertEqual(tramite.html_pdf_editado, '')
        self.assertFalse(tramite.archivo_pdf)
        mock_unlink.assert_called_once()

    def test_rechazar_exige_motivo(self):
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE)

        with self.assertRaises(ValidationError):
            tramite.rechazar(self.trabajador, '   ')

    @patch('tramites.views.obtener_ip_cliente', return_value='127.0.0.1')
    @patch('tramites.views.registrar_evento')
    @patch('tramites.views.generar_pdf_tramite', return_value=BytesIO(b'%PDF-1.4'))
    @patch('tramites.views.generar_html_tramite', return_value='<div class="document-container">PDF</div>')
    @patch('tramites.views.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_aprobar_view_genera_pdf_y_envia_a_en_revision(
        self,
        mock_file,
        mock_mkdir,
        mock_generar_html,
        mock_generar_pdf,
        mock_registrar_evento,
        mock_ip,
    ):
        del mock_file, mock_mkdir, mock_generar_html, mock_generar_pdf, mock_ip
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE, numero_referencia='TRM-APR')
        self.client.force_login(self.trabajador)

        response = self.client.post(reverse('tramites:aprobar', args=[tramite.uuid]))

        self.assertEqual(response.status_code, 302)
        tramite.refresh_from_db()
        self.assertEqual(tramite.estado, Tramite.EN_REVISION)
        self.assertEqual(tramite.html_pdf_editado, '<div class="document-container">PDF</div>')
        self.assertEqual(tramite.archivo_pdf.name, f'temp_pdfs/tramite_{tramite.uuid}.pdf')
        self.assertEqual(mock_registrar_evento.call_args.kwargs['metadata']['fase'], 'solicitud')

    @patch('tramites.views.obtener_ip_cliente', return_value='127.0.0.1')
    @patch('tramites.views.registrar_evento')
    def test_aprobar_pdf_view_mueve_a_aprobado(self, mock_registrar_evento, mock_ip):
        del mock_ip
        tramite = self.crear_tramite(
            estado=Tramite.EN_REVISION,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
        )
        self.client.force_login(self.trabajador)

        response = self.client.post(reverse('tramites:aprobar_pdf', args=[tramite.uuid]))

        self.assertEqual(response.status_code, 302)
        tramite.refresh_from_db()
        self.assertEqual(tramite.estado, Tramite.APROBADO)
        self.assertEqual(mock_registrar_evento.call_args.kwargs['metadata']['fase'], 'pdf')

    @patch('tramites.views.obtener_ip_cliente', return_value='127.0.0.1')
    @patch('tramites.views.registrar_evento')
    def test_rechazar_view_pasa_a_rechazado(self, mock_registrar_evento, mock_ip):
        del mock_ip
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE)
        self.client.force_login(self.trabajador)

        response = self.client.post(
            reverse('tramites:rechazar', args=[tramite.uuid]),
            {'motivo_rechazo': 'Falta documentación.'},
        )

        self.assertEqual(response.status_code, 302)
        tramite.refresh_from_db()
        self.assertEqual(tramite.estado, Tramite.RECHAZADO)
        self.assertEqual(tramite.motivo_rechazo, 'Falta documentación.')
        self.assertEqual(mock_registrar_evento.call_args.kwargs['tipo_evento'], 'RECHAZO')

    @patch('tramites.views.obtener_ip_cliente', return_value='127.0.0.1')
    @patch('tramites.views.registrar_evento')
    def test_regresar_view_desde_aprobado_vuelve_a_en_revision(self, mock_registrar_evento, mock_ip):
        del mock_ip
        tramite = self.crear_tramite(
            estado=Tramite.APROBADO,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )
        self.client.force_login(self.trabajador)

        response = self.client.post(
            reverse('tramites:regresar', args=[tramite.uuid]),
            {'nota_regreso': 'Revisar el contenido del PDF.'},
        )

        self.assertEqual(response.status_code, 302)
        tramite.refresh_from_db()
        self.assertEqual(tramite.estado, Tramite.EN_REVISION)
        self.assertEqual(mock_registrar_evento.call_args.kwargs['metadata']['estado_nuevo'], Tramite.EN_REVISION)

    @patch('tramites.views.obtener_ip_cliente', return_value='127.0.0.1')
    @patch('tramites.views.registrar_evento')
    @patch('tramites.models.Path.unlink')
    @patch('tramites.models.Path.exists', return_value=True)
    def test_regresar_view_desde_en_revision_vuelve_a_pendiente(
        self,
        mock_exists,
        mock_unlink,
        mock_registrar_evento,
        mock_ip,
    ):
        del mock_exists, mock_ip
        tramite = self.crear_tramite(
            estado=Tramite.EN_REVISION,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )
        self.client.force_login(self.trabajador)

        response = self.client.post(reverse('tramites:regresar', args=[tramite.uuid]))

        self.assertEqual(response.status_code, 302)
        tramite.refresh_from_db()
        self.assertEqual(tramite.estado, Tramite.PENDIENTE)
        self.assertEqual(tramite.html_pdf_editado, '')
        self.assertFalse(tramite.archivo_pdf)
        self.assertEqual(mock_registrar_evento.call_args.kwargs['metadata']['estado_nuevo'], Tramite.PENDIENTE)
        mock_unlink.assert_called_once()

    def test_detalle_muestra_acciones_de_en_revision(self):
        tramite = self.crear_tramite(
            estado=Tramite.EN_REVISION,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )
        request = self.preparar_request(reverse('tramites:detalle', args=[tramite.uuid]), self.trabajador)
        response = detalle_view(request, tramite.uuid)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn(reverse('tramites:editar_pdf', args=[tramite.uuid]), contenido)
        self.assertIn(reverse('tramites:aprobar_pdf', args=[tramite.uuid]), contenido)
        self.assertIn(reverse('tramites:regresar', args=[tramite.uuid]), contenido)
        self.assertNotIn(reverse('tramites:firmar', args=[tramite.uuid]), contenido)

    def test_detalle_muestra_firma_y_oculta_edicion_en_aprobado(self):
        tramite = self.crear_tramite(
            estado=Tramite.APROBADO,
            revisor=self.trabajador,
            html_pdf_editado='<div class="document-container">PDF</div>',
            archivo_pdf='temp_pdfs/demo.pdf',
        )
        request = self.preparar_request(reverse('tramites:detalle', args=[tramite.uuid]), self.director)
        response = detalle_view(request, tramite.uuid)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn(reverse('tramites:firmar', args=[tramite.uuid]), contenido)
        self.assertIn(reverse('tramites:regresar', args=[tramite.uuid]), contenido)
        self.assertNotIn(reverse('tramites:editar_pdf', args=[tramite.uuid]), contenido)
        self.assertNotIn(reverse('tramites:aprobar_pdf', args=[tramite.uuid]), contenido)

    def test_detalle_muestra_rechazo_en_pendiente(self):
        tramite = self.crear_tramite(estado=Tramite.PENDIENTE)
        request = self.preparar_request(reverse('tramites:detalle', args=[tramite.uuid]), self.trabajador)
        response = detalle_view(request, tramite.uuid)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn(reverse('tramites:rechazar', args=[tramite.uuid]), contenido)
        self.assertNotIn(reverse('tramites:regresar', args=[tramite.uuid]), contenido)

    def test_aprobado_existente_sigue_accediendo_a_pantalla_de_firma(self):
        tramite = self.crear_tramite(
            estado=Tramite.APROBADO,
            revisor=self.trabajador,
            archivo_pdf='temp_pdfs/demo.pdf',
        )
        request = self.preparar_request(reverse('tramites:firmar', args=[tramite.uuid]), self.director)
        response = firmar_view(request, tramite.uuid)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Firmar con Certificado Digital', response.content.decode())
