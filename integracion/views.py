from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import Http404
from .services import buscar_empresa
from .adapters import normalizar_datos_empresa, construir_ubicacion_completa
from .api_client import consultar_empresa as api_consultar
from auditoria.services import registrar_evento, obtener_ip_cliente, registrar_consulta_secuencial
from auditoria.models import BitacoraEvento


@login_required
@require_http_methods(["GET", "POST"])
def api_search_view(request):
    """
    Endpoint HTMX para búsqueda de empresas.
    Devuelve fragmento HTML con tabla de avisos.
    """
    query = (request.GET.get('q', '') or request.GET.get('ruc_empresa', '') or
             request.POST.get('q', '')).strip()

    if not query:
        return render(request, 'integracion/resultados_vacios.html')

    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    resultado = buscar_empresa(query, page=page)

    # Registrar evento de consulta
    ip_cliente = obtener_ip_cliente(request)

    # Construir resumen de resultados para la consulta secuencial
    resultados_detalle = []
    num_resultados = 0
    if resultado and resultado.get('resultados_raw'):
        num_resultados = len(resultado['resultados_raw'])
        for raw in resultado['resultados_raw']:
            resultados_detalle.append({
                'numero_aviso': raw.get('aviso_operacion', ''),
                'razon_social': raw.get('razon_social', ''),
                'estatus': raw.get('estatus', ''),
            })

    # Registrar consulta secuencial
    consulta_seq = registrar_consulta_secuencial(
        consulta=query,
        usuario=request.user,
        ip_origen=ip_cliente,
        resultados_encontrados=num_resultados,
        resultados_detalle=resultados_detalle,
    )

    # Acumular IDs de consultas secuenciales en la sesión
    consultas_ids = request.session.get('consultas_secuencia_ids', [])
    consultas_ids.append(consulta_seq.numero)
    request.session['consultas_secuencia_ids'] = consultas_ids

    registrar_evento(
        tipo_evento=BitacoraEvento.CONSULTA_API,
        actor=request.user,
        ip_origen=ip_cliente,
        descripcion=f'Consulta de empresa por RUC: {query}',
        metadata={'query': query, 'encontrado': resultado is not None, 'consulta_secuencia': consulta_seq.numero}
    )

    if not resultado:
        return render(request, 'integracion/resultados_no_encontrados.html', {
            'query': query
        })

    # Guardar resultados raw en sesión para el modal de detalle
    request.session['ultimos_resultados_api'] = resultado['resultados_raw']

    # RUCs ya en carrito para toggle Agregar/Remover
    empresas_cart = request.session.get('empresas_cart', [])
    rucs_en_cart = {e.get('ruc_completo', '') for e in empresas_cart}

    return render(request, 'integracion/resultados_empresa.html', {
        'empresa': resultado['detalle'],
        'avisos': resultado['avisos'],
        'paginacion': resultado['paginacion'],
        'query': query,
        'rucs_en_cart': rucs_en_cart,
    })


@login_required
def detalle_empresa_hx(request, aviso):
    """
    Devuelve el contenido del modal para una empresa específica por aviso.
    """
    # Buscar primero en los resultados guardados en sesión
    resultados_api = request.session.get('ultimos_resultados_api', [])
    empresa_raw = next((e for e in resultados_api if e.get('aviso_operacion') == aviso), None)

    # Fallback: consultar la API directamente
    if not empresa_raw:
        respuesta = api_consultar(aviso)
        if respuesta:
            resultados = respuesta['resultados']
            empresa_raw = next((e for e in resultados if e.get('aviso_operacion') == aviso), resultados[0])

    if not empresa_raw:
        raise Http404("Empresa no encontrada")

    empresa = normalizar_datos_empresa(empresa_raw)
    empresa['ubicacion_completa'] = construir_ubicacion_completa(empresa)

    return render(request, 'integracion/partials/modal_detalle.html', {
        'empresa': empresa
    })
