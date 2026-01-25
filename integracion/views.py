from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, Http404
from .services import buscar_empresa
from .mock_data import MOCK_EMPRESAS_API
from .adapters import normalizar_datos_empresa, construir_ubicacion_completa
from auditoria.services import registrar_evento, obtener_ip_cliente
from auditoria.models import BitacoraEvento


@login_required
def buscador_view(request):
    """Vista principal del buscador de empresas."""
    return render(request, 'integracion/buscador.html')


@login_required
@require_http_methods(["GET", "POST"])
def api_search_view(request):
    """
    Endpoint HTMX para búsqueda de empresas.
    Devuelve fragmento HTML con tabla de avisos.
    """
    query = request.GET.get('q', '').strip() or request.POST.get('q', '').strip()
    
    if not query:
        return render(request, 'integracion/resultados_vacios.html')
    
    resultado = buscar_empresa(query)
    
    # Registrar evento de consulta
    ip_cliente = obtener_ip_cliente(request)
    registrar_evento(
        tipo_evento=BitacoraEvento.CONSULTA_API,
        actor=request.user,
        ip_origen=ip_cliente,
        descripcion=f'Consulta de empresa por RUC: {query}',
        metadata={'query': query, 'encontrado': resultado is not None}
    )
    
    if not resultado:
        return render(request, 'integracion/resultados_no_encontrados.html', {
            'query': query
        })
    
    return render(request, 'integracion/resultados_empresa.html', {
        'empresa': resultado['detalle'],
        'avisos': resultado['avisos'],
        'query': query,
    })


@login_required
def detalle_empresa_hx(request, aviso):
    """
    Devuelve el contenido del modal para una empresa específica por aviso.
    """
    empresa_raw = next((e for e in MOCK_EMPRESAS_API if e['aviso_operacion'] == aviso), None)
    
    if not empresa_raw:
        raise Http404("Empresa no encontrada")
        
    empresa = normalizar_datos_empresa(empresa_raw)
    empresa['ubicacion_completa'] = construir_ubicacion_completa(empresa)
    
    return render(request, 'integracion/partials/modal_detalle.html', {
        'empresa': empresa
    })
