"""
Decoradores reutilizables para control de acceso basado en roles.

$Reusable$
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def require_rol(*roles_requeridos):
    """
    Decorador que verifica que el usuario tenga uno de los roles especificados.
    
    Uso:
        @require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
        def mi_vista(request):
            ...
    
    $Reusable$
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Debe iniciar sesión para acceder a esta página.')
                return redirect('identidad:login')
            
            if not hasattr(request.user, 'rol'):
                messages.error(request, 'Usuario sin rol asignado.')
                raise PermissionDenied
            
            if request.user.rol not in roles_requeridos:
                messages.error(request, 'No tiene permisos para acceder a esta página.')
                raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_autenticado(view_func):
    """
    Decorador simple que verifica autenticación.
    
    $Reusable$
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Debe iniciar sesión para acceder a esta página.')
            return redirect('identidad:login')
        return view_func(request, *args, **kwargs)
    return wrapper

