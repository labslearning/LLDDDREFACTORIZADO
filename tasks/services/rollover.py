# tasks/services/rollover.py

import os
import re
from datetime import datetime
from django.db import transaction
from django.conf import settings
from django.core.management import call_command
from django.core.files.base import ContentFile # Necesario para guardar el PDF en memoria
from tasks.models import User, Perfil, Curso, Nota, Asistencia, HistorialAcademico, CierreAnualLog, Periodo

# IMPORTANTE: Asegúrate de haber creado este archivo puente como acordamos
# Si tu función se llama diferente, ajusta esta línea.
try:
    from tasks.utils.pdf_bridge import generar_pdf_binario
except ImportError:
    # Fallback para que no rompa si aún no creas el archivo puente
    def generar_pdf_binario(*args): return b""

class YearRolloverService:
    """
    🦅 CLASE MAESTRA: PROTOCOLO FÉNIX (ENTERPRISE GRADE)
    Orquestador transaccional para el cierre de año escolar y transición de ciclo.
    Incluye generación de evidencia documental (PDFs) y Time Machine.
    """
    
    def __init__(self, anio_actual, usuario_ejecutor):
        self.anio_actual = int(anio_actual)
        self.anio_nuevo = self.anio_actual + 1
        self.usuario = usuario_ejecutor
        self.log_buffer = [] 
        self.stats = {"total": 0, "promovidos": 0, "reprobados": 0, "graduados": 0}

    def ejecutar_cierre(self):
        """Punto de entrada principal. Ejecuta las fases del protocolo de manera atómica."""
        self._log(f"🔥 INICIANDO PROTOCOLO FÉNIX: {self.anio_actual} -> {self.anio_nuevo}")
        
        try:
            # PASO 0: GENERAR BACKUP DE SEGURIDAD (Time Machine)
            # Crítico: Se hace ANTES de la transacción para asegurar persistencia en disco.
            archivo_backup_path = self._generar_backup_json()

            # BLOQUE ATÓMICO: Todo o Nada
            with transaction.atomic():
                
                # FASE 1: CONGELAMIENTO + GENERACIÓN DE PDFs
                # Aquí guardamos los datos Y los documentos antes de borrar nada.
                self._fase_congelamiento()
                
                # FASE 2: DECISIÓN (PROMOCIÓN AUTOMÁTICA)
                self._fase_decision()
                
                # FASE 3: LIMPIEZA (TIERRA QUEMADA)
                # Aquí se borran las notas. Si no generamos los PDFs antes, saldrían vacíos.
                self._fase_limpieza()
                
                # FASE 4: AUDITORÍA
                cierre_log = self._guardar_auditoria(exito=True, path_backup=archivo_backup_path)
            
            return True, "Protocolo Fénix ejecutado con éxito. Boletines generados y sistema reiniciado.", cierre_log.id

        except Exception as e:
            self._log(f"❌ ERROR CRÍTICO (ROLLBACK AUTOMÁTICO): {str(e)}")
            try:
                self._guardar_auditoria(exito=False)
            except:
                pass 
            return False, str(e), None

    # ---------------------------------------------------------
    # 💾 FASE 0: TIME MACHINE (BACKUP)
    # ---------------------------------------------------------
    def _generar_backup_json(self):
        self._log("💾 Generando punto de restauración (Time Machine)...")
        filename = f"restore_point_{self.anio_actual}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'security', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        full_path = os.path.join(backup_dir, filename)
        
        with open(full_path, 'w') as f:
            # Dumpeamos solo la app 'tasks'
            call_command('dumpdata', 'tasks', indent=2, stdout=f)
            
        self._log(f"✅ Punto de restauración creado en: {filename}")
        return os.path.join('security', 'backups', filename)

    # ---------------------------------------------------------
    # 🧊 FASE 1: CONGELAMIENTO + PDFs
    # ---------------------------------------------------------
    def _fase_congelamiento(self):
        self._log("🧊 Iniciando snapshot y generación masiva de boletines...")
        
        perfiles = Perfil.objects.filter(rol='ESTUDIANTE').select_related('user')
        count_procesados = 0
        
        for perfil in perfiles:
            # 1. Obtener datos académicos
            curso_actual = getattr(perfil, 'curso', None)
            nombre_curso = curso_actual.nombre if curso_actual else "Sin Asignar"
            
            notas = Nota.objects.filter(estudiante=perfil.user).select_related('materia')
            
            calificaciones_map = {}
            suma_notas = 0.0
            conteo_notas = 0
            materias_perdidas = 0
            
            for nota in notas:
                try:
                    valor = float(nota.valor)
                except (ValueError, TypeError):
                    valor = 0.0
                    
                calificaciones_map[nota.materia.nombre] = valor
                suma_notas += valor
                conteo_notas += 1
                if valor < 3.0: 
                    materias_perdidas += 1
            
            promedio = round(suma_notas / conteo_notas, 2) if conteo_notas > 0 else 0.0
            
            # 2. Crear Objeto Historial
            historial = HistorialAcademico(
                estudiante=perfil,
                anio_lectivo=self.anio_actual,
                curso_snapshot=nombre_curso,
                promedio_final=promedio,
                calificaciones_json=calificaciones_map,
                meta_confianza={
                    "materias_perdidas": materias_perdidas,
                    "total_asignaturas": conteo_notas,
                    "fecha_snapshot": str(datetime.now())
                },
                version=1,
                is_active=True,
                estado_final="PENDIENTE"
            )

            # 3. 🔥 GENERACIÓN DE PDF (BOLETÍN) 🔥
            # Esto debe ocurrir AQUI, mientras las notas existen en la DB
            try:
                # Llamada al puente que reutiliza tu lógica actual
                pdf_bytes = generar_pdf_binario(perfil.user.id, self.anio_actual)
                
                if pdf_bytes:
                    filename = f"Boletin_{self.anio_actual}_{perfil.user.username}.pdf"
                    # Guardamos el archivo en el campo FileField
                    historial.archivo_boletin.save(filename, ContentFile(pdf_bytes), save=False)
            except Exception as e:
                self._log(f"⚠️ Error generando boletín para {perfil.user}: {e}")
                # No detenemos el cierre por un PDF fallido, pero lo registramos

            # Guardamos el registro (con o sin PDF)
            historial.save()
            count_procesados += 1
        
        self._log(f"✅ {count_procesados} historiales y documentos archivados.")

    # ---------------------------------------------------------
    # ⚖️ FASE 2: MOTOR DE DECISIÓN
    # ---------------------------------------------------------
    def _fase_decision(self):
        self._log("⚖️ Ejecutando motor de reglas SIEE...")
        
        historiales = HistorialAcademico.objects.filter(anio_lectivo=self.anio_actual)
        self.stats['total'] = historiales.count()
        mapa_sucesion = self._construir_mapa_sucesion()
        
        for h in historiales:
            perfil = h.estudiante
            curso_actual = getattr(perfil, 'curso', None)
            
            if not curso_actual:
                self._log(f"⚠️ Estudiante {perfil} sin curso asignado. Omitiendo promoción.")
                continue

            materias_perdidas = h.meta_confianza.get('materias_perdidas', 0)
            promedio = h.promedio_final
            
            nuevo_estado = "REPROBADO"
            siguiente_curso = curso_actual
            
            nombre_curso = curso_actual.nombre.strip().upper()
            es_grado_once = "11" in nombre_curso or "ONCE" in nombre_curso or "UNDECIMO" in nombre_curso
            
            aprueba_anio = (promedio >= 3.0) and (materias_perdidas <= 2)
            
            if aprueba_anio:
                if es_grado_once:
                    nuevo_estado = "GRADUADO"
                    perfil.rol = "EX_ALUMNO"
                    siguiente_curso = None 
                    self.stats['graduados'] += 1
                else:
                    nuevo_estado = "PROMOVIDO"
                    siguiente_curso = mapa_sucesion.get(curso_actual.id, curso_actual)
                    self.stats['promovidos'] += 1
            else:
                self.stats['reprobados'] += 1
            
            perfil.curso = siguiente_curso
            perfil.save()
            
            h.estado_final = nuevo_estado
            h.save()

    # ---------------------------------------------------------
    # 🧹 FASE 3: LIMPIEZA (TIERRA QUEMADA)
    # ---------------------------------------------------------
    def _fase_limpieza(self):
        self._log("🧹 Iniciando limpieza de tablas operativas...")
        
        # Como ya generamos los PDFs en Fase 1, es seguro borrar esto
        n_notas, _ = Nota.objects.all().delete()
        self._log(f"🗑️ {n_notas} notas eliminadas.")
        
        n_asist, _ = Asistencia.objects.all().delete()
        self._log(f"🗑️ {n_asist} registros de asistencia eliminados.")
        
        Periodo.objects.update(activo=False)
        self._log("🔒 Periodos académicos desactivados.")

    # ---------------------------------------------------------
    # 🧠 UTILS (MAPA DE CURSOS & LOGS)
    # ---------------------------------------------------------
    def _construir_mapa_sucesion(self):
        mapa = {}
        cursos = Curso.objects.all()
        cursos_por_nombre = {c.nombre.strip().upper(): c for c in cursos}
        
        for curso in cursos:
            nombre = curso.nombre.strip().upper()
            siguiente = None
            
            # Lógica Numérica
            match = re.match(r"(\d+)", nombre)
            if match:
                try:
                    numero_str = match.group(1) 
                    nivel_actual = int(numero_str[0]) if len(numero_str) > 2 else int(numero_str)
                    
                    if nivel_actual == 9:
                        nivel_siguiente = 10
                        resto = nombre[1:]
                        nombre_buscado = f"{nivel_siguiente}{resto}"
                    elif nivel_actual >= 10:
                        nivel_siguiente = nivel_actual + 1
                        resto = nombre[2:]
                        nombre_buscado = f"{nivel_siguiente}{resto}"
                    else:
                        nivel_siguiente = nivel_actual + 1
                        nombre_buscado = f"{nivel_siguiente}{nombre[1:]}"
                    
                    if nombre_buscado in cursos_por_nombre:
                        siguiente = cursos_por_nombre[nombre_buscado]
                except: pass 
            
            # Lógica Texto
            secuencia = ["PARVULOS", "PREJARDIN", "JARDIN", "TRANSICION", "PRIMERO"]
            if nombre in secuencia:
                try:
                    idx = secuencia.index(nombre)
                    if idx + 1 < len(secuencia):
                        nombre_siguiente = secuencia[idx+1]
                        for c_nom, c_obj in cursos_por_nombre.items():
                            if nombre_siguiente in c_nom:
                                siguiente = c_obj
                                break
                except: pass

            mapa[curso.id] = siguiente if siguiente else curso
                
        return mapa

    def _log(self, msg):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_buffer.append(f"{timestamp} {msg}")
        print(f"[FENIX] {msg}")

    def _guardar_auditoria(self, exito, path_backup=None):
        return CierreAnualLog.objects.create(
            anio_cerrado=self.anio_actual,
            anio_nuevo=self.anio_nuevo,
            ejecutado_por=self.usuario,
            total_procesados=self.stats['total'],
            promovidos=self.stats['promovidos'],
            reprobados=self.stats['reprobados'],
            graduados=self.stats['graduados'],
            exitoso=exito,
            archivo_backup=path_backup,
            log_detalle="\n".join(self.log_buffer)
        )

# ==============================================================================
# ⏪ NUEVA CLASE: SERVICIO DE REVERSIÓN (TIME MACHINE)
# ==============================================================================
class ReverseProtocolService:
    """
    ⏳ TIME MACHINE: MOTOR DE REVERSIÓN
    Restaura la base de datos al estado exacto previo al cierre.
    """
    def __init__(self, log_id, usuario_ejecutor):
        self.log_cierre = CierreAnualLog.objects.get(id=log_id)
        self.usuario = usuario_ejecutor

    def ejecutar_reversion(self):
        if self.log_cierre.status == 'REVERTIDO':
            return False, "Este cierre ya fue revertido anteriormente."
            
        if not self.log_cierre.archivo_backup:
            return False, "❌ Error Fatal: No existe archivo de respaldo para este cierre. Imposible deshacer."

        try:
            with transaction.atomic():
                print("🧹 Eliminando historiales generados por el cierre...")
                # Borramos el registro de historial, pero los PDFs físicos se quedan en disco (por seguridad)
                HistorialAcademico.objects.filter(
                    anio_lectivo=self.log_cierre.anio_cerrado,
                    created_at__gte=self.log_cierre.fecha_ejecucion
                ).delete()
                
                print("🔥 Limpiando tablas operativas para restauración...")
                Nota.objects.all().delete()
                Asistencia.objects.all().delete()
                
                backup_path = self.log_cierre.archivo_backup.path
                if not os.path.exists(backup_path):
                    raise FileNotFoundError(f"El archivo de backup no se encuentra en disco: {backup_path}")
                
                print(f"⏳ Restaurando desde Time Machine: {backup_path}")
                call_command('loaddata', backup_path)
                
                self.log_cierre.status = 'REVERTIDO'
                self.log_cierre.log_detalle += f"\n\n[REVERSION] Ejecutada por {self.usuario.username} el {datetime.now()}\nSistema restaurado al estado original."
                self.log_cierre.save()
                
            return True, "✅ Sistema restaurado exitosamente al estado previo al cierre."
            
        except Exception as e:
            return False, f"❌ Fallo crítico en la restauración: {str(e)}"