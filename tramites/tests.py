from io import BytesIO
from unittest.mock import mock_open, patch

from django.core.exceptions import ValidationError
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from identidad.models import UsuarioMICI

from integracion.api_client import _mapear_campos
from integracion.services import normalizar_noconsta_entry

from .models import Tramite
from .services.generador_pdf import generar_html_tramite
from .views import agregar_empresa_desde_resultado_hx, agregar_empresa_hx, detalle_view, firmar_view


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


class TramitesEmpresaCartTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.usuario = self.crear_usuario(
            username='empresa-cart',
            email='empresa.cart@mici.gob.pa',
            cedula='8-555-0001',
            rol=UsuarioMICI.TRABAJADOR,
        )
        self.trabajador = self.usuario
        self.director = self.crear_usuario(
            username='director-cart',
            email='director.cart@mici.gob.pa',
            cedula='8-555-0002',
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
            'solicitante': self.usuario,
        }
        defaults.update(overrides)
        return Tramite.objects.create(**defaults)

    def preparar_request(self, path, user, method='get', data=None, htmx=False):
        factory_method = getattr(self.factory, method.lower())
        extra = {'HTTP_HX_REQUEST': 'true'} if htmx else {}
        request = factory_method(path, data or {}, **extra)
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = user
        setattr(request, '_messages', FallbackStorage(request))
        return request

    @patch('tramites.views.buscar_empresa_todas_paginas')
    @patch('tramites.views.buscar_empresa_por_campo')
    def test_agregar_empresa_hx_acepta_busqueda_directa_por_ruc(
        self,
        mock_buscar_empresa_por_campo,
        mock_buscar_empresa_todas_paginas,
    ):
        mock_buscar_empresa_por_campo.return_value = {
            'detalle': {},
            'avisos': [],
            'resultados_raw': [],
            'paginacion': {'current_page': 1, 'last_page': 1, 'total': 1, 'per_page': 10, 'has_next': False, 'has_previous': False},
        }
        mock_buscar_empresa_todas_paginas.return_value = [
            _mapear_campos({
                "numero_aviso": "645991-1-458971-2009-193089",
                "nombreComercial": "HORUS, S.A.",
                "razon_social_juridica": "HORUS ENTERPRISE",
                "razon_social_natural": "",
                "ruc": "645991-1-458971",
                "cedula_representante": "8-123-456",
                "representante_legal": "ANA HORUS",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 1,
            }),
        ]

        request = self.preparar_request(
            reverse('tramites:agregar_empresa_hx'),
            self.usuario,
            method='post',
            data={'campo_busqueda': 'ruc', 'empresa_query': '645991-1-458971'},
            htmx=True,
        )
        response = agregar_empresa_hx(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Trigger'], 'empresas-changed')
        self.assertEqual(len(request.session['empresas_cart']), 1)
        mock_buscar_empresa_por_campo.assert_called_once_with('645991-1-458971', 'ruc', page=1)
        mock_buscar_empresa_todas_paginas.assert_called_once_with('645991-1-458971')

    @patch('tramites.views.buscar_empresa_por_campo')
    def test_agregar_empresa_hx_rechaza_busqueda_directa_fuera_de_ruc_con_resultados(self, mock_buscar_empresa_por_campo):
        mock_buscar_empresa_por_campo.return_value = {
            'detalle': {},
            'avisos': [{'ruc_completo': '8-123-456'}],
            'resultados_raw': [{'ruc': '8-123-456'}],
            'paginacion': {'current_page': 1, 'last_page': 1, 'total': 1, 'per_page': 10, 'has_next': False, 'has_previous': False},
        }

        request = self.preparar_request(
            reverse('tramites:agregar_empresa_hx'),
            self.usuario,
            method='post',
            data={'campo_busqueda': 'cedula', 'empresa_query': '8-123-456'},
            htmx=True,
        )
        response = agregar_empresa_hx(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Agregue la empresa desde una fila de la tabla', response.content.decode())
        self.assertNotIn('empresas_cart', request.session)
        self.assertNotIn('noconsta_cart', request.session)

    @patch('tramites.views.buscar_empresa_todas_paginas')
    @patch('tramites.views.buscar_empresa_por_campo', return_value=None)
    def test_agregar_empresa_hx_genera_noconsta_automatico_sin_resultados_ruc(
        self,
        mock_buscar_empresa_por_campo,
        mock_buscar_empresa_todas_paginas,
    ):
        request = self.preparar_request(
            reverse('tramites:agregar_empresa_hx'),
            self.usuario,
            method='post',
            data={'campo_busqueda': 'ruc', 'empresa_query': '99990000'},
            htmx=True,
        )
        response = agregar_empresa_hx(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Trigger'], 'noconsta-changed')
        self.assertEqual(response['HX-Retarget'], '#noconsta-cart')
        self.assertEqual(response['HX-Reswap'], 'outerHTML')
        self.assertEqual(
            request.session['noconsta_cart'],
            [normalizar_noconsta_entry('ruc: 99990000')],
        )
        mock_buscar_empresa_por_campo.assert_called_once_with('99990000', 'ruc', page=1)
        mock_buscar_empresa_todas_paginas.assert_not_called()

    @patch('tramites.views.buscar_empresa_todas_paginas')
    @patch('tramites.views.buscar_empresa_por_campo', return_value=None)
    def test_agregar_empresa_hx_genera_noconsta_automatico_sin_resultados_cedula(
        self,
        mock_buscar_empresa_por_campo,
        mock_buscar_empresa_todas_paginas,
    ):
        request = self.preparar_request(
            reverse('tramites:agregar_empresa_hx'),
            self.usuario,
            method='post',
            data={'campo_busqueda': 'cedula', 'empresa_query': '8-123-456'},
            htmx=True,
        )
        response = agregar_empresa_hx(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            request.session['noconsta_cart'],
            [normalizar_noconsta_entry('cedula: 8-123-456')],
        )
        self.assertEqual(response['HX-Retarget'], '#noconsta-cart')
        mock_buscar_empresa_por_campo.assert_called_once_with('8-123-456', 'cedula', page=1)
        mock_buscar_empresa_todas_paginas.assert_not_called()

    @patch('tramites.views.buscar_empresa_por_campo', return_value=None)
    def test_agregar_empresa_hx_evita_duplicados_noconsta(self, mock_buscar_empresa_por_campo):
        request = self.preparar_request(
            reverse('tramites:agregar_empresa_hx'),
            self.usuario,
            method='post',
            data={'campo_busqueda': 'razon_social', 'empresa_query': 'HORUS ENTERPRISE'},
            htmx=True,
        )
        request.session['noconsta_cart'] = ['razon social: HORUS ENTERPRISE']
        request.session.save()

        response = agregar_empresa_hx(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('ya fue agregada', response.content.decode())
        self.assertEqual(
            request.session['noconsta_cart'],
            [normalizar_noconsta_entry('razon social: HORUS ENTERPRISE')],
        )
        mock_buscar_empresa_por_campo.assert_called_once_with('HORUS ENTERPRISE', 'razon_social', page=1)

    @patch('tramites.views.buscar_empresa_por_campo')
    @patch('tramites.views.buscar_empresa_todas_paginas')
    def test_agregar_empresa_desde_resultado_hx_ignora_filtro_actual_y_no_genera_noconsta(
        self,
        mock_buscar_empresa_todas_paginas,
        mock_buscar_empresa_por_campo,
    ):
        mock_buscar_empresa_todas_paginas.return_value = [
            _mapear_campos({
                "numero_aviso": "30486-2-239028-2011-307149",
                "nombreComercial": "EL TELAR, S.A.",
                "razon_social_juridica": "EL TELAR S A",
                "razon_social_natural": "",
                "ruc": "30486-2-239028",
                "cedula_representante": "8-155-1818",
                "representante_legal": "JAIME ANGEL CATTAN",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 1,
            }),
        ]

        request = self.preparar_request(
            reverse('tramites:agregar_empresa_desde_resultado_hx'),
            self.usuario,
            method='post',
            data={
                'ruc_empresa': '30486-2-239028',
                'campo_busqueda': 'nombre_comercial',
                'empresa_query': 'EL TELAR',
            },
            htmx=True,
        )
        response = agregar_empresa_desde_resultado_hx(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Trigger'], 'empresas-changed')
        self.assertEqual(len(request.session['empresas_cart']), 1)
        self.assertNotIn('noconsta_cart', request.session)
        mock_buscar_empresa_todas_paginas.assert_called_once_with('30486-2-239028')
        mock_buscar_empresa_por_campo.assert_not_called()

    def test_detalle_normaliza_noconsta_snapshot_legacy(self):
        tramite = self.crear_tramite(
            noconsta_snapshot=['nombre comercial: HORUS'],
        )
        request = self.preparar_request(reverse('tramites:detalle', args=[tramite.uuid]), self.usuario)

        response = detalle_view(request, tramite.uuid)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Nombre comercial: HORUS', response.content.decode())


class TramitesPdfRenderingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.usuario = UsuarioMICI.objects.create_user(
            username='pdf-render',
            email='pdf.render@mici.gob.pa',
            cedula='8-700-0001',
            institucion='MICI',
            rol=UsuarioMICI.TRABAJADOR,
            password='ClaveSegura!2026',
            is_active=True,
        )
        self.trabajador = self.usuario
        self.director = UsuarioMICI.objects.create_user(
            username='pdf-render-director',
            email='pdf.render.director@mici.gob.pa',
            cedula='8-700-0002',
            institucion='MICI',
            rol=UsuarioMICI.DIRECTOR,
            password='ClaveSegura!2026',
            is_active=True,
        )

    def crear_tramite(self, **overrides):
        defaults = {
            'tipo_documento': 'CERTIFICADO',
            'estado': Tramite.EN_REVISION,
            'numero_referencia': 'PDF-001',
            'empresa_snapshot': [],
            'noconsta_snapshot': [],
            'solicitante': self.usuario,
            'destinatario': 'DESTINATARIO PRUEBA',
            'objetivo_solicitud': 'verificar antecedentes comerciales',
        }
        defaults.update(overrides)
        return Tramite.objects.create(**defaults)

    def preparar_request(self, path, user, method='get', data=None):
        factory_method = getattr(self.factory, method.lower())
        request = factory_method(path, data or {})
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = user
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def test_generar_html_tramite_usa_frase_noconsta_normalizada(self):
        tramite = self.crear_tramite(
            noconsta_snapshot=['ruc: 9000000'],
        )

        html = generar_html_tramite(tramite)

        self.assertIn('asociado al siguiente RUC: 9000000', html)
        self.assertNotIn('asociado a los siguientes datos: ruc: 9000000', html)

    def test_generar_html_tramite_mantiene_texto_justificado_en_certificado(self):
        tramite = self.crear_tramite()

        html = generar_html_tramite(tramite)

        self.assertIn('.cuerpo p { text-align: justify; }', html)

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
