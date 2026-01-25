from django.urls import path
from . import views

app_name = 'integracion'

urlpatterns = [
    path('consultar/', views.buscador_view, name='buscador'),
    path('hx/buscar-empresa/', views.api_search_view, name='api_search'),
    path('hx/detalle-empresa/<str:aviso>/', views.detalle_empresa_hx, name='detalle_empresa_hx'),
]
