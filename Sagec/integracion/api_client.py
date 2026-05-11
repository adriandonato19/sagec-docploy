"""
Cliente HTTP para la API de Panamá Emprende.
"""
import logging
from typing import Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


def _normalizar_tipo_persona(tipo: str) -> str:
    """Normaliza el tipo de persona para comparaciones internas."""
    return str(tipo or '').strip().lower()


def _resolver_ruc(registro: Dict) -> str:
    """
    Devuelve el identificador fiscal a usar en la app.

    Para persona natural, cuando la API no envía RUC, se usa la cédula del
    representante legal como valor operativo y visible del campo.
    """
    ruc = str(registro.get('ruc') or '').strip()
    if ruc:
        return ruc

    if _normalizar_tipo_persona(registro.get('tipo')) == 'natural':
        return str(registro.get('cedula_representante') or '').strip()

    return ''


def consultar_empresa(busqueda: str, page: int = 1) -> Optional[Dict]:
    """
    Consulta la API de Panamá Emprende por cédula, RUC o nombre comercial.

    Args:
        busqueda: Término de búsqueda (cédula, RUC, nombre comercial, razón social)
        page: Número de página a solicitar a la API

    Returns:
        Dict con 'resultados' (lista mapeada) y 'paginacion' (metadata), o None si falla
    """
    url = settings.PANAMA_EMPRENDE_API_URL.format(busqueda=busqueda)
    headers = {
        'X-User': settings.PANAMA_EMPRENDE_USER,
        'X-Password': settings.PANAMA_EMPRENDE_PASSWORD,
    }
    params = {'page': page}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        data = response.json()

        if not data or data.get('error'):
            logger.info("API Panamá Emprende: sin resultados para '%s'", busqueda)
            return None

        # La API retorna: {"data": {"data": [...], "current_page": N, "last_page": N, "total": N, ...}, "error": false, "mensaje": "..."}
        pagina_data = data.get('data', {})
        registros = pagina_data.get('data', [])

        if not registros:
            logger.info("API Panamá Emprende: sin resultados para '%s'", busqueda)
            return None

        current_page = pagina_data.get('current_page', 1)
        last_page = pagina_data.get('last_page', 1)
        total = pagina_data.get('total', len(registros))
        per_page = pagina_data.get('per_page', 10)

        return {
            'resultados': [_mapear_campos(r) for r in registros],
            'paginacion': {
                'current_page': current_page,
                'last_page': last_page,
                'total': total,
                'per_page': per_page,
                'has_next': current_page < last_page,
                'has_previous': current_page > 1,
            },
        }

    except requests.exceptions.Timeout:
        logger.error("API Panamá Emprende: timeout al consultar '%s'", busqueda)
        return None
    except requests.exceptions.HTTPError as e:
        logger.error("API Panamá Emprende: error HTTP %s al consultar '%s'", e.response.status_code, busqueda)
        return None
    except requests.exceptions.ConnectionError:
        logger.error("API Panamá Emprende: error de conexión al consultar '%s'", busqueda)
        return None
    except requests.exceptions.RequestException as e:
        logger.error("API Panamá Emprende: error inesperado al consultar '%s': %s", busqueda, e)
        return None
    except (ValueError, KeyError, TypeError) as e:
        logger.error("API Panamá Emprende: error al procesar respuesta para '%s': %s", busqueda, e)
        return None


def _mapear_campos(registro: Dict) -> Dict:
    """
    Mapea los campos de la API real al formato que esperan los adapters.

    Campos API real → formato interno (mock):
        numero_aviso → aviso_operacion
        nombreComercial → razon_comercial
        razon_social_juridica/natural → razon_social
        estado → estado_sucursal
        monto_estimado → capital_invertido
        id_sucursal → sucursal
    """
    # Determinar razón social (jurídica tiene prioridad)
    razon_social = (registro.get('razon_social_juridica') or
                    registro.get('razon_social_natural') or '')

    # Para persona natural sin RUC, usamos la cédula del representante.
    ruc = _resolver_ruc(registro)
    dv = ''  # La API real no separa el DV
    tipo = str(registro.get('tipo') or '').strip()
    representante_legal = str(registro.get('representante_legal') or '').strip()
    cedula_representante = str(registro.get('cedula_representante') or '').strip()

    return {
        'aviso_operacion': registro.get('numero_aviso', ''),
        'numero_licencia': '',
        'razon_comercial': (registro.get('nombreComercial') or '').strip(),
        'representante_legal': representante_legal,
        'cedula_representante': cedula_representante,
        'ruc': ruc,
        'dv': dv,
        'tipo': tipo,
        'razon_social': razon_social.strip(),
        'fecha_inicio_operaciones': registro.get('fecha_inicio_operaciones', ''),
        'provincia': registro.get('provincia', ''),
        'distrito': registro.get('distrito', ''),
        'corregimiento': registro.get('corregimiento') or '',
        'urbanizacion': registro.get('urbanizacion') or '',
        'calle': registro.get('calle') or '',
        'casa': registro.get('casa') or '',
        'edificio': registro.get('edificio') or '',
        'apartamento': registro.get('apartamento') or '',
        'actividad_comercial': '',
        'ciiu': '',
        'capital_invertido': registro.get('monto_estimado', 0) or 0,
        'estado_sucursal': (registro.get('estado') or '').strip(),
        'sucursal': str(registro.get('id_sucursal', '000')),
    }
