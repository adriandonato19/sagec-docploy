from django.urls import path
from . import views

app_name = 'tramites'

urlpatterns = [
    path('solicitudes/', views.bandeja_admin_view, name='bandeja_admin'),
    path('certificados/', views.mis_certificados_view, name='mis_certificados'),
    path('oficios/', views.mis_oficios_view, name='mis_oficios'),
    path('<uuid:id>/', views.detalle_view, name='detalle'),
    path('<uuid:id>/aprobar/', views.aprobar_view, name='aprobar'),
    path('<uuid:id>/aprobar-pdf/', views.aprobar_pdf_view, name='aprobar_pdf'),
    path('<uuid:id>/rechazar/', views.rechazar_view, name='rechazar'),
    path('<uuid:id>/regresar/', views.regresar_view, name='regresar'),
    path('<uuid:id>/firmar/', views.firmar_view, name='firmar'),
    path('<uuid:id>/editar-pdf/', views.editar_pdf_view, name='editar_pdf'),
    path('<uuid:id>/pdf/', views.descargar_view, name='descargar'),
    path('hx/vista-previa/<uuid:id>/', views.vista_previa_pdf_hx, name='vista_previa_pdf'),
    path('<uuid:id>/hx/responder-preguntas/', views.responder_preguntas_hx, name='responder_preguntas_hx'),
    path('<uuid:id>/hx/responder-solicitud/', views.responder_solicitud_hx, name='responder_solicitud_hx'),
    path('hx/agregar-empresa/', views.agregar_empresa_hx, name='agregar_empresa_hx'),
    path('hx/agregar-empresa-desde-resultado/', views.agregar_empresa_desde_resultado_hx, name='agregar_empresa_desde_resultado_hx'),
    path('hx/remover-empresa/<int:index>/', views.remover_empresa_hx, name='remover_empresa_hx'),
    path('hx/remover-empresa-ruc/', views.remover_empresa_por_ruc_hx, name='remover_empresa_por_ruc_hx'),
    path('hx/remover-noconsta/<int:index>/', views.remover_noconsta_hx, name='remover_noconsta_hx'),
]
