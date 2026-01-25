from django.urls import path
from . import views

app_name = 'tramites'

urlpatterns = [
    path('crear/', views.crear_tramite_view, name='crear'),
    path('solicitudes/', views.bandeja_admin_view, name='bandeja_admin'),
    path('certificados/', views.mis_certificados_view, name='mis_certificados'),
    path('oficios/', views.mis_oficios_view, name='mis_oficios'),
    path('<uuid:id>/', views.detalle_view, name='detalle'),
    path('<uuid:id>/aprobar/', views.aprobar_view, name='aprobar'),
    path('<uuid:id>/firmar/', views.firmar_view, name='firmar'),
    path('<uuid:id>/pdf/', views.descargar_view, name='descargar'),
    path('hx/vista-previa/<uuid:id>/', views.vista_previa_pdf_hx, name='vista_previa_pdf'),
]

