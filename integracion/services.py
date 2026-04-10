"""
Servicio de integración con API de Panamá Emprende.

$Reusable$
"""
import logging
import math
import re
import unicodedata
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
BUSQUEDA_FIELDS = {
    'ruc': 'RUC',
    'cedula': 'Cédula',
    'nombre_comercial': 'Nombre comercial',
    'razon_social': 'Razón social',
}
BUSQUEDA_FIELDS_NOCONSTA = {
    'ruc': {
        'descripcion': 'RUC',
        'frase': 'asociado al siguiente RUC',
    },
    'cedula': {
        'descripcion': 'Cédula',
        'frase': 'asociado a la siguiente cédula',
    },
    'nombre_comercial': {
        'descripcion': 'Nombre comercial',
        'frase': 'asociado al siguiente nombre comercial',
    },
    'razon_social': {
        'descripcion': 'Razón social',
        'frase': 'asociado a la siguiente razón social',
    },
}
BUSQUEDA_FIELDS_NOCONSTA_LOOKUP = {
    _normalizado: campo
    for campo, _normalizado in {
        'ruc': 'ruc',
        'cedula': 'cedula',
        'nombre_comercial': 'nombre comercial',
        'razon_social': 'razon social',
    }.items()
}
BUSQUEDA_PAGE_SIZE = 10
SUFIJOS_SOCIETARIOS = {
    'sa', 'sde rl', 's de rl', 'srl', 'inc', 'corp', 'corporation', 'llc', 'ltd',
}


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


def campo_busqueda_valido(campo: str) -> str:
    """Retorna un campo de búsqueda permitido o el default."""
    campo_normalizado = str(campo or '').strip().lower()
    return campo_normalizado if campo_normalizado in BUSQUEDA_FIELDS else 'ruc'


def etiqueta_campo_busqueda(campo: str) -> str:
    """Devuelve la etiqueta legible del campo de búsqueda."""
    return BUSQUEDA_FIELDS[campo_busqueda_valido(campo)]


def construir_noconsta_entry(campo: str, query: str) -> Dict[str, str]:
    """Construye una entrada estructurada de No Consta."""
    campo = campo_busqueda_valido(campo)
    valor = str(query or '').strip()
    metadata = BUSQUEDA_FIELDS_NOCONSTA[campo]
    return {
        'campo': campo,
        'valor': valor,
        'descripcion': f"{metadata['descripcion']}: {valor}",
        'frase_certificacion': f"{metadata['frase']}: {valor}",
    }


def construir_texto_noconsta(campo: str, query: str) -> str:
    """Construye el texto visible para una entrada automática de No Consta."""
    return construir_noconsta_entry(campo, query)['descripcion']


def _normalizar_identificador(valor: str) -> str:
    """Normaliza cédulas y RUCs para comparación exacta."""
    return re.sub(r'[^0-9A-Za-z]', '', str(valor or '').strip()).upper()


def _normalizar_texto(valor: str) -> str:
    """Normaliza texto libre para búsquedas parciales."""
    valor_normalizado = unicodedata.normalize('NFD', str(valor or '').strip().lower())
    valor_sin_acentos = ''.join(ch for ch in valor_normalizado if unicodedata.category(ch) != 'Mn')
    valor_sin_puntuacion = re.sub(r'[^0-9a-z\s]', '', valor_sin_acentos)
    return ' '.join(valor_sin_puntuacion.split())


def _generar_terminos_busqueda_api(query: str, campo: str) -> List[str]:
    """Genera variantes de búsqueda para la API cuando el campo es textual."""
    query = str(query or '').strip()
    campo = campo_busqueda_valido(campo)
    if not query:
        return []

    if campo in ('ruc', 'cedula'):
        return [query]

    terminos = []

    def agregar(termino: str):
        termino = str(termino or '').strip()
        if termino and termino not in terminos:
            terminos.append(termino)

    agregar(query)

    query_normalizada = _normalizar_texto(query)
    agregar(query_normalizada.upper())

    tokens = query_normalizada.split()
    while tokens:
        sufijo = ' '.join(tokens[-3:])
        if sufijo in SUFIJOS_SOCIETARIOS:
            tokens = tokens[:-3]
            continue

        sufijo = ' '.join(tokens[-2:])
        if sufijo in SUFIJOS_SOCIETARIOS:
            tokens = tokens[:-2]
            continue

        if tokens[-1] in SUFIJOS_SOCIETARIOS:
            tokens.pop()
            continue
        break

    agregar(' '.join(tokens).upper())
    return terminos


def _buscar_empresa_todas_paginas_por_termino(query: str) -> List[Dict]:
    """Consulta todas las páginas para un término exacto de búsqueda en la API."""
    primera = api_consultar(query, page=1)
    if not primera:
        return []

    todos = list(primera['resultados'])
    last_page = primera['paginacion']['last_page']

    for page in range(2, min(last_page + 1, MAX_PAGINAS_CARRITO + 1)):
        respuesta = api_consultar(query, page=page)
        if not respuesta:
            break
        todos.extend(respuesta['resultados'])

    return todos


def _buscar_empresa_todas_paginas_por_campo(query: str, campo: str) -> Optional[List[Dict]]:
    """Recupera candidatos desde la API y deduplica por aviso según el campo."""
    campo = campo_busqueda_valido(campo)
    if campo in ('ruc', 'cedula'):
        return buscar_empresa_todas_paginas(query)

    resultados = []
    avisos_vistos = set()
    for termino in _generar_terminos_busqueda_api(query, campo):
        for registro in _buscar_empresa_todas_paginas_por_termino(termino):
            aviso = registro.get('aviso_operacion') or registro.get('numero_aviso')
            if aviso and aviso in avisos_vistos:
                continue
            if aviso:
                avisos_vistos.add(aviso)
            resultados.append(registro)

    return resultados or None


def normalizar_noconsta_entry(entry) -> Dict[str, str]:
    """Normaliza una entrada de No Consta a la estructura canónica."""
    if isinstance(entry, dict):
        campo = campo_busqueda_valido(entry.get('campo'))
        valor = str(entry.get('valor') or '').strip()
        if campo in BUSQUEDA_FIELDS and valor:
            return construir_noconsta_entry(campo, valor)

        descripcion = str(entry.get('descripcion') or '').strip()
        if descripcion:
            return normalizar_noconsta_entry(descripcion)

        frase = str(entry.get('frase_certificacion') or '').strip()
        if frase:
            return {
                'campo': 'legacy',
                'valor': frase,
                'descripcion': frase,
                'frase_certificacion': frase,
            }

    texto = str(entry or '').strip()
    if not texto:
        return {
            'campo': 'legacy',
            'valor': '',
            'descripcion': '',
            'frase_certificacion': '',
        }

    etiqueta, separador, valor = texto.partition(':')
    campo = BUSQUEDA_FIELDS_NOCONSTA_LOOKUP.get(_normalizar_texto(etiqueta))
    valor = valor.strip()
    if separador and campo and valor:
        return construir_noconsta_entry(campo, valor)

    return {
        'campo': 'legacy',
        'valor': texto,
        'descripcion': texto,
        'frase_certificacion': f"asociado a los siguientes datos: {texto}",
    }


def normalizar_noconsta_entries(entries) -> List[Dict[str, str]]:
    """Normaliza una lista de entradas de No Consta, ignorando valores vacíos."""
    if not isinstance(entries, list):
        return []

    normalizados = []
    for entry in entries:
        normalizado = normalizar_noconsta_entry(entry)
        if normalizado.get('descripcion'):
            normalizados.append(normalizado)
    return normalizados


def es_misma_entrada_noconsta(actual, nueva) -> bool:
    """Determina si dos entradas de No Consta representan la misma búsqueda."""
    actual_normalizado = normalizar_noconsta_entry(actual)
    nueva_normalizada = normalizar_noconsta_entry(nueva)

    campo_actual = actual_normalizado.get('campo')
    campo_nuevo = nueva_normalizada.get('campo')
    if campo_actual == campo_nuevo and campo_actual in BUSQUEDA_FIELDS:
        if campo_actual in ('ruc', 'cedula'):
            return _normalizar_identificador(actual_normalizado.get('valor')) == _normalizar_identificador(nueva_normalizada.get('valor'))
        return _normalizar_texto(actual_normalizado.get('valor')) == _normalizar_texto(nueva_normalizada.get('valor'))

    return _normalizar_texto(actual_normalizado.get('descripcion')) == _normalizar_texto(nueva_normalizada.get('descripcion'))


def _coincide_registro_por_campo(registro: Dict, campo: str, query: str) -> bool:
    """Evalúa si un registro coincide con el campo de búsqueda seleccionado."""
    campo = campo_busqueda_valido(campo)
    query_identificador = _normalizar_identificador(query)

    if campo == 'ruc':
        return query_identificador in _normalizar_identificador(registro.get('ruc'))

    if campo == 'cedula':
        return query_identificador in _normalizar_identificador(registro.get('cedula_representante'))

    if campo == 'nombre_comercial':
        return _normalizar_texto(query) in _normalizar_texto(registro.get('razon_comercial'))

    if campo == 'razon_social':
        return _normalizar_texto(query) in _normalizar_texto(registro.get('razon_social'))

    return False


def buscar_empresa_por_campo(query: str, campo: str, page: int = 1) -> Optional[Dict]:
    """
    Busca empresas y filtra por el campo indicado con paginación local.

    Como la API externa solo acepta un término libre, se consultan todas las
    páginas disponibles dentro del límite configurado y se filtra localmente.
    """
    query = str(query or '').strip()
    if not query:
        return None

    campo = campo_busqueda_valido(campo)
    resultados_raw = _buscar_empresa_todas_paginas_por_campo(query, campo)
    if not resultados_raw:
        return None

    resultados_filtrados = [
        registro for registro in resultados_raw
        if _coincide_registro_por_campo(registro, campo, query)
    ]
    if not resultados_filtrados:
        return None

    total = len(resultados_filtrados)
    current_page = max(1, int(page or 1))
    last_page = max(1, math.ceil(total / BUSQUEDA_PAGE_SIZE))
    current_page = min(current_page, last_page)
    inicio = (current_page - 1) * BUSQUEDA_PAGE_SIZE
    fin = inicio + BUSQUEDA_PAGE_SIZE
    pagina_actual = resultados_filtrados[inicio:fin]

    detalle_normalizado = normalizar_datos_empresa(pagina_actual[0])
    detalle_normalizado['ubicacion_completa'] = construir_ubicacion_completa(detalle_normalizado)

    return {
        'detalle': detalle_normalizado,
        'avisos': normalizar_lista_avisos(pagina_actual),
        'resultados_raw': pagina_actual,
        'paginacion': {
            'current_page': current_page,
            'last_page': last_page,
            'total': total,
            'per_page': BUSQUEDA_PAGE_SIZE,
            'has_next': current_page < last_page,
            'has_previous': current_page > 1,
        },
    }
