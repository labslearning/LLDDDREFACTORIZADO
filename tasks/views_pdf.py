# tasks/views_pdf.py
import markdown
import logging # <--- INYECTADO: Necesario para reportar errores
from django.http import HttpResponse
from django.shortcuts import get_object_or_404 # <--- INYECTADO: Para buscar el historial o dar 404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from weasyprint import HTML, CSS 

# --- Importaciones de tu IA (Existentes - NO TOCAR) ---
from .ai.orchestrator import ai_orchestrator
from .ai.constants import ACCION_ANALISIS_GLOBAL_BIENESTAR

# --- Importaciones Nuevas para Certificados (INYECTADO) ---
from .models import HistorialAcademico
from .services.certificate_service import CertificateService

# Configuración del logger
logger = logging.getLogger(__name__)

@login_required
def generar_pdf_bienestar(request):
    """
    Genera el PDF Profesional usando WeasyPrint + Stratos AI.
    (CÓDIGO ORIGINAL DEL USUARIO - INTACTO)
    """
    
    # 1. LLAMADA A STRATOS AI (Tu cerebro existente)
    respuesta_ia = ai_orchestrator.process_request(
        user=request.user,
        action_type=ACCION_ANALISIS_GLOBAL_BIENESTAR,
        user_query="",
        params={}
    )

    if not respuesta_ia.get('success'):
        return HttpResponse(f"Error generando reporte IA: {respuesta_ia.get('content')}", status=500)

    # 2. PROCESAMIENTO MARKDOWN
    texto_markdown = respuesta_ia.get('content', '')
    contenido_html_cuerpo = markdown.markdown(
        texto_markdown,
        extensions=['extra', 'nl2br', 'sane_lists']
    )

    # 3. CONTEXTO PARA EL TEMPLATE
    contexto = {
        'contenido_html': contenido_html_cuerpo,
        'objetivo': request.user, # Institucional
        'solicitante': request.user,
        'tipo_reporte': 'AUDITORÍA ESTRATÉGICA DE BIENESTAR',
        'fecha_impresion': timezone.now(),
        'query_original': 'Diagnóstico de Clima Escolar y Rutas de Mejora'
    }

    # 4. RENDERIZADO CON WEASYPRINT
    html_string = render_to_string('pdf/ai_report_template.html', contexto, request=request)

    # Configuración de respuesta HTTP como PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f"Informe_Stratos_Bienestar_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Generación del PDF
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    
    return response


# ========================================================
#  NUEVA FUNCIONALIDAD: CERTIFICADOS ACADÉMICOS
#  (Inyectado para solucionar el AttributeError)
# ========================================================

@login_required
def download_certificate_view(request, historial_id):
    """
    Genera el Certificado Oficial de Notas con QR de seguridad.
    """
    try:
        # 1. Obtener el historial específico
        historial = get_object_or_404(HistorialAcademico, id=historial_id)
        
        # 2. Instanciar el servicio profesional
        service = CertificateService()
        
        # 3. Generar los bytes del PDF
        pdf_bytes = service.generate_certificate_pdf(historial, request)
        
        # 4. Construir respuesta HTTP
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        
        # Nombre del archivo: "Certificado_JuanPerez_2025.pdf"
        filename = f"Certificado_{historial.estudiante.numero_documento}_{historial.anio_lectivo}.pdf"
        
        # 'inline' para ver en navegador (cambiar a 'attachment' para forzar descarga)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response

    except Exception as e:
        logger.error(f"Error crítico generando certificado PDF: {e}", exc_info=True)
        return HttpResponse("Error del servidor generando el documento oficial.", status=500)