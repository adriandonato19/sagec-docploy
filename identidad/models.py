from django.contrib.auth.models import AbstractUser
from django.db import models


class UsuarioMICI(AbstractUser):
    # Definición de Roles como constantes para evitar errores de dedo
    FISCAL = 'FISCAL'      # Organismos gubernamentales externos
    TRABAJADOR = 'TRABAJADOR'  # Funcionario MICI operativo
    DIRECTOR = 'DIRECTOR'    # Autoridad con poder de firma
    
    ROLES_CHOICES = [
        (FISCAL, 'Fiscal / Organismo Externo'),
        (TRABAJADOR, 'Trabajador MICI'),
        (DIRECTOR, 'Director / Firmante'),
    ]

    rol = models.CharField(
        max_length=20, 
        choices=ROLES_CHOICES, 
        default=FISCAL
    )
    cedula = models.CharField(max_length=20, unique=True, help_text="Cédula de identidad personal")
    institucion = models.CharField(max_length=100, blank=True, help_text="Entidad a la que pertenece (ej. Ministerio Público)")
    debe_cambiar_password = models.BooleanField(
        default=False,
        help_text="Obliga al usuario a cambiar su contraseña en el siguiente inicio de sesión.",
    )

    class Meta:
        verbose_name = "Usuario MICI"
        verbose_name_plural = "Usuarios MICI"

    # Métodos de ayuda para la lógica de negocio (Scream Architecture)
    @property
    def puede_solicitar(self):
        # Todos los roles pueden solicitar [cite: 1, 2, 3]
        return True

    @property
    def puede_aprobar(self):
        # Solo trabajadores y directores aprueban [cite: 2, 3]
        return self.rol in [self.TRABAJADOR, self.DIRECTOR]

    @property
    def puede_firmar(self):
        # Solo el director tiene permiso de firma final 
        return self.rol == self.DIRECTOR

    def __str__(self):
        return f"{self.get_full_name()} ({self.rol})"
