"""
Servicio de integración con API externa (mock por ahora).

$Reusable$
"""
from typing import Optional, Dict
from .mock_data import buscar_por_ruc
from .adapters import normalizar_datos_empresa, construir_ubicacion_completa, normalizar_lista_avisos


def buscar_empresa(query: str) -> Optional[Dict]:
    """
    Busca una empresa por RUC o número de aviso.
    
    Args:
        query: RUC o número de aviso a buscar
    
    Returns:
        Diccionario con 'detalle' y 'avisos' o None si no se encuentra
    
    $Reusable$
    """
    # Por ahora usamos mock data
    resultado = buscar_por_ruc(query)
    
    if resultado:
        # Normalizar datos usando adapters
        detalle_normalizado = normalizar_datos_empresa(resultado['detalle'])
        detalle_normalizado['ubicacion_completa'] = construir_ubicacion_completa(detalle_normalizado)
        
        avisos_normalizados = normalizar_lista_avisos(resultado['avisos'])
        
        return {
            'detalle': detalle_normalizado,
            'avisos': avisos_normalizados,
        }
    
    return None

