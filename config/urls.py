"""
URL configuration for SAGEC (MICI).

Mapea las rutas según ROUTES.MD siguiendo la arquitectura Scream Architecture.
"""
from django.contrib import admin
from django.urls import path, include
from tramites.views import crear_tramite_view, formulario_tipo_hx

urlpatterns = [
    path('admin/', admin.site.urls),

    # Módulo de Identidad (/auth/)
    path('', include('identidad.urls')),

    # Módulo de Integración (HTMX endpoints)
    path('', include('integracion.urls')),

    # Página principal: Crear Trámite
    path('consultar/', crear_tramite_view, name='consultar_tramite'),
    path('hx/formulario-tipo/', formulario_tipo_hx, name='formulario_tipo_hx'),

    # Módulo de Trámites (/tramites/)
    path('tramites/', include('tramites.urls')),
]
