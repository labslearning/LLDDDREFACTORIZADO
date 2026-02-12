import logging
import time
from typing import Dict, Any
from django.db import transaction
from django.utils import timezone
from tasks.models import ImportBatch, HistorialAcademico, StagingRow

logger = logging.getLogger(__name__)

class RollbackService:
    """
    ⏪ MÁQUINA DEL TIEMPO (ROLLBACK SYSTEM) - ENTERPRISE EDITION
    
    Características Avanzadas:
    1. Atomicidad Estricta: Todo o nada.
    2. Bulk Operations: Minimiza latencia de red agrupando updates SQL.
    3. Auditoría Forense: Guarda un reporte detallado JSON dentro del Lote.
    4. Resiliencia: Maneja inconsistencias de datos (fantasmas) silenciosamente pero dejando rastro.
    """

    def revert_batch(self, batch_id: str) -> Dict[str, Any]:
        """
        Ejecuta la reversión quirúrgica de un lote con optimización de alto rendimiento.
        """
        start_time = time.time()
        
        try:
            batch = ImportBatch.objects.get(id=batch_id)
        except ImportBatch.DoesNotExist:
            raise ValueError(f"Lote {batch_id} no encontrado.")

        # Validación de Estados Reversibles
        ESTADOS_REVERSIBLES = ['COMPLETED', 'PARTIAL_SUCCESS', 'FAILED', 'IMPORTING']
        if batch.estado not in ESTADOS_REVERSIBLES:
            raise ValueError(f"Operación inválida: No se puede revertir un lote en estado '{batch.estado}'.")

        # Contadores y Listas para Bulk Update
        stats = {
            'deleted': 0,
            'restored': 0,
            'ghosts': 0, # Registros que debían estar pero ya no existen
            'duration_ms': 0
        }
        
        staging_rows_to_update = []
        rollback_log = []

        logger.info(f"🔄 [ROLLBACK-START] Iniciando reversión lote {batch_id}")

        with transaction.atomic():
            # 1. Bloqueo de filas afectadas (SELECT FOR UPDATE)
            # Evita que otro proceso modifique estas filas mientras revertimos
            filas_afectadas = batch.filas_staging.select_for_update().filter(
                id_objeto_creado__isnull=False
            ).exclude(id_objeto_creado='')

            if not filas_afectadas.exists():
                logger.warning(f"⚠️ El lote {batch_id} no tiene registros vinculados para revertir.")
                batch.estado = 'ROLLED_BACK'
                batch.save()
                return stats

            # 2. Iteración y Procesamiento
            for row in filas_afectadas:
                try:
                    # A. Obtener el registro final
                    historial = HistorialAcademico.objects.get(id=row.id_objeto_creado)
                    
                    # B. Restaurar Snapshot (Padre) si existe
                    parent = historial.parent_version
                    if parent:
                        parent.is_active = True
                        parent.save(update_fields=['is_active']) # Optimización: solo actualizamos 1 campo
                        stats['restored'] += 1
                    
                    # C. Hard Delete del registro erróneo
                    historial.delete()
                    stats['deleted'] += 1

                    # D. Preparar actualización de Staging (En memoria)
                    row.es_valido = False
                    row.id_objeto_creado = None
                    row.errores.append(f"[{timezone.now().strftime('%H:%M:%S')}] Revertido por usuario.")
                    staging_rows_to_update.append(row)

                except HistorialAcademico.DoesNotExist:
                    # Manejo de Fantasmas: El registro ya fue borrado manualmente
                    stats['ghosts'] += 1
                    row.errores.append("Rollback Warning: El registro ya no existía en BD.")
                    staging_rows_to_update.append(row)
                    continue
                
                except Exception as e:
                    logger.error(f"❌ Error crítico en fila {row.id}: {str(e)}")
                    raise e # Rompemos la transacción para garantizar integridad total

            # 3. BULK UPDATE (La joya de la corona del rendimiento)
            # En lugar de 1000 queries, hacemos 1 query gigante.
            if staging_rows_to_update:
                StagingRow.objects.bulk_update(
                    staging_rows_to_update, 
                    fields=['es_valido', 'id_objeto_creado', 'errores'],
                    batch_size=1000
                )

            # 4. Finalización y Reporte
            end_time = time.time()
            duration_ms = round((end_time - start_time) * 1000, 2)
            stats['duration_ms'] = duration_ms

            # Guardamos el reporte forense en el log de errores del batch (o un campo nuevo json 'audit_log')
            reporte_final = {
                "action": "ROLLBACK",
                "timestamp": timezone.now().isoformat(),
                "stats": stats,
                "executed_by": "System/User" # Podrías pasar el user request.user aquí
            }
            
            # Actualizamos el lote maestro
            batch.estado = 'ROLLED_BACK'
            # No sobrescribimos el log anterior, lo anexamos
            if isinstance(batch.log_errores, list):
                batch.log_errores.append(reporte_final)
            else:
                batch.log_errores = [reporte_final]
                
            batch.save(update_fields=['estado', 'log_errores'])

        logger.info(f"✅ [ROLLBACK-SUCCESS] Lote {batch_id}. Deleted: {stats['deleted']}, Restored: {stats['restored']} in {duration_ms}ms")
        
        return stats
