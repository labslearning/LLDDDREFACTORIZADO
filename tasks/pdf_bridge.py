# tasks/utils/pdf_bridge.py

from django.template.loader import render_to_string
# SI USAS WEASYPRINT:
from weasyprint import HTML, CSS
from django.conf import settings
from tasks.models import Perfil, Nota, Asistencia

def generar_pdf_binario(estudiante_id, anio_actual):
    """
    Toma tu lógica actual de boletines y devuelve los BYTES del PDF.
    Esto permite guardarlo en la base de datos sin descargarlo.
    """
    
    # 1. REUTILIZA TU CONTEXTO ACTUAL
    # (Copia aquí la misma lógica que tienes en tu views.py para obtener notas)
    perfil = Perfil.objects.get(user_id=estudiante_id)
    notas = Nota.objects.filter(estudiante_id=estudiante_id)
    # ... (toda tu lógica de promedios, logros, observaciones) ...
    
    context = {
        'estudiante': perfil.user,
        'notas': notas,
        'anio': anio_actual,
        'es_copia_controlada': True, # Marca de agua opcional
        # ... resto de tu contexto ...
    }

    # 2. RENDERIZAR TU TEMPLATE ACTUAL
    # Usa exactamente el mismo HTML que ya tienes diseñado
    html_string = render_to_string('boletines/tu_template_de_siempre.html', context)

    # 3. GENERAR BINARIO (WeasyPrint Ejemplo)
    # Si usas otra librería, ajusta esta línea
    pdf_file = HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()
    
    return pdf_file
