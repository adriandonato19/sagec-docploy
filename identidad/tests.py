from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.core.management import CommandError, call_command
from django.http import HttpResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import Resolver404, resolve, reverse

from auditoria.models import BitacoraEvento

from .forms import DirectorManagedUserUpdateForm
from .middleware import ForcePasswordChangeMiddleware
from .models import UsuarioMICI
from .views import lista_usuarios_view


class IdentidadTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def crear_usuario(self, **overrides):
        defaults = {
            "username": "usuario_base",
            "email": "base@example.gob.pa",
            "password": "ClaveSegura!2026",
            "cedula": "8-000-1000",
            "rol": UsuarioMICI.FISCAL,
            "first_name": "Usuario",
            "last_name": "Base",
            "institucion": "MICI",
            "debe_cambiar_password": False,
            "is_active": True,
        }
        defaults.update(overrides)
        password = defaults.pop("password")
        user = UsuarioMICI.objects.create_user(password=password, **defaults)
        return user

    def preparar_request(self, request, user):
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = user
        setattr(request, "_messages", FallbackStorage(request))
        return request


class RegistroPublicoTests(IdentidadTestCase):
    def test_registro_publico_desaparece_y_login_no_muestra_enlace(self):
        with self.assertRaises(Resolver404):
            resolve("/registro/")

        login_template = Path("identidad/templates/identidad/login.html").read_text(encoding="utf-8")
        self.assertNotIn("Regístrate", login_template)

    def test_raiz_redirige_a_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("identidad:login"))


class RootRedirectAuthenticatedTests(IdentidadTestCase):
    def setUp(self):
        super().setUp()
        self.director = self.crear_usuario(
            username="director_root",
            email="director.root@mici.gob.pa",
            cedula="8-000-0099",
            rol=UsuarioMICI.DIRECTOR,
        )

    def test_raiz_con_sesion_activa_termina_en_destino_post_login(self):
        self.client.force_login(self.director)

        response = self.client.get("/")
        login_response = self.client.get(reverse("identidad:login"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("identidad:login"))
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.headers["Location"], reverse("tramites:bandeja_admin"))


class CrearDirectorCommandTests(IdentidadTestCase):
    @patch("identidad.management.commands.crear_director.getpass")
    @patch("identidad.management.commands.crear_director.input")
    def test_crea_unico_director(self, mock_input, mock_getpass):
        mock_input.side_effect = ["director", "director@mici.gob.pa", "8-000-0001"]
        mock_getpass.side_effect = ["ClaveDirector!2026", "ClaveDirector!2026"]

        output = StringIO()
        call_command("crear_director", stdout=output)

        director = UsuarioMICI.objects.get(username="director")
        self.assertEqual(director.rol, UsuarioMICI.DIRECTOR)
        self.assertTrue(director.is_staff)
        self.assertTrue(director.is_active)
        self.assertFalse(director.debe_cambiar_password)

    @patch("identidad.management.commands.crear_director.getpass")
    @patch("identidad.management.commands.crear_director.input")
    def test_falla_si_ya_existe_director(self, mock_input, mock_getpass):
        self.crear_usuario(
            username="director_actual",
            email="director.actual@mici.gob.pa",
            cedula="8-000-0009",
            rol=UsuarioMICI.DIRECTOR,
        )
        mock_input.side_effect = ["otro", "otro@mici.gob.pa", "8-000-0010"]
        mock_getpass.side_effect = ["OtraClave!2026", "OtraClave!2026"]

        with self.assertRaises(CommandError):
            call_command("crear_director")


class GestionUsuariosTests(IdentidadTestCase):
    def setUp(self):
        super().setUp()
        self.director = self.crear_usuario(
            username="director",
            email="director@mici.gob.pa",
            cedula="8-000-0002",
            rol=UsuarioMICI.DIRECTOR,
        )
        self.trabajador = self.crear_usuario(
            username="trabajador",
            email="trabajador@mici.gob.pa",
            cedula="8-000-0003",
            rol=UsuarioMICI.TRABAJADOR,
        )
        self.fiscal = self.crear_usuario(
            username="fiscal",
            email="fiscal@mp.gob.pa",
            cedula="8-000-0004",
            rol=UsuarioMICI.FISCAL,
        )

    def test_director_crea_usuario_gestionable_y_audita(self):
        self.client.force_login(self.director)

        response = self.client.post(
            reverse("identidad:crear_usuario"),
            {
                "username": "nuevo_trabajador",
                "email": "nuevo.trabajador@mici.gob.pa",
                "first_name": "Nuevo",
                "last_name": "Trabajador",
                "cedula": "8-000-0011",
                "institucion": "MICI",
                "rol": UsuarioMICI.TRABAJADOR,
                "password": "ClaveTemporal!2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("identidad:lista_usuarios"))
        usuario = UsuarioMICI.objects.get(username="nuevo_trabajador")
        self.assertTrue(usuario.debe_cambiar_password)
        self.assertEqual(
            BitacoraEvento.objects.filter(tipo_evento=BitacoraEvento.GESTION_USUARIO, object_id=usuario.pk).count(),
            1,
        )

    def test_no_director_recibe_403_en_panel(self):
        request = self.preparar_request(
            self.factory.get(reverse("identidad:lista_usuarios")),
            self.trabajador,
        )

        with self.assertRaises(PermissionDenied):
            lista_usuarios_view(request)

    def test_edicion_no_permite_promover_a_director(self):
        form = DirectorManagedUserUpdateForm(
            instance=self.trabajador,
            data={
                "email": self.trabajador.email,
                "first_name": self.trabajador.first_name,
                "last_name": self.trabajador.last_name,
                "institucion": self.trabajador.institucion,
                "rol": UsuarioMICI.DIRECTOR,
            },
        )

        self.assertFalse(form.is_valid())
        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.rol, UsuarioMICI.TRABAJADOR)

    def test_toggle_activo_desactiva_y_bloquea_login(self):
        self.client.force_login(self.director)
        response = self.client.post(reverse("identidad:toggle_activo", args=[self.fiscal.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("identidad:lista_usuarios"))
        self.fiscal.refresh_from_db()
        self.assertFalse(self.fiscal.is_active)
        self.assertIsNone(authenticate(username=self.fiscal.username, password="ClaveSegura!2026"))


class PasswordTemporalTests(IdentidadTestCase):
    def setUp(self):
        super().setUp()
        self.usuario = self.crear_usuario(
            username="temporal",
            email="temporal@mici.gob.pa",
            cedula="8-000-0012",
            rol=UsuarioMICI.FISCAL,
            password="Temporal!2026",
            debe_cambiar_password=True,
        )

    def test_primer_login_redirige_a_perfil_y_exige_cambio(self):
        response = self.client.post(
            reverse("identidad:login"),
            {"username": self.usuario.username, "password": "Temporal!2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("identidad:perfil"))

        request = self.factory.get(reverse("consultar_tramite"))
        request.user = self.usuario
        middleware = ForcePasswordChangeMiddleware(lambda req: HttpResponse("ok"))
        bloqueo = middleware(request)
        self.assertEqual(bloqueo.status_code, 302)
        self.assertEqual(bloqueo.headers["Location"], reverse("identidad:perfil"))

        cambio = self.client.post(
            reverse("identidad:perfil"),
            {
                "cambiar_password": "1",
                "password_actual": "Temporal!2026",
                "password_nueva": "NuevaClaveSegura!2026",
                "password_confirmar": "NuevaClaveSegura!2026",
            },
        )
        self.assertEqual(cambio.status_code, 302)
        self.assertEqual(cambio.headers["Location"], reverse("identidad:perfil"))

        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.debe_cambiar_password)

        request = self.factory.get(reverse("consultar_tramite"))
        request.user = self.usuario
        acceso = middleware(request)
        self.assertEqual(acceso.status_code, 200)
