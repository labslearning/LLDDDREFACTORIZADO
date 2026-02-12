import qrcode
import base64
import logging
from io import BytesIO
from typing import Dict, Any, Union

from django.template.loader import render_to_string
from django.utils import timezone
from django.core.signing import Signer
from django.http import HttpRequest
from django.conf import settings
from django.utils.text import slugify

from weasyprint import HTML

# Configuración de Logging Estructurado para trazabilidad industrial
logger = logging.getLogger(__name__)

class CertificateService:
    """
    🏭 SERVICIO DE CERTIFICACIÓN ACADÉMICA (ENTERPRISE GRADE)
    
    Responsabilidades:
    1. Generación de firmas criptográficas (Anti-Tampering) mediante Salt aislado.
    2. Renderizado de documentos PDF de alta fidelidad (High-Fidelity) con WeasyPrint.
    3. Normalización estadística de calificaciones y cálculo de promedios robustos.
    """

    # Constantes de Configuración (Fácil mantenimiento institucional)
    QR_COLOR_FILL = "#002d72"  # Azul Institucional
    QR_COLOR_BACK = "white"
    VERIFICATION_ROUTE = '/verificar-certificado/publico/'
    SIGNER_SALT = 'tasks.services.certificate' # Aislamiento de seguridad criptográfica

    def __init__(self):
        # Usamos Salt para asegurar que estos tokens solo sirven para certificados
        self.signer = Signer(salt=self.SIGNER_SALT)

    def generate_signed_url(self, request: HttpRequest, doc_id: str, year: int) -> str:
        """
        Genera una URL firmada criptográficamente para el código QR.
        Garantiza que el ID del documento y el año no han sido manipulados.
        """
        try:
            payload = f"{doc_id}:{year}"
            signed_token = self.signer.sign(payload)
            return request.build_absolute_uri(f'{self.VERIFICATION_ROUTE}?token={signed_token}')
        except Exception as e:
            logger.error(f"Error generando firma criptográfica para {doc_id}: {e}")
            raise ValueError("Fallo en el subsistema de seguridad documental.")

    def generate_qr_code(self, data: str) -> str:
        """
        Genera un QR de alta redundancia (Level H) en Base64.
        Permite la lectura incluso con daños físicos en el papel impreso.
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H, # Máxima redundancia
                box_size=10,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(
                fill_color=self.QR_COLOR_FILL, 
                back_color=self.QR_COLOR_BACK
            )
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode()
            
        except Exception as e:
            logger.critical(f"Fallo crítico en motor QR: {str(e)}", exc_info=True)
            return ""

    def generate_certificate_pdf(self, historial: Any, request: HttpRequest) -> bytes:
        """
        Orquestador principal del pipeline de generación de PDF oficial.
        """
        try:
            estudiante = historial.estudiante
            
            # 1. Capa de Seguridad: URL Firmada para validación QR
            verify_url = self.generate_signed_url(
                request, 
                estudiante.numero_documento, 
                historial.anio_lectivo
            )
            
            # 2. Capa de Activos: Generar QR institucional
            qr_base64 = self.generate_qr_code(verify_url)

            # 3. Capa de Datos: Procesamiento de calificaciones
            promedio_final = self._calcular_promedio_robusto(historial.calificaciones_json)

            # 4. Construcción del Contexto de Renderizado
            context = {
                'estudiante': estudiante,
                'historial': historial,
                'notas': historial.calificaciones_json,
                'fecha_impresion': timezone.now(),
                'qr_code': qr_base64,
                'anio': historial.anio_lectivo,
                'promedio': promedio_final,
                'uuid_folio': str(historial.id).split('-')[0].upper(), # Folio visual único
                'request': request 
            }

            # 5. Renderizado de Template a String HTML
            html_string = render_to_string('admin/reports/certificate_template.html', context)
            
            # 6. Generación de PDF mediante Motor WeasyPrint
            base_url = request.build_absolute_uri('/')
            html = HTML(string=html_string, base_url=base_url)
            
            pdf_bytes = html.write_pdf(
                presentational_hints=True, # Importante para CSS de impresión
                metadata=self._get_pdf_metadata(estudiante, historial.anio_lectivo)
            )
            
            logger.info(f"Certificado generado exitosamente: {estudiante.numero_documento} - Ciclo {historial.anio_lectivo}")
            return pdf_bytes

        except Exception as e:
            logger.critical(
                f"🔥 Fallo crítico en generación PDF. Historial ID: {historial.id}. Error: {str(e)}", 
                exc_info=True
            )
            raise ValueError("Error interno procesando el documento. Contacte a sistemas.")

    def _calcular_promedio_robusto(self, notas: Dict) -> float:
        """
        Calcula el promedio aritmético limpiando datos corruptos, textos o nulos.
        """
        if not notas or not isinstance(notas, dict):
            return 0.0
        
        total = 0.0
        count = 0
        
        for val in notas.values():
            try:
                # Extraer valor si es dict complejo o usar el valor directo
                raw_val = val.get('valor') if isinstance(val, dict) else val
                
                if raw_val is None:
                    continue
                    
                # Limpieza y conversión segura
                if isinstance(raw_val, str):
                    clean_val = raw_val.strip().replace(',', '.')
                    # Validar si es convertible a número (flotante)
                    if not clean_val.replace('.', '', 1).replace('-', '', 1).isdigit():
                        continue
                    num = float(clean_val)
                else:
                    num = float(raw_val)

                total += num
                count += 1
                
            except (ValueError, TypeError, AttributeError):
                continue # Ignorar entradas no numéricas ("Aprobado", "Pendiente", etc.)
                
        return round(total / count, 2) if count > 0 else 0.0

    def _get_pdf_metadata(self, estudiante: Any, anio: int) -> Dict[str, str]:
        """
        Genera metadatos XMP profesionales para el archivo PDF.
        CORRECCIÓN: Acceso a través de la relación 'user'.
        """
        # Extraer nombres desde el modelo User relacionado
        first_name = estudiante.user.first_name if estudiante.user else "Estudiante"
        last_name = estudiante.user.last_name if estudiante.user else f"Doc:{estudiante.numero_documento}"
        
        nombre_completo = f"{first_name} {last_name}"
        nombre_slug = slugify(nombre_completo)
        
        return {
            'Title': f"Certificado Academico {anio} - {nombre_completo}",
            'Author': getattr(settings, 'SCHOOL_NAME', 'Learning Labs Institute'),
            'Subject': f"Historial de Calificaciones Oficial - Periodo {anio}",
            'Keywords': f"certificado, notas, {nombre_slug}, {anio}, oficial",
            'Creator': 'Sistema de Gestion Academica V2'
        }