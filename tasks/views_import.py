import json
import logging
import datetime
import traceback
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction, DatabaseError
from django.conf import settings

# --- IMPORTACIONES DE MODELOS Y SERVICIOS ---
from .models import ImportBatch, StagingRow, HistorialAcademico
from .services.importer import ImportService
from .services.document_importer import DocumentImportService
from .services.rollback import RollbackService

# Configuración de Logger para Auditoría
logger = logging.getLogger(__name__)

# --- CONTROL DE ACCESO (GATEKEEPER) ---
def is_staff_or_superuser(user):
    """Solo personal autorizado (Staff/Superuser) puede operar el ETL."""
    return user.is_staff or user.is_superuser

# ========================================================
#  1. MÓDULO DE INGESTA (PIPELINE DE CARGA)
# ========================================================

@login_required
@user_passes_test(is_staff_or_superuser)
def import_upload_view(request):
    """
    PASO 1: SUBIDA Y ANÁLISIS (Upload Strategy Pattern)
    Detecta automáticamente si es una carga de DATOS (Excel) o DOCUMENTOS (ZIP).
    """
    current_year = datetime.datetime.now().year
    available_years = list(range(current_year + 1, 1969, -1))

    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        target_year = request.POST.get('target_year')
        
        # 1. Validación de Contexto
        if not target_year:
            messages.error(request, "⛔ REQUERIDO: Debes seleccionar el 'Año Lectivo' para aislar los datos.")
            return render(request, 'admin/import/upload.html', {'available_years': available_years})

        try:
            # 2. Detección de Estrategia por Extensión
            file_extension = archivo.name.split('.')[-1].lower()

            if file_extension == 'zip':
                # --- ESTRATEGIA A: GESTIÓN DOCUMENTAL ---
                logger.info(f"AUDIT: Inicio carga documental (ZIP) por {request.user} - Año {target_year}")
                
                doc_service = DocumentImportService()
                stats = doc_service.process_zip(archivo, int(target_year), request.user)
                
                msg = f"📚 Digitalización: {stats['processed']} documentos archivados."
                if stats['errors']:
                    msg += f" ⚠️ {len(stats['errors'])} fallos parciales."
                
                messages.success(request, msg)
                return redirect('import_history')

            else:
                # --- ESTRATEGIA B: INGESTA DE DATOS (ETL) ---
                logger.info(f"AUDIT: Inicio carga de datos (Excel) por {request.user} - Año {target_year}")
                
                service = ImportService()
                batch, columns, preview_data, suggestions = service.create_batch(
                    file_obj=archivo, 
                    user=request.user, 
                    model_target='HistorialAcademico'
                )
                
                # Persistencia de Estado (Session)
                request.session['import_batch_id'] = str(batch.id)
                request.session['import_columns'] = columns       
                request.session['import_preview'] = preview_data  
                request.session['import_suggestions'] = suggestions
                request.session['import_target_year'] = int(target_year)
                
                messages.success(request, f"✅ Archivo analizado correctamente. Configurado para: {target_year}")
                return redirect('import_mapping')
            
        except ValueError as e:
            logger.warning(f"Validación fallida: {e}")
            messages.warning(request, f"⚠️ Validación: {str(e)}")
        except Exception as e:
            logger.critical(f"Error crítico en upload: {traceback.format_exc()}")
            messages.error(request, f"⛔ Error del Sistema: {str(e)}")
            
    return render(request, 'admin/import/upload.html', {'available_years': available_years})

@login_required
@user_passes_test(is_staff_or_superuser)
def import_mapping_view(request):
    """
    PASO 2: MAPEO Y TRANSFORMACIÓN (Mapping Interface)
    Conecta columnas del archivo con el esquema de base de datos.
    """
    batch_id = request.session.get('import_batch_id')
    target_year = request.session.get('import_target_year')
    
    # Validación de Sesión
    if not batch_id or not target_year:
        messages.warning(request, "⚠️ La sesión ha expirado. Por favor reinicia el proceso.")
        return redirect('import_upload')

    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # --- EJECUCIÓN DEL ETL ---
    if request.method == 'POST':
        mapping_json = request.POST.get('mapping_data')
        
        if not mapping_json:
            messages.error(request, "❌ Error: No se recibieron datos de mapeo.")
            return redirect('import_mapping')

        try:
            mapping_dict = json.loads(mapping_json)
            service = ImportService()
            
            # Ejecución del Pipeline
            count = service.execute_import(batch_id, mapping_dict, target_year)
            
            # Garbage Collection (Limpieza de Sesión)
            keys = ['import_batch_id', 'import_columns', 'import_preview', 'import_suggestions']
            for key in keys:
                if key in request.session: del request.session[key]
            
            if count > 0:
                messages.success(request, f"🚀 Éxito: {count} registros procesados para el año {target_year}.")
            else:
                messages.warning(request, "⚠️ El proceso finalizó pero no se generaron registros. Verifica los IDs de estudiante.")
            
            return redirect('import_history') 
            
        except ValueError as e:
            messages.warning(request, f"⚠️ Error de Lógica: {str(e)}")
        except Exception as e:
            logger.error(f"Error en mapping: {traceback.format_exc()}")
            messages.error(request, f"⛔ Error Crítico: {str(e)}")

    # --- PREPARACIÓN DE VISTA ---
    columns = request.session.get('import_columns', [])
    preview_rows = request.session.get('import_preview', [])
    suggestions = request.session.get('import_suggestions', {})

    # Recuperación de emergencia (Disaster Recovery)
    if not columns and batch.filas_staging.exists():
        first_rows = batch.filas_staging.all()[:5]
        preview_rows = [r.data_original for r in first_rows]
        if preview_rows:
            columns = list(preview_rows[0].keys())

    materias_comunes = [
        'Matemáticas', 'Español', 'Inglés', 'Ciencias Naturales', 'Ciencias Sociales', 
        'Física', 'Química', 'Filosofía', 'Educación Física', 'Artes', 'Informática'
    ]

    context = {
        'batch': batch,
        'columns': columns,      
        'rows': preview_rows,    
        'suggestions': suggestions, 
        'materias': materias_comunes,
        'target_year': target_year 
    }
    return render(request, 'admin/import/mapping.html', context)

# ========================================================
#  2. MÓDULO DE AUDITORÍA Y SEGURIDAD
# ========================================================

@login_required
@user_passes_test(is_staff_or_superuser)
def import_history_view(request):
    """
    DASHBOARD DE CONTROL
    Visualización de bitácora de operaciones.
    """
    queryset = ImportBatch.objects.select_related('usuario').all().order_by('-creado_en')
    
    paginator = Paginator(queryset, 15) 
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin/import/history.html', {'lotes': page_obj})

@login_required
@user_passes_test(is_staff_or_superuser)
def import_inspect_view(request, batch_id):
    """
    INSPECTOR VISUAL (Data Lens) - VERSIÓN FORENSE
    Muestra éxitos y, lo más importante, reporta por qué fallaron las filas.
    """
    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # 1. Obtener Éxitos (Historiales creados)
    historiales = HistorialAcademico.objects.select_related('estudiante').filter(lote_origen=batch)
    
    # 2. Obtener Fallos (Filas de Staging inválidas) - ESTO ES NUEVO
    errores = batch.filas_staging.filter(es_valido=False).order_by('numero_fila')
    
    # Paginación inteligente (Prioridad a errores si el lote falló)
    if batch.estado == 'FAILED' or batch.estado == 'PARTIAL_SUCCESS':
        # Si falló, mostramos los errores en la tabla principal
        modo_visualizacion = 'errores'
        paginator = Paginator(errores, 50)
    else:
        # Si fue exitoso, mostramos los datos cargados
        modo_visualizacion = 'exitos'
        paginator = Paginator(historiales, 50)

    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin/import/inspect.html', {
        'batch': batch,
        'page_obj': page_obj,
        'modo': modo_visualizacion,
        'total_errores': errores.count(),
        'total_exitos': historiales.count()
    })

@login_required
@user_passes_test(is_staff_or_superuser)
def import_rollback_view(request, batch_id):
    """
    ROLLBACK TRANSACCIONAL (Atomic Undo)
    Elimina un lote completo garantizando integridad de base de datos.
    """
    if request.method == "POST":
        batch = get_object_or_404(ImportBatch, id=batch_id)
        
        try:
            with transaction.atomic():
                # 1. Identificar registros a eliminar
                target_records = HistorialAcademico.objects.filter(lote_origen=batch)
                count = target_records.count()
                
                # 2. Eliminación Física
                target_records.delete()
                
                # 3. Limpieza de Temporales
                batch.filas_staging.all().delete()
                
                # 4. Marcado de Auditoría
                batch.estado = 'ROLLED_BACK'
                batch.filas_exitosas = 0
                batch.save()
                
                logger.info(f"AUDIT: Rollback por {request.user} en lote {batch_id}. -{count} registros.")
                messages.success(request, f"♻️ Operación Revertida: Se eliminaron {count} registros del sistema.")
                
        except DatabaseError as e:
            logger.critical(f"Fallo en BD durante Rollback: {e}")
            messages.error(request, "⛔ Error de Base de Datos: No se pudo completar la reversión.")
        except Exception as e:
            logger.error(f"Error inesperado en rollback: {traceback.format_exc()}")
            messages.error(request, f"⛔ Error Crítico: {str(e)}")
            
    return redirect('import_history')