import logging
import pandas as pd
import numpy as np
import json
import traceback
import re
from django.db import transaction, DatabaseError
from django.conf import settings
from django.contrib.auth.models import User
from tasks.models import ImportBatch, StagingRow, Perfil, HistorialAcademico

# Logger optimizado para producción
logger = logging.getLogger(__name__)

class ImportService:
    """
    🏭 MOTOR DE INGESTA DE DATOS V11 (POSTGRES COMPLIANT)
    
    Corrección Crítica:
    - Manejo de JSONField: Se usa dict vacío {} en lugar de None para limpiar errores,
      cumpliendo con la restricción NOT NULL de PostgreSQL.
    """

    def create_batch(self, file_obj, user, model_target: str) -> tuple[ImportBatch, list, list, dict]:
        """FASE 1: INGESTA DE ALTO RENDIMIENTO"""
        try:
            # Estrategia de lectura defensiva
            if file_obj.name.lower().endswith('.csv'):
                try:
                    df = pd.read_csv(file_obj, encoding='utf-8', on_bad_lines='skip', dtype=str)
                except UnicodeDecodeError:
                    file_obj.seek(0)
                    df = pd.read_csv(file_obj, encoding='latin-1', on_bad_lines='skip', dtype=str)
            else:
                # Engine optimizado para Excel moderno
                df = pd.read_excel(file_obj, dtype=str, engine='openpyxl')
        except Exception as e:
            logger.critical(f"FATAL: Error I/O: {traceback.format_exc()}")
            raise ValueError(f"Archivo corrupto: {str(e)}")

        # Higiene de Datos
        df.dropna(how='all', inplace=True)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = df.columns.str.strip().str.upper()
        df = df.replace({np.nan: None, 'nan': None, 'NaN': None})

        total_rows = len(df)
        if total_rows == 0: raise ValueError("Archivo vacío.")

        columns = list(df.columns)
        records = df.to_dict('records')

        with transaction.atomic():
            batch = ImportBatch.objects.create(
                usuario=user, archivo_original=file_obj, nombre_archivo=file_obj.name,
                tipo_modelo=model_target, total_filas=total_rows, estado='MAPPING'
            )
            
            # Inserción por lotes (Batch Insert)
            batch_size = 2000
            for i in range(0, total_rows, batch_size):
                chunk = records[i:i + batch_size]
                staging_instances = [
                    StagingRow(
                        batch=batch, numero_fila=base_idx + 1,
                        data_original={k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()},
                        es_valido=False,
                        errores={} # Inicializamos con dict vacío para evitar problemas
                    ) for base_idx, row in enumerate(chunk, start=i)
                ]
                StagingRow.objects.bulk_create(staging_instances)

        suggestions = self._generate_suggestions(columns)
        return batch, columns, records[:5], suggestions

    def execute_import(self, batch_id: str, mapping: dict, target_year: int) -> int:
        """FASE 2: TRANSFORMACIÓN Y AUTO-CREACIÓN"""
        try:
            batch = ImportBatch.objects.get(id=batch_id)
        except ImportBatch.DoesNotExist: raise ValueError("Lote no existe.")

        # --- 1. CONFIGURACIÓN DEL MAPEO ---
        col_id = next((k for k, v in mapping.items() if v == 'CODIGO_ESTUDIANTE'), None)
        col_subj = next((k for k, v in mapping.items() if v == 'DYNAMIC_SUBJECT_NAME'), None)
        col_grade = next((k for k, v in mapping.items() if v == 'DYNAMIC_GRADE_VALUE'), None)
        
        col_att = next((k for k, v in mapping.items() if v == 'DYNAMIC_ATTENDANCE'), None)
        col_obs = next((k for k, v in mapping.items() if v == 'DYNAMIC_OBSERVATION'), None)
        col_period = next((k for k, v in mapping.items() if v == 'FIELD_PERIOD'), None)
        col_name = next((k for k, v in mapping.items() if v == 'FIELD_NAME'), None)
        col_surname = next((k for k, v in mapping.items() if v == 'FIELD_SURNAME'), None)

        is_vertical_mode = bool(col_subj and col_grade)
        if not col_id: raise ValueError("Falta mapear ID_ESTUDIANTE.")

        processed_count = 0
        error_count = 0
        aggregated_data = {}
        
        rows = batch.filas_staging.filter(es_valido=False).iterator()

        print(f"\n--- 🚀 INICIANDO INGESTA (FIX POSTGRES) - Batch {batch_id} ---")

        with transaction.atomic():
            batch.estado = 'IMPORTING'
            batch.save()

            for row in rows:
                try:
                    raw = row.data_original
                    uid_raw = raw.get(col_id)
                    
                    if not uid_raw:
                        self._log_error(row, "Fila saltada: ID vacío.")
                        error_count += 1
                        continue

                    # --- A. LIMPIEZA NUCLEAR DE ID ---
                    clean_id = self._normalize_id(uid_raw)

                    if clean_id not in aggregated_data:
                        # --- B. BÚSQUEDA ---
                        estudiante = self._find_student(clean_id)

                        # --- C. AUTO-CREACIÓN (MODO DIOS) ---
                        if not estudiante:
                            # print(f"⚠️ Creando nuevo estudiante: {clean_id}")
                            estudiante = self._create_student(clean_id, raw, col_name, col_surname)
                            
                            if not estudiante:
                                self._log_error(row, f"Error creando usuario {clean_id}. Verifica logs.")
                                error_count += 1
                                continue

                        # --- D. ACTUALIZACIÓN PERFIL ---
                        if col_name or col_surname:
                            self._update_profile(estudiante, raw, col_name, col_surname)

                        aggregated_data[clean_id] = {
                            'student': estudiante,
                            'grades': {},
                            'rows': []
                        }

                    aggregated_data[clean_id]['rows'].append(row.id)

                    # --- E. PARSING DE NOTAS ---
                    if is_vertical_mode:
                        self._parse_vertical(aggregated_data[clean_id]['grades'], raw, col_subj, col_grade, col_att, col_obs, col_period)
                    else:
                        self._parse_horizontal(aggregated_data[clean_id]['grades'], raw, mapping)

                except Exception as e:
                    self._log_error(row, f"Error procesando fila: {str(e)}")
                    error_count += 1

            # --- 3. PERSISTENCIA FINAL ---
            valid_ids = []
            
            for uid, data in aggregated_data.items():
                if not data['grades']: 
                    processed_count += 1
                    continue 
                
                try:
                    HistorialAcademico.objects.update_or_create(
                        estudiante=data['student'],
                        anio_lectivo=target_year,
                        defaults={
                            'nombre_institucion': 'Importación Masiva',
                            'calificaciones_json': data['grades'],
                            'is_active': True,
                            'lote_origen': batch
                        }
                    )
                    processed_count += 1
                    valid_ids.extend(data['rows'])
                except Exception as e:
                    logger.error(f"Error persistencia {uid}: {e}")
                    error_count += 1

            # --- CORRECCIÓN CRÍTICA AQUÍ ---
            # Antes: update(..., errores=None) -> Crash en Postgres
            # Ahora: update(..., errores={}) -> Correcto para JSONField
            if valid_ids:
                StagingRow.objects.filter(id__in=valid_ids).update(es_valido=True, errores={})

            batch.filas_procesadas = processed_count + error_count
            batch.filas_exitosas = processed_count
            batch.filas_con_error = error_count
            
            # Lógica de Estado Final
            if processed_count == 0 and error_count > 0:
                batch.estado = 'FAILED'
            elif error_count > 0:
                batch.estado = 'PARTIAL_SUCCESS'
            else:
                batch.estado = 'COMPLETED'
                
            batch.save()
            print(f"--- 🏁 FIN: Éxitos={processed_count} | Errores={error_count} ---")

        return processed_count

    # --- FUNCIONES DE SOPORTE ---

    def _create_student(self, clean_id, raw, col_name, col_surname):
        """Crea Usuario y Perfil (Sin romper campos inexistentes)"""
        try:
            first_name = str(raw.get(col_name, 'Estudiante')).strip() if col_name else 'Estudiante'
            last_name = str(raw.get(col_surname, clean_id)).strip() if col_surname else clean_id
            
            # 1. Crear User Django
            user, created = User.objects.get_or_create(
                username=clean_id,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f"{clean_id}@sistema.edu"
                }
            )
            
            if not created:
                # Actualizar nombres si ya existía el usuario pero no el perfil
                if user.first_name != first_name or user.last_name != last_name:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
            else:
                user.set_password(clean_id)
                user.save()

            # 2. Crear Perfil (SOLO campos válidos)
            perfil, _ = Perfil.objects.get_or_create(
                user=user,
                defaults={
                    'numero_documento': clean_id,
                    'rol': 'Estudiante'
                }
            )
            return perfil
        except Exception as e:
            logger.error(f"Error creando usuario {clean_id}: {e}")
            return None

    def _update_profile(self, student, raw, col_name, col_surname):
        """Actualiza User a través del Perfil"""
        try:
            user = student.user 
            changed = False
            
            if col_name and raw.get(col_name):
                n = str(raw.get(col_name)).strip()
                if user.first_name != n: 
                    user.first_name = n
                    changed = True
            
            if col_surname and raw.get(col_surname):
                s = str(raw.get(col_surname)).strip()
                if user.last_name != s: 
                    user.last_name = s
                    changed = True
            
            if changed: 
                user.save() 
        except Exception as e:
            logger.warning(f"Error actualizando perfil {student}: {e}")

    def _normalize_id(self, val):
        s = str(val).strip().upper()
        if s.endswith('.0'): s = s[:-2]
        if s.replace('.', '').isdigit(): s = s.replace('.', '')
        return s

    def _find_student(self, clean_id):
        est = Perfil.objects.filter(numero_documento=clean_id).first()
        if not est:
            est = Perfil.objects.filter(user__username=clean_id).first()
        return est

    def _parse_vertical(self, grades, raw, subj_col, grade_col, att_col, obs_col, per_col):
        subj = raw.get(subj_col)
        val = raw.get(grade_col)
        if subj and val:
            clean_val = self._clean_grade(val)
            clean_subj = str(subj).strip().title()
            if clean_val is not None:
                payload = {'valor': clean_val}
                if att_col: payload['fallas'] = str(raw.get(att_col, '')).strip()
                if obs_col: payload['observacion'] = str(raw.get(obs_col, '')).strip()
                if per_col: payload['periodo'] = str(raw.get(per_col, '')).strip()
                grades[clean_subj] = payload

    def _parse_horizontal(self, grades, raw, mapping):
        for csv_col, sys_field in mapping.items():
            if sys_field.startswith('MATERIA:'):
                subj = sys_field.replace('MATERIA:', '')
                val = self._clean_grade(raw.get(csv_col))
                if val is not None:
                    grades[subj] = val

    def _log_error(self, row, msg):
        try:
            row.errores = {'msg': msg} # Dict, no None
            row.es_valido = False
            row.save(update_fields=['errores', 'es_valido'])
        except: pass

    def _clean_grade(self, val):
        if val is None: return None
        s = str(val).strip().replace(',', '.')
        if not s: return None
        try: return float(s)
        except: return s

    def _generate_suggestions(self, columns: list) -> dict:
        sug = {}
        keywords = {
            'CODIGO_ESTUDIANTE': ['id', 'documento', 'código', 'codigo'],
            'FIELD_NAME': ['nombre', 'nombres'],
            'FIELD_SURNAME': ['apellido', 'apellidos'],
            'DYNAMIC_SUBJECT_NAME': ['materia', 'asignatura'],
            'DYNAMIC_GRADE_VALUE': ['nota', 'valor'],
            'DYNAMIC_ATTENDANCE': ['falla'],
            'DYNAMIC_OBSERVATION': ['obs'],
            'FIELD_PERIOD': ['periodo']
        }
        for col in columns:
            c = col.lower()
            for k, words in keywords.items():
                if any(w in c for w in words):
                    sug[col] = k; break
        return sug