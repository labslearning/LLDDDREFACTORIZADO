from django import template

register = template.Library()

@register.filter
def find_note_by_number(notes, number):
    """
    Finds a note with a specific number (e.g., 5 for the weighted average) 
    from a list of notes or a dictionary where the key is the number_nota.
    """
    # 1. Si es un diccionario (estructura usada por acudiente), intenta acceder por clave
    if isinstance(notes, dict):
        try:
            # Convierte el número a int si es string, que es la clave esperada.
            note_key = int(number)
            return notes.get(note_key)
        except ValueError:
            return None
        
    # 2. Si es una lista (estructura usada por estudiante), itera
    elif isinstance(notes, list):
        for note in notes:
            if hasattr(note, 'numero_nota') and note.numero_nota == number:
                return note
                
    return None