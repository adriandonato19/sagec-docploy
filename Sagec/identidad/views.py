from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from auditoria.models import BitacoraEvento
from auditoria.services import obtener_ip_cliente, registrar_evento, registrar_gestion_usuario

from .decorators import require_autenticado, require_rol
from .forms import DirectorManagedUserCreateForm, DirectorManagedUserUpdateForm
from .models import UsuarioMICI


def _redirect_post_login(user):
    if user.debe_cambiar_password:
        return redirect("identidad:perfil")
    if user.rol in {UsuarioMICI.DIRECTOR, UsuarioMICI.TRABAJADOR}:
        return redirect("tramites:bandeja_admin")
    return redirect("consultar_tramite")


def _agregar_errores_formulario(request, form):
    for field_errors in form.errors.values():
        for error in field_errors:
            messages.error(request, error)


def _usuario_gestionable(user_id):
    return get_object_or_404(UsuarioMICI.objects.exclude(rol=UsuarioMICI.DIRECTOR), pk=user_id)


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Vista de login con soporte para Axes (protección contra fuerza bruta)."""
    if request.user.is_authenticated:
        return _redirect_post_login(request.user)

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            messages.error(request, "Por favor ingrese usuario y contraseña.")
            return render(request, "identidad/login.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenido, {user.get_full_name() or user.username}")

            registrar_evento(
                tipo_evento=BitacoraEvento.LOGIN,
                actor=user,
                ip_origen=obtener_ip_cliente(request),
                descripcion=f"Inicio de sesión exitoso - Rol: {user.get_rol_display()}",
            )

            if user.debe_cambiar_password:
                messages.warning(request, "Debe cambiar su contraseña temporal antes de continuar.")
            return _redirect_post_login(user)

        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "identidad/login.html")


@require_autenticado
@require_http_methods(["POST"])
def logout_view(request):
    """Vista de logout."""
    registrar_evento(
        tipo_evento=BitacoraEvento.LOGOUT,
        actor=request.user,
        ip_origen=obtener_ip_cliente(request),
        descripcion="Cierre de sesión",
    )

    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("identidad:login")


@require_autenticado
def perfil_view(request):
    """Vista de perfil para editar datos y cambiar contraseña."""
    if request.method == "POST":
        if "cambiar_password" in request.POST:
            password_actual = request.POST.get("password_actual", "")
            password_nueva = request.POST.get("password_nueva", "")
            password_confirmar = request.POST.get("password_confirmar", "")

            if not request.user.check_password(password_actual):
                messages.error(request, "La contraseña actual es incorrecta.")
            elif password_nueva != password_confirmar:
                messages.error(request, "Las contraseñas nuevas no coinciden.")
            else:
                try:
                    validate_password(password_nueva, request.user)
                except ValidationError as exc:
                    for error in exc.messages:
                        messages.error(request, error)
                else:
                    request.user.set_password(password_nueva)
                    request.user.debe_cambiar_password = False
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, "Contraseña actualizada correctamente.")
                    return redirect("identidad:perfil")

        elif "editar_datos" in request.POST:
            email = request.POST.get("email", "").strip().lower()
            if not email:
                messages.error(request, "El correo electrónico es obligatorio.")
            elif UsuarioMICI.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                messages.error(request, "Ya existe un usuario con ese correo electrónico.")
            else:
                request.user.first_name = request.POST.get("first_name", "").strip()
                request.user.last_name = request.POST.get("last_name", "").strip()
                request.user.email = email
                request.user.save(update_fields=["first_name", "last_name", "email"])
                messages.success(request, "Datos actualizados correctamente.")
                return redirect("identidad:perfil")

    return render(
        request,
        "identidad/perfil.html",
        {
            "usuario": request.user,
            "forzar_cambio_password": request.user.debe_cambiar_password,
        },
    )


@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET"])
def lista_usuarios_view(request):
    usuarios = UsuarioMICI.objects.exclude(rol=UsuarioMICI.DIRECTOR).order_by("-date_joined")
    return render(request, "identidad/usuarios/lista.html", {"usuarios": usuarios})


@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def crear_usuario_view(request):
    form = DirectorManagedUserCreateForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            usuario = form.save()
            registrar_gestion_usuario(
                actor=request.user,
                objetivo=usuario,
                ip_origen=obtener_ip_cliente(request),
                accion="crear",
                descripcion=f"Usuario {usuario.username} creado por director.",
                metadata={
                    "username": usuario.username,
                    "rol": usuario.rol,
                    "is_active": usuario.is_active,
                },
            )
            messages.success(request, f"Usuario {usuario.username} creado correctamente.")
            return redirect("identidad:lista_usuarios")

        _agregar_errores_formulario(request, form)

    return render(request, "identidad/usuarios/crear.html", {"form": form})


@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def editar_usuario_view(request, user_id):
    usuario_objetivo = _usuario_gestionable(user_id)
    valores_anteriores = {
        "email": usuario_objetivo.email,
        "rol": usuario_objetivo.rol,
        "first_name": usuario_objetivo.first_name,
        "last_name": usuario_objetivo.last_name,
        "institucion": usuario_objetivo.institucion,
    }
    form = DirectorManagedUserUpdateForm(request.POST or None, instance=usuario_objetivo)

    if request.method == "POST":
        if form.is_valid():
            usuario = form.save()
            registrar_gestion_usuario(
                actor=request.user,
                objetivo=usuario,
                ip_origen=obtener_ip_cliente(request),
                accion="editar",
                descripcion=f"Usuario {usuario.username} actualizado por director.",
                metadata={
                    "antes": valores_anteriores,
                    "despues": {
                        "email": usuario.email,
                        "rol": usuario.rol,
                        "first_name": usuario.first_name,
                        "last_name": usuario.last_name,
                        "institucion": usuario.institucion,
                    },
                },
            )
            messages.success(request, f"Usuario {usuario.username} actualizado correctamente.")
            return redirect("identidad:lista_usuarios")

        _agregar_errores_formulario(request, form)

    return render(
        request,
        "identidad/usuarios/editar.html",
        {"form": form, "usuario_objetivo": usuario_objetivo},
    )


@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def toggle_activo_view(request, user_id):
    usuario_objetivo = _usuario_gestionable(user_id)

    if usuario_objetivo.pk == request.user.pk:
        messages.error(request, "No puede desactivarse a sí mismo.")
        return redirect("identidad:lista_usuarios")

    estado_anterior = usuario_objetivo.is_active
    usuario_objetivo.is_active = not usuario_objetivo.is_active
    usuario_objetivo.save(update_fields=["is_active"])

    accion = "activar" if usuario_objetivo.is_active else "desactivar"
    registrar_gestion_usuario(
        actor=request.user,
        objetivo=usuario_objetivo,
        ip_origen=obtener_ip_cliente(request),
        accion=accion,
        descripcion=f'Usuario {usuario_objetivo.username} marcado como {"activo" if usuario_objetivo.is_active else "inactivo"}.',
        metadata={
            "estado_anterior": estado_anterior,
            "estado_nuevo": usuario_objetivo.is_active,
        },
    )

    messages.success(
        request,
        f'Usuario {usuario_objetivo.username} {"activado" if usuario_objetivo.is_active else "desactivado"} correctamente.',
    )
    return redirect("identidad:lista_usuarios")
