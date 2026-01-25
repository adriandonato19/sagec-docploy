"""
Filtros personalizados para templates de trámites.

$Reusable$
"""
from django import template

register = template.Library()


@register.filter
def extraer_nombre_destinatario(destinatario):
    """
    Extrae el nombre del destinatario removiendo prefijos como "Señor", "Sr.", etc.
    
    $Reusable$
    """
    if not destinatario:
        return ""
    
    # Remover prefijos comunes
    prefijos = ["Señor", "SEÑOR", "señor", "Sr.", "SR.", "sr.", "Sr", "SR", "sr"]
    nombre = destinatario.strip()
    
    for prefijo in prefijos:
        if nombre.startswith(prefijo):
            nombre = nombre[len(prefijo):].strip()
            # Remover espacios adicionales después del prefijo
            while nombre.startswith(" "):
                nombre = nombre[1:]
            break
    
    return nombre

