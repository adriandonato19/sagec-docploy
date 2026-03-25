"""
Servicio de integración con API de Panamá Emprende.

$Reusable$
"""
import logging
from typing import Optional, Dict, List

from .api_client import consultar_empresa as api_consultar
from .adapters import normalizar_datos_empresa, construir_ubicacion_completa, normalizar_lista_avisos

logger = logging.getLogger(__name__)


def buscar_empresa(query: str, page: int = 1) -> Optional[Dict]:
    """
    Busca una empresa por RUC, cédula, nombre comercial o razón social.

    Args:
        query: Término de búsqueda
        page: Número de página para la API

    Returns:
        Diccionario con 'detalle', 'avisos', 'resultados_raw' y 'paginacion', o None si no se encuentra

    $Reusable$
    """
    respuesta = api_consultar(query, page=page)

    if not respuesta:
        return None

    resultados = respuesta['resultados']

    # Normalizar datos usando adapters
    detalle_normalizado = normalizar_datos_empresa(resultados[0])
    detalle_normalizado['ubicacion_completa'] = construir_ubicacion_completa(detalle_normalizado)

    avisos_normalizados = normalizar_lista_avisos(resultados)

    return {
        'detalle': detalle_normalizado,
        'avisos': avisos_normalizados,
        'resultados_raw': resultados,
        'paginacion': respuesta['paginacion'],
    }


MAX_PAGINAS_CARRITO = 10


def buscar_empresa_todas_paginas(query: str) -> Optional[List[Dict]]:
    """
    Busca empresa y retorna todos los resultados raw de todas las páginas.

    Usado para agregar al carrito donde se necesitan todos los avisos.
    Límite de seguridad: máximo MAX_PAGINAS_CARRITO páginas.
    """
    primera = api_consultar(query, page=1)
    if not primera:
        return None

    todos = list(primera['resultados'])
    last_page = primera['paginacion']['last_page']

    for page in range(2, min(last_page + 1, MAX_PAGINAS_CARRITO + 1)):
        respuesta = api_consultar(query, page=page)
        if not respuesta:
            break
        todos.extend(respuesta['resultados'])

    return todos
