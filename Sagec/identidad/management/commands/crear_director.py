from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from identidad.models import UsuarioMICI


class Command(BaseCommand):
    help = "Crea el único usuario DIRECTOR permitido por el sistema."

    def handle(self, *args, **options):
        if UsuarioMICI.objects.filter(rol=UsuarioMICI.DIRECTOR).exists():
            raise CommandError("Ya existe un usuario con rol DIRECTOR. No se permiten directores adicionales.")

        username = self._prompt("Username")
        email = self._prompt("Email")
        cedula = self._prompt("Cédula")
        password = self._prompt_password()

        if UsuarioMICI.objects.filter(username__iexact=username).exists():
            raise CommandError("El nombre de usuario ya existe.")
        if UsuarioMICI.objects.filter(email__iexact=email).exists():
            raise CommandError("El correo electrónico ya existe.")
        if UsuarioMICI.objects.filter(cedula__iexact=cedula).exists():
            raise CommandError("La cédula ya existe.")

        user = UsuarioMICI(
            username=username,
            email=email.lower(),
            cedula=cedula,
            rol=UsuarioMICI.DIRECTOR,
            is_staff=True,
            is_active=True,
            debe_cambiar_password=False,
        )

        validate_password(password, user)
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"DIRECTOR creado correctamente: {user.username}"))

    def _prompt(self, label):
        value = input(f"{label}: ").strip()
        if not value:
            raise CommandError(f"{label} es obligatorio.")
        return value

    def _prompt_password(self):
        password = getpass("Password: ")
        confirm_password = getpass("Confirm Password: ")
        if not password:
            raise CommandError("La contraseña es obligatoria.")
        if password != confirm_password:
            raise CommandError("Las contraseñas no coinciden.")
        return password
