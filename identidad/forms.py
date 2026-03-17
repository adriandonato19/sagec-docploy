from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import UsuarioMICI


MANAGED_ROLE_CHOICES = [
    (UsuarioMICI.FISCAL, "Fiscal / Organismo Externo"),
    (UsuarioMICI.TRABAJADOR, "Trabajador MICI"),
]


class _BaseManagedUserForm(forms.ModelForm):
    class Meta:
        model = UsuarioMICI
        fields = ["email", "first_name", "last_name", "institucion", "rol"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["rol"].choices = MANAGED_ROLE_CHOICES

        text_fields = ("email", "first_name", "last_name", "institucion")
        for field_name in text_fields:
            self.fields[field_name].widget.attrs.update(
                {
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
                }
            )

        self.fields["rol"].widget.attrs.update(
            {
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            }
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        queryset = UsuarioMICI.objects.filter(email__iexact=email)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo electrónico.")
        return email

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        if rol not in {UsuarioMICI.FISCAL, UsuarioMICI.TRABAJADOR}:
            raise forms.ValidationError("Solo se permite gestionar usuarios FISCAL o TRABAJADOR.")
        return rol


class DirectorManagedUserCreateForm(_BaseManagedUserForm):
    password = forms.CharField(
        label="Contraseña temporal",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            }
        ),
        help_text="Debe cumplir la política institucional y se cambiará en el primer inicio de sesión.",
    )

    class Meta(_BaseManagedUserForm.Meta):
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "cedula",
            "institucion",
            "rol",
            "password",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            }
        )
        self.fields["cedula"].widget.attrs.update(
            {
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            }
        )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if UsuarioMICI.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("El nombre de usuario ya existe.")
        return username

    def clean_cedula(self):
        cedula = self.cleaned_data["cedula"].strip()
        if UsuarioMICI.objects.filter(cedula__iexact=cedula).exists():
            raise forms.ValidationError("Ya existe un usuario con esa cédula.")
        return cedula

    def clean_password(self):
        password = self.cleaned_data["password"]
        provisional_user = UsuarioMICI(
            username=self.cleaned_data.get("username", ""),
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
        )
        validate_password(password, provisional_user)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.debe_cambiar_password = True
        user.is_active = True
        user.is_staff = False
        if commit:
            user.save()
        return user


class DirectorManagedUserUpdateForm(_BaseManagedUserForm):
    class Meta(_BaseManagedUserForm.Meta):
        fields = ["email", "first_name", "last_name", "institucion", "rol"]
