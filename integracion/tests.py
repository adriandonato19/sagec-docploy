from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from integracion.adapters import normalizar_datos_empresa, normalizar_lista_avisos
from integracion.api_client import _mapear_campos
from integracion.views import api_search_view


class IntegracionMappingTests(TestCase):
    def test_mantiene_ruc_para_registro_juridico(self):
        registro = {
            "numero_aviso": "1156670-1-558090-2007-6",
            "nombreComercial": "ALTIBARMAK",
            "razon_social_juridica": "altibarmak import & export, inc",
            "razon_social_natural": "",
            "ruc": "1156670-1-558090",
            "cedula_representante": "4-293-79",
            "representante_legal": "jaime mojica rivera",
            "estado": "Cancelado ",
            "tipo": "Juridico",
            "fecha_inicio_operaciones": "2007-07-01",
            "monto_estimado": 10000,
            "id_sucursal": 74,
        }

        mapeado = _mapear_campos(registro)
        normalizado = normalizar_datos_empresa(mapeado)

        self.assertEqual(mapeado["tipo"], "Juridico")
        self.assertEqual(mapeado["ruc"], "1156670-1-558090")
        self.assertEqual(normalizado["ruc_completo"], "1156670-1-558090")

    def test_usa_cedula_como_ruc_para_persona_natural_sin_ruc(self):
        registro = {
            "numero_aviso": "4-148-986-2007-0",
            "nombreComercial": "AGROPECUARIA J&M",
            "razon_social_juridica": None,
            "razon_social_natural": "Manuel Amador Pitti Staff",
            "ruc": "",
            "cedula_representante": "4-148-986",
            "representante_legal": "Manuel Amador Pitti Staff ",
            "estado": "En solicitud",
            "tipo": " Natural ",
            "fecha_inicio_operaciones": "2007-09-01",
            "monto_estimado": 5000,
            "id_sucursal": 99,
        }

        mapeado = _mapear_campos(registro)
        normalizado = normalizar_datos_empresa(mapeado)

        self.assertEqual(mapeado["ruc"], "4-148-986")
        self.assertEqual(mapeado["cedula_representante"], "4-148-986")
        self.assertEqual(normalizado["ruc"], "4-148-986")
        self.assertEqual(normalizado["ruc_completo"], "4-148-986")

    def test_no_sobrescribe_ruc_existente_para_persona_natural(self):
        registro = {
            "numero_aviso": "789321-2025",
            "nombreComercial": "MINI SUPER LA BENDICIÓN",
            "razon_social_juridica": None,
            "razon_social_natural": "Ana Gómez",
            "ruc": "8-765-4321",
            "cedula_representante": "4-148-986",
            "representante_legal": "Ana Gómez",
            "estado": "Vigente",
            "tipo": "Natural",
            "fecha_inicio_operaciones": "2018-12-12",
            "monto_estimado": 2000,
            "id_sucursal": 5,
        }

        mapeado = _mapear_campos(registro)
        normalizado = normalizar_datos_empresa(mapeado)

        self.assertEqual(mapeado["ruc"], "8-765-4321")
        self.assertEqual(normalizado["ruc_completo"], "8-765-4321")

    def test_deja_ruc_vacio_si_natural_no_trae_ruc_ni_cedula(self):
        registro = {
            "numero_aviso": "4-148-986-2007-0",
            "nombreComercial": "AGROPECUARIA J&M",
            "razon_social_juridica": None,
            "razon_social_natural": "Manuel Amador Pitti Staff",
            "ruc": "",
            "cedula_representante": "",
            "representante_legal": "Manuel Amador Pitti Staff",
            "estado": "En solicitud",
            "tipo": "Natural",
            "fecha_inicio_operaciones": "2007-09-01",
            "monto_estimado": 5000,
            "id_sucursal": 99,
        }

        mapeado = _mapear_campos(registro)
        normalizado = normalizar_datos_empresa(mapeado)

        self.assertEqual(mapeado["ruc"], "")
        self.assertEqual(normalizado["ruc_completo"], "")


class IntegracionSearchViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="integracion-tester",
            password="ClaveSegura12345",
            cedula="8-000-0001",
        )

    @patch("integracion.views.buscar_empresa")
    def test_api_search_renderiza_cedula_en_columna_ruc_para_persona_natural(self, mock_buscar_empresa):
        registro_mapeado = _mapear_campos({
            "numero_aviso": "4-148-986-2007-0",
            "nombreComercial": "AGROPECUARIA J&M",
            "razon_social_juridica": None,
            "razon_social_natural": "Manuel Amador Pitti Staff",
            "ruc": "",
            "cedula_representante": "4-148-986",
            "representante_legal": "Manuel Amador Pitti Staff ",
            "estado": "En solicitud",
            "tipo": "Natural",
            "fecha_inicio_operaciones": "2007-09-01",
            "provincia": "CHIRIQUÍ",
            "distrito": "DOLEGA",
            "corregimiento": "POTRERILLOS ABAJO",
            "urbanizacion": "S/I",
            "calle": "PRINCIPAL, VIA CITRICOS S.A.",
            "casa": "40",
            "edificio": "",
            "apartamento": "",
            "monto_estimado": 5000,
            "id_sucursal": 99,
        })
        mock_buscar_empresa.return_value = {
            "detalle": normalizar_datos_empresa(registro_mapeado),
            "avisos": normalizar_lista_avisos([registro_mapeado]),
            "resultados_raw": [registro_mapeado],
            "paginacion": {
                "current_page": 1,
                "last_page": 1,
                "total": 1,
                "per_page": 10,
                "has_next": False,
                "has_previous": False,
            },
        }

        request = self.factory.get(
            reverse("integracion:api_search"),
            {"ruc_empresa": "4-148-986"},
            HTTP_HX_REQUEST="true",
        )
        request.user = self.user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        response = api_search_view(request)
        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn("4-148-986", contenido)
        self.assertGreaterEqual(contenido.count("4-148-986"), 3)
        self.assertIn('{"ruc_empresa": "4-148-986"}', response.content.decode())
        self.assertEqual(
            request.session["ultimos_resultados_api"][0]["ruc"],
            "4-148-986",
        )
