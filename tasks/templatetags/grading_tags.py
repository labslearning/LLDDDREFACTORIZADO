from django import template
from decimal import Decimal

register = template.Library()

# =======================================================
# 1. ACCESO A DATOS (LÓGICA)
# =======================================================

@register.filter
def get_item(dictionary, key):
    """
    Obtiene valor de un diccionario de forma segura.
    Uso: {{ midict|get_item:llave }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.simple_tag
def get_nota_celda(notas_map, estudiante_id, definicion_id):
    """
    ACCESO MATRICIAL DIRECTO.
    Recupera el valor exacto para una celda de la sábana de notas.
    
    Args:
        notas_map: Diccionario {estudiante_id: {definicion_id: valor}}
        estudiante_id: ID del alumno (fila)
        definicion_id: ID de la columna (definición)
        
    Retorna:
        El valor numérico o cadena vacía '' (para que el input HTML se vea limpio).
    """
    try:
        if not notas_map or not isinstance(notas_map, dict):
            return ''
            
        # 1. Obtener notas del estudiante
        notas_estudiante = notas_map.get(estudiante_id, {})
        
        # 2. Obtener nota de la columna específica
        valor = notas_estudiante.get(definicion_id)
        
        # Retornamos '' si es None, para no ensuciar el input con la palabra "None"
        return valor if valor is not None else ''
        
    except (AttributeError, TypeError):
        return ''

# =======================================================
# 2. AYUDAS VISUALES (UX/UI)
# =======================================================

@register.filter
def color_nota_css(valor):
    """
    Retorna clases CSS para colorear la nota según su valor.
    Estándar pedagógico:
    - < 3.0: Rojo (Desempeño Bajo)
    - 3.0 - 3.9: Negro/Amarillo (Básico)
    - 4.0 - 4.5: Azul (Alto)
    - > 4.5: Verde (Superior)
    
    Uso: class="form-control {{ nota_valor|color_nota_css }}"
    """
    try:
        if valor is None or valor == '':
            return ''
        
        # Convertimos a float, manejando comas por si acaso
        if isinstance(valor, str):
            valor = valor.replace(',', '.')
            
        f_valor = float(valor)
        
        if f_valor < 3.0:
            return 'text-danger fw-bold border-danger' # Rojo alerta
        elif 3.0 <= f_valor < 4.0:
            return 'text-dark' # Normal
        elif 4.0 <= f_valor < 4.6:
            return 'text-primary fw-500' # Azul destacado
        else:
            return 'text-success fw-bold' # Verde éxito
            
    except (ValueError, TypeError):
        return ''

@register.filter
def input_value(valor):
    """
    Filtro cosmético: Si el valor es None, imprime vacío.
    Si es un número decimal terminado en .0 (ej: 4.0), lo deja bonito.
    """
    if valor is None or valor == '':
        return ''
    return str(valor)