"""
URL configuration for SAGEC (MICI).

Mapea las rutas según ROUTES.MD siguiendo la arquitectura Scream Architecture.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Módulo de Identidad (/auth/)
    path('', include('identidad.urls')),
    
    # Módulo de Integración (/consultas/)
    path('', include('integracion.urls')),
    
    # Módulo de Trámites (/tramites/)
    path('tramites/', include('tramites.urls')),
]
