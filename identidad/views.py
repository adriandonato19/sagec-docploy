from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .decorators import require_autenticado
from .models import UsuarioMICI
from auditoria.services import registrar_evento, obtener_ip_cliente
from auditoria.models import BitacoraEvento


@require_http_methods(["GET", "POST"])
def register_view(request):
    """Vista de registro para propósitos de testeo."""
    if request.user.is_authenticated:
        return redirect('tramites:bandeja_admin')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        rol = request.POST.get('rol', UsuarioMICI.FISCAL)
        cedula = request.POST.get('cedula')
        institucion = request.POST.get('institucion')
        
        if not username or not password or not cedula:
            messages.error(request, 'Usuario, contraseña y cédula son obligatorios.')
            return render(request, 'identidad/register.html')
        
        if UsuarioMICI.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe.')
            return render(request, 'identidad/register.html')
            
        try:
            user = UsuarioMICI.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                rol=rol,
                cedula=cedula,
                institucion=institucion
            )
            messages.success(request, 'Usuario creado exitosamente. Ahora puede iniciar sesión.')
            return redirect('identidad:login')
        except Exception as e:
            messages.error(request, f'Error al crear el usuario: {str(e)}')
            
    return render(request, 'identidad/register.html', {
        'roles': UsuarioMICI.ROLES_CHOICES
    })


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Vista de login con soporte para Axes (protección contra fuerza bruta)."""
    # ... (rest of the code)
    if request.user.is_authenticated:
        return redirect('tramites:bandeja_admin')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Por favor ingrese usuario y contraseña.')
            return render(request, 'identidad/login.html')
        
        # Validar dominio .gob.pa si es necesario (puede ser opcional en desarrollo)
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenido, {user.get_full_name() or user.username}')
            
            # Registrar evento de login
            ip_cliente = obtener_ip_cliente(request)
            registrar_evento(
                tipo_evento=BitacoraEvento.LOGIN,
                actor=user,
                ip_origen=ip_cliente,
                descripcion=f'Inicio de sesión exitoso - Rol: {user.get_rol_display()}'
            )
            
            # Redirigir según rol
            if user.rol == UsuarioMICI.DIRECTOR:
                return redirect('tramites:bandeja_admin')
            elif user.rol == UsuarioMICI.TRABAJADOR:
                return redirect('tramites:bandeja_admin')
            else:  # FISCAL
                return redirect('consultar_tramite')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    
    return render(request, 'identidad/login.html')


@require_autenticado
@require_http_methods(["POST"])
def logout_view(request):
    """Vista de logout."""
    # Registrar evento antes de cerrar sesión
    ip_cliente = obtener_ip_cliente(request)
    registrar_evento(
        tipo_evento=BitacoraEvento.LOGOUT,
        actor=request.user,
        ip_origen=ip_cliente,
        descripcion='Cierre de sesión'
    )
    
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('identidad:login')


@require_autenticado
def perfil_view(request):
    """Vista de perfil para editar datos y cambiar contraseña."""
    if request.method == 'POST':
        # Cambio de contraseña
        if 'cambiar_password' in request.POST:
            password_actual = request.POST.get('password_actual')
            password_nueva = request.POST.get('password_nueva')
            password_confirmar = request.POST.get('password_confirmar')
            
            if not request.user.check_password(password_actual):
                messages.error(request, 'La contraseña actual es incorrecta.')
            elif password_nueva != password_confirmar:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
            elif len(password_nueva) < 12:
                messages.error(request, 'La contraseña debe tener al menos 12 caracteres.')
            else:
                request.user.set_password(password_nueva)
                request.user.save()
                messages.success(request, 'Contraseña actualizada correctamente.')
                return redirect('identidad:perfil')
        
        # Edición de datos básicos
        elif 'editar_datos' in request.POST:
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.email = request.POST.get('email', '')
            request.user.save()
            messages.success(request, 'Datos actualizados correctamente.')
            return redirect('identidad:perfil')
    
    return render(request, 'identidad/perfil.html', {
        'usuario': request.user
    })
