from django import template
from django.db.models import QuerySet

register = template.Library()

@register.filter
def get_item(value, arg):
    """
    Accede de forma segura a un elemento por clave (diccionario) o por índice (lista/QuerySet/Tuple).
    
    Uso:
    {{ diccionario|get_item:"clave" }}
    {{ lista|get_item:0 }}
    """
    if value is None:
        return None
    
    # 1. Acceso por índice (para listas, QuerySets, tuplas)
    if isinstance(value, (list, tuple, QuerySet)):
        try:
            arg = int(arg)
            return value[arg]
        except (ValueError, TypeError, IndexError):
            # Falla si el índice no es válido o está fuera de rango
            return None
    
    # 2. Acceso por clave (para diccionarios)
    elif isinstance(value, dict):
        return value.get(arg)
        
    # 3. Fallback seguro si no es ninguna colección esperada
    return None

# Nota: El filtro 'dict_filters' ya está cargado y registrado en tu proyecto, 
# por lo que no es necesario redefinirlo a menos que quieras reemplazar su funcionalidad.