"""
Adaptadores para normalizar datos de la API externa (Actualizado para el nuevo JSON y campo sucursal).

$Reusable$
"""
from typing import Dict, List, Optional


def normalizar_datos_empresa(datos_api: Dict) -> Dict:
    """
    Normaliza los datos de la API de Panamá Emprende a formato interno.
    
    Args:
        datos_api: Diccionario con datos crudos de la API
    
    Returns:
        Diccionario normalizado con estructura estándar
    
    $Reusable$
    """
    # Manejar el RUC que ya puede venir con guiones o separado del DV
    ruc_raw = str(datos_api.get('ruc', ''))
    dv = str(datos_api.get('dv', ''))
    
    if dv and dv not in ruc_raw:
        ruc_completo = f"{ruc_raw}-{dv}"
    else:
        ruc_completo = ruc_raw

    return {
        'ruc': ruc_raw,
        'dv': dv,
        'ruc_completo': ruc_completo,
        'razon_social': datos_api.get('razon_social', ''),
        'razon_comercial': datos_api.get('razon_comercial', ''),
        'numero_aviso': datos_api.get('aviso_operacion', ''),
        'numero_licencia': datos_api.get('numero_licencia', ''),
        'representante_legal': datos_api.get('representante_legal', ''),
        'fecha_inicio_operaciones': datos_api.get('fecha_inicio_operaciones', ''),
        'provincia': datos_api.get('provincia', ''),
        'distrito': datos_api.get('distrito', ''),
        'corregimiento': datos_api.get('corregimiento', ''),
        'urbanizacion': datos_api.get('urbanizacion', ''),
        'calle': datos_api.get('calle', ''),
        'casa': datos_api.get('casa', ''),
        'edificio': datos_api.get('edificio', ''),
        'apartamento': datos_api.get('apartamento', ''),
        'actividad_comercial': datos_api.get('actividad_comercial', ''),
        'actividades_comerciales_ciiu': datos_api.get('ciiu', ''),
        'capital_invertido': f"{datos_api.get('capital_invertido', 0.00):.2f}",
        'estatus': datos_api.get('estado_sucursal', ''),
        'sucursal': datos_api.get('sucursal', '000'), # Nuevo campo sucursal
    }


def construir_ubicacion_completa(datos: Dict) -> str:
    """
    Construye la dirección completa concatenando campos de ubicación.
    
    Args:
        datos: Diccionario con datos de empresa
    
    Returns:
        String con la dirección completa formateada
    
    $Reusable$
    """
    partes = []
    
    if datos.get('provincia'):
        partes.append(datos['provincia'])
    if datos.get('distrito'):
        partes.append(datos['distrito'])
    if datos.get('corregimiento'):
        partes.append(datos['corregimiento'])
    if datos.get('urbanizacion'):
        partes.append(datos['urbanizacion'])
    if datos.get('calle'):
        partes.append(datos['calle'])
    if datos.get('casa'):
        partes.append(f"Casa {datos['casa']}")
    if datos.get('edificio'):
        partes.append(datos['edificio'])
    if datos.get('apartamento'):
        partes.append(datos['apartamento'])
    
    return ', '.join(filter(None, partes)) if partes else 'No especificada'


def normalizar_lista_avisos(avisos_api: List[Dict]) -> List[Dict]:
    """
    Normaliza una lista de avisos de operación.
    
    Args:
        avisos_api: Lista de diccionarios con datos de avisos
    
    Returns:
        Lista normalizada de avisos
    
    $Reusable$
    """
    return [
        {
            'numero_aviso': aviso.get('aviso_operacion', ''),
            'sucursal': aviso.get('sucursal', '000'), # Usar el campo sucursal del JSON
            'razon_comercial': aviso.get('razon_comercial', ''),
            'razon_social': aviso.get('razon_social', ''),
            'estatus': aviso.get('estado_sucursal', ''),
            'fecha_inicio': aviso.get('fecha_inicio_operaciones', ''),
            'ruc_completo': f"{aviso.get('ruc', '')}-{aviso.get('dv', '')}" if aviso.get('dv') else aviso.get('ruc', ''),
        }
        for aviso in avisos_api
    ]
