from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from integracion.adapters import normalizar_datos_empresa, normalizar_lista_avisos
from integracion.api_client import _mapear_campos
from integracion.services import (
    buscar_empresa_por_campo,
    construir_noconsta_entry,
    normalizar_noconsta_entry,
)
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

    @patch("integracion.views.buscar_empresa_por_campo")
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

    @patch("integracion.views.buscar_empresa_por_campo")
    def test_api_search_preserva_campo_busqueda_en_paginacion(self, mock_buscar_empresa):
        registros = [
            _mapear_campos({
                "numero_aviso": f"645991-1-458971-2010-{indice}",
                "nombreComercial": "HORUS, S.A.",
                "razon_social_juridica": f"HORUS ENTERPRISE {indice}",
                "razon_social_natural": "",
                "ruc": "645991-1-458971",
                "cedula_representante": "8-111-222",
                "representante_legal": "MARIA HORUS",
                "estado": "Vigente",
                "tipo": "Juridico",
                "fecha_inicio_operaciones": "2010-01-01",
                "monto_estimado": 1000,
                "id_sucursal": indice,
            })
            for indice in range(1, 11)
        ]
        mock_buscar_empresa.return_value = {
            "detalle": normalizar_datos_empresa(registros[0]),
            "avisos": normalizar_lista_avisos(registros),
            "resultados_raw": registros,
            "paginacion": {
                "current_page": 1,
                "last_page": 2,
                "total": 11,
                "per_page": 10,
                "has_next": True,
                "has_previous": False,
            },
        }

        request = self.factory.get(
            reverse("integracion:api_search"),
            {"empresa_query": "horus", "campo_busqueda": "razon_social"},
            HTTP_HX_REQUEST="true",
        )
        request.user = self.user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        response = api_search_view(request)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('Filtro aplicado: Razón social = "horus"', contenido)
        self.assertIn('empresa_query=horus&campo_busqueda=razon_social&page=2', contenido)
        self.assertIn('data-empresa-pagination="true"', contenido)
        self.assertIn('type="button"', contenido)
        mock_buscar_empresa.assert_called_once_with("horus", "razon_social", page=1)

    @patch("integracion.views.buscar_empresa_por_campo", return_value=None)
    def test_api_search_sin_resultados_indica_generacion_automatica_de_noconsta(self, mock_buscar_empresa):
        request = self.factory.get(
            reverse("integracion:api_search"),
            {"empresa_query": "99990000", "campo_busqueda": "ruc"},
            HTTP_HX_REQUEST="true",
        )
        request.user = self.user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        response = api_search_view(request)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        self.assertIn('Si presiona <strong>Agregar</strong>', contenido)
        self.assertIn('asociado al siguiente RUC: 99990000', contenido)
        self.assertIn('data-auto-noconsta="true"', contenido)
        mock_buscar_empresa.assert_called_once_with("99990000", "ruc", page=1)


class IntegracionNoConstaFormattingTests(TestCase):
    def test_construir_noconsta_entry_devuelve_redaccion_por_ruc(self):
        entry = construir_noconsta_entry("ruc", "9000000")

        self.assertEqual(entry["descripcion"], "RUC: 9000000")
        self.assertEqual(entry["frase_certificacion"], "asociado al siguiente RUC: 9000000")

    def test_construir_noconsta_entry_devuelve_redaccion_por_cedula(self):
        entry = construir_noconsta_entry("cedula", "8-123-456")

        self.assertEqual(entry["descripcion"], "Cédula: 8-123-456")
        self.assertEqual(entry["frase_certificacion"], "asociado a la siguiente cédula: 8-123-456")

    def test_normalizar_noconsta_entry_migra_string_legacy(self):
        entry = normalizar_noconsta_entry("razon social: HORUS ENTERPRISE")

        self.assertEqual(entry["campo"], "razon_social")
        self.assertEqual(entry["descripcion"], "Razón social: HORUS ENTERPRISE")
        self.assertEqual(
            entry["frase_certificacion"],
            "asociado a la siguiente razón social: HORUS ENTERPRISE",
        )


class IntegracionServiceFilterTests(TestCase):
    @patch("integracion.services.buscar_empresa_todas_paginas")
    def test_filtra_por_cedula_con_coincidencia_parcial_normalizada(self, mock_buscar_empresa_todas_paginas):
        mock_buscar_empresa_todas_paginas.return_value = [
            _mapear_campos({
                "numero_aviso": "111",
                "nombreComercial": "PRIMERA",
                "razon_social_juridica": "PRIMERA, S.A.",
                "razon_social_natural": "",
                "ruc": "111-1-111",
                "cedula_representante": "8-123-456",
                "representante_legal": "ANA",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 1,
            }),
            _mapear_campos({
                "numero_aviso": "222",
                "nombreComercial": "SEGUNDA",
                "razon_social_juridica": "SEGUNDA, S.A.",
                "razon_social_natural": "",
                "ruc": "222-1-222",
                "cedula_representante": "8-999-000",
                "representante_legal": "BETO",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 2,
            }),
        ]

        resultado = buscar_empresa_por_campo("8", "cedula", page=1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 2)
        self.assertEqual(resultado["avisos"][0]["cedula_representante"], "8-123-456")

    @patch("integracion.services.buscar_empresa_todas_paginas")
    def test_filtra_por_ruc_con_coincidencia_parcial_normalizada(self, mock_buscar_empresa_todas_paginas):
        mock_buscar_empresa_todas_paginas.return_value = [
            _mapear_campos({
                "numero_aviso": "111",
                "nombreComercial": "PRIMERA",
                "razon_social_juridica": "PRIMERA, S.A.",
                "razon_social_natural": "",
                "ruc": "645991-1-458971",
                "cedula_representante": "8-123-456",
                "representante_legal": "ANA",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 1,
            }),
            _mapear_campos({
                "numero_aviso": "222",
                "nombreComercial": "SEGUNDA",
                "razon_social_juridica": "SEGUNDA, S.A.",
                "razon_social_natural": "",
                "ruc": "22005-143-197211",
                "cedula_representante": "8-999-000",
                "representante_legal": "BETO",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 2,
            }),
        ]

        resultado = buscar_empresa_por_campo("645991", "ruc", page=1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 1)
        self.assertEqual(resultado["avisos"][0]["ruc_completo"], "645991-1-458971")

    @patch("integracion.services.api_consultar")
    def test_filtra_por_nombre_comercial_con_coincidencia_parcial_sin_acentos(self, mock_api_consultar):
        mock_api_consultar.return_value = {
            "resultados": [
                _mapear_campos({
                "numero_aviso": "333",
                "nombreComercial": "TECNOLOGÍA AVANZADA",
                "razon_social_juridica": "INVERSIONES DEL ISTMO, S.A.",
                "razon_social_natural": "",
                "ruc": "333-1-333",
                "cedula_representante": "8-444-555",
                "representante_legal": "CARLA",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 3,
                }),
                _mapear_campos({
                "numero_aviso": "444",
                "nombreComercial": "PANADERIA CENTRAL",
                "razon_social_juridica": "PANADERIA CENTRAL, S.A.",
                "razon_social_natural": "",
                "ruc": "444-1-444",
                "cedula_representante": "8-777-888",
                "representante_legal": "DARIO",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": 4,
                }),
            ],
            "paginacion": {
                "current_page": 1,
                "last_page": 1,
                "total": 2,
                "per_page": 10,
                "has_next": False,
                "has_previous": False,
            },
        }

        resultado = buscar_empresa_por_campo("tecnologia avanzada", "nombre_comercial", page=1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 1)
        self.assertEqual(resultado["avisos"][0]["razon_comercial"], "TECNOLOGÍA AVANZADA")

    @patch("integracion.services.api_consultar")
    def test_filtra_por_nombre_comercial_con_variacion_de_puntuacion_y_termino_sanitizado(self, mock_api_consultar):
        registro = _mapear_campos({
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
        })
        mock_api_consultar.side_effect = lambda busqueda, page=1: {
            ("EL TELAR SA", 1): {
                "resultados": [registro],
                "paginacion": {
                    "current_page": 1,
                    "last_page": 1,
                    "total": 1,
                    "per_page": 10,
                    "has_next": False,
                    "has_previous": False,
                },
            },
        }.get((busqueda, page))

        resultado = buscar_empresa_por_campo("EL TELAR , S.A.", "nombre_comercial", page=1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 1)
        self.assertEqual(resultado["avisos"][0]["ruc_completo"], "30486-2-239028")
        mock_api_consultar.assert_any_call("EL TELAR SA", page=1)

    @patch("integracion.services.api_consultar")
    def test_filtra_por_nombre_comercial_con_espacios_y_puntuacion_equivalentes(self, mock_api_consultar):
        registro = _mapear_campos({
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
            })
        mock_api_consultar.return_value = {
            "resultados": [registro],
            "paginacion": {
                "current_page": 1,
                "last_page": 1,
                "total": 1,
                "per_page": 10,
                "has_next": False,
                "has_previous": False,
            },
        }

        resultado = buscar_empresa_por_campo("EL TELAR , S.A.", "nombre_comercial", page=1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 1)
        self.assertEqual(resultado["avisos"][0]["razon_comercial"], "EL TELAR, S.A.")

    @patch("integracion.services.api_consultar")
    def test_paginar_localmente_resultados_filtrados(self, mock_api_consultar):
        mock_api_consultar.return_value = {
            "resultados": [
                _mapear_campos({
                "numero_aviso": f"500-{indice}",
                "nombreComercial": f"HORUS SHOP {indice}",
                "razon_social_juridica": f"HORUS ENTERPRISE {indice}",
                "razon_social_natural": "",
                "ruc": f"500-1-{indice:03d}",
                "cedula_representante": "8-000-111",
                "representante_legal": "HORUS REP",
                "estado": "Vigente",
                "tipo": "Juridico",
                "monto_estimado": 1000,
                "id_sucursal": indice,
                })
                for indice in range(1, 12)
            ],
            "paginacion": {
                "current_page": 1,
                "last_page": 1,
                "total": 11,
                "per_page": 10,
                "has_next": False,
                "has_previous": False,
            },
        }

        resultado = buscar_empresa_por_campo("horus", "razon_social", page=2)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["paginacion"]["total"], 11)
        self.assertEqual(resultado["paginacion"]["current_page"], 2)
        self.assertEqual(resultado["paginacion"]["last_page"], 2)
        self.assertTrue(resultado["paginacion"]["has_previous"])
        self.assertFalse(resultado["paginacion"]["has_next"])
        self.assertEqual(len(resultado["avisos"]), 1)
