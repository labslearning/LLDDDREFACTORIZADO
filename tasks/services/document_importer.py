import zipfile
import os
import logging
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from tasks.models import DocumentoHistorico, Perfil

logger = logging.getLogger(__name__)

class DocumentImportService:
    """
    🏭 MOTOR DE INGESTA DOCUMENTAL MASIVA (ZIP STREAMING)
    
    Procesa archivos comprimidos ZIP conteniendo activos digitales históricos.
    Realiza asociación automática mediante heurística de nombres y garantiza
    integridad transaccional.
    
    Estrategia de Memoria:
    - No descomprime todo el ZIP en RAM.
    - Lee archivo por archivo en stream.
    """

    # Mapa de inferencia heurística (Palabra clave -> Tipo Documento)
    HEURISTIC_MAP = {
        'observador': 'OBSERVADOR',
        'disciplina': 'OBSERVADOR',
        'convivencia': 'OBSERVADOR',
        'boletin': 'BOLETIN',
        'notas': 'BOLETIN',
        'calificaciones': 'BOLETIN',
        'informe': 'BOLETIN',
        'acta': 'ACTA',
        'promocion': 'ACTA',
        'comision': 'ACTA',
        'certificado': 'CERTIFICADO',
        'constancia': 'CERTIFICADO',
        'matricula': 'MATRICULA',
        'ficha': 'MATRICULA',
        'paz': 'PAZ_SALVO',
        'salvo': 'PAZ_SALVO',
        'clinico': 'CLINICO',
        'medico': 'CLINICO',
        'legal': 'LEGAL',
        'juridico': 'LEGAL',
        'cedula': 'DOCUMENTO_ID',
        'ti': 'DOCUMENTO_ID',
        'rc': 'DOCUMENTO_ID',
    }

    def process_zip(self, zip_file_obj, target_year, user) -> dict:
        """
        Ejecuta el pipeline de procesamiento del ZIP.
        Retorna estadísticas detalladas.
        """
        stats = {
            'processed': 0,
            'errors': [],
            'ignored': 0,
            'bytes_processed': 0
        }

        # 1. Validación de Integridad del ZIP
        if not zipfile.is_zipfile(zip_file_obj):
            raise ValueError("El archivo subido no es un contenedor ZIP válido o está corrupto.")

        try:
            with zipfile.ZipFile(zip_file_obj, 'r') as zf:
                # Filtrar archivos basura de sistemas operativos (__MACOSX, .DS_Store, Thumbs.db)
                file_list = [
                    f for f in zf.namelist() 
                    if not f.startswith('__') 
                    and not f.endswith('/') 
                    and not f.split('/')[-1].startswith('.')
                ]

                total_files = len(file_list)
                logger.info(f"Iniciando procesamiento de ZIP con {total_files} archivos para el año {target_year}")

                for filename in file_list:
                    result = self._process_single_file(zf, filename, target_year, user)
                    
                    if result['status'] == 'success':
                        stats['processed'] += 1
                        stats['bytes_processed'] += result['size']
                    elif result['status'] == 'ignored':
                        stats['ignored'] += 1
                    else:
                        stats['errors'].append(result['message'])

        except Exception as e:
            logger.error(f"Error crítico procesando ZIP: {e}", exc_info=True)
            raise ValueError(f"Fallo sistémico al procesar el contenedor ZIP: {str(e)}")

        return stats

    def _process_single_file(self, zf_handle, filename, target_year, user) -> dict:
        """
        Procesa un único archivo dentro del ZIP con aislamiento de errores.
        """
        try:
            # A. Extracción de Metadatos del Nombre
            base_name = os.path.basename(filename)
            name_clean = base_name.lower().replace('-', '_').replace(' ', '_')
            
            # Separar ID del resto (Formato esperado: 12345_tipo.pdf)
            name_parts = name_clean.split('_')
            
            # Validación mínima: Debe tener al menos el ID
            if not name_parts or not name_parts[0].isalnum():
                return {'status': 'error', 'message': f"{base_name}: Formato de nombre inválido. Se requiere [ID_ESTUDIANTE]_..."}

            documento_id = name_parts[0]
            
            # B. Inferencia de Tipo (IA Simbólica)
            tipo_detectado = 'OTRO'
            for keyword, doc_type in self.HEURISTIC_MAP.items():
                if keyword in name_clean:
                    tipo_detectado = doc_type
                    break

            # C. Búsqueda de Estudiante (Query Optimizada)
            # Intentamos match exacto primero, luego búsqueda flexible
            estudiante = Perfil.objects.filter(numero_documento=documento_id).first()
            
            if not estudiante:
                # Si el archivo es "ACTA_GENERAL.pdf", no requiere estudiante
                if 'acta' in name_clean and 'general' in name_clean:
                    estudiante = None
                    tipo_detectado = 'ACTA'
                else:
                    return {'status': 'error', 'message': f"{base_name}: Estudiante con ID '{documento_id}' no encontrado."}

            # D. Lectura y Persistencia (Streaming)
            # Usamos transaction.atomic para asegurar integridad de este registro específico
            with transaction.atomic():
                file_info = zf_handle.getinfo(filename)
                
                # Protección contra ZIP Bombs (Archivos descomprimidos gigantes)
                if file_info.file_size > 100 * 1024 * 1024: # Límite 100MB por archivo interno
                    return {'status': 'error', 'message': f"{base_name}: Excede límite de 100MB."}

                with zf_handle.open(filename) as file_content:
                    # Crear instancia del modelo
                    doc = DocumentoHistorico(
                        estudiante=estudiante,
                        anio_lectivo=target_year,
                        tipo=tipo_detectado,
                        nombre_original=base_name,
                        subido_por=user,
                        procesado_automaticamente=True,
                        metadata={
                            'source': 'batch_zip_upload',
                            'original_path': filename,
                            'file_size': file_info.file_size
                        }
                    )
                    
                    # Guardar el contenido (Django maneja el streaming al storage backend S3/Local)
                    doc.archivo.save(base_name, ContentFile(file_content.read()))
                    doc.save()

            return {'status': 'success', 'size': file_info.file_size}

        except Exception as e:
            logger.warning(f"Fallo al procesar archivo interno '{filename}': {str(e)}")
            return {'status': 'error', 'message': f"{filename}: Error interno de procesamiento ({str(e)})"}
