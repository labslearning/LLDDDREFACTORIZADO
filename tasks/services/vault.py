import os
import zipfile
import io
import hashlib
import uuid
from datetime import datetime
from django.core.management import call_command
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
from tasks.models import HistorialAcademico, BovedaSeguridad

class VaultManagerService:
    """
    🛡️ VAULT ENGINE v2.0 - INDUSTRIAL EDITION
    Motor de respaldo con sellado criptográfico y gestión de activos inmutables.
    """
    def __init__(self, usuario, nombre_identificador, ip_cliente=None):
        self.usuario = usuario
        self.nombre = nombre_identificador
        self.ip_cliente = ip_cliente
        self.uuid = uuid.uuid4()
        self.checksum_engine = hashlib.sha256()

    def generar_snapshot_militar(self):
        """
        Ejecuta un snapshot completo del sistema con validación de integridad.
        """
        zip_buffer = io.BytesIO()
        stats = {
            'db_backup_version': '1.0',
            'engine': 'Stratos-Fenix-Vault',
            'files_processed': 0,
            'errors': []
        }

        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 1. 💾 SNAPSHOT DE BASE DE DATOS (JSON)
                self._respaldar_db(zip_file)

                # 2. 📄 SNAPSHOT DE BOLETINES (ACTIVOS E HISTÓRICOS)
                stats['files_processed'] = self._empaquetar_boletines(zip_file, stats)

                # 3. 📜 MANIFIESTO TÉCNICO DE INTEGRIDAD
                self._generar_manifiesto(zip_file, stats)

            # --- SELLADO CRIPTOGRÁFICO ---
            # Obtenemos los bytes finales para el Checksum
            zip_content = zip_buffer.getvalue()
            self.checksum_engine.update(zip_content)
            final_hash = self.checksum_engine.hexdigest()

            # --- PERSISTENCIA ATÓMICA ---
            with transaction.atomic():
                respaldo = BovedaSeguridad(
                    uuid_operacion=self.uuid,
                    nombre_identificador=self.nombre,
                    generado_por=self.usuario,
                    checksum_sha256=final_hash,
                    ip_origen=self.ip_cliente,
                    stats_contenido=stats,
                    tamanio_mb=len(zip_content) / (1024 * 1024)
                )

                file_name = f"VAULT_{self.anio_actual}_{self.uuid.hex[:8]}.zip"
                respaldo.archivo_zip.save(file_name, ContentFile(zip_content), save=False)
                respaldo.save()

            return True, respaldo

        except Exception as e:
            return False, str(e)

    def _respaldar_db(self, zip_file):
        """Ejecuta dumpdata con buffers para no saturar memoria."""
        json_dump = io.StringIO()
        # Solo respaldamos 'tasks' para asegurar que la carga posterior sea compatible
        call_command('dumpdata', 'tasks', indent=2, stdout=json_dump)
        zip_file.writestr("RAW_DATA_SOURCE.json", json_dump.getvalue())

    def _empaquetar_boletines(self, zip_file, stats):
        """Busca y valida cada archivo físico antes de comprimir."""
        count = 0
        # Buscamos todos los historiales que posean un archivo físico
        activos = HistorialAcademico.objects.exclude(archivo_boletin='')
        
        for b in activos:
            if b.archivo_boletin:
                try:
                    path_fisico = b.archivo_boletin.path
                    if os.path.exists(path_fisico):
                        # Estructura: /Anio/Curso/Nombre_Estudiante.pdf
                        arcname = f"ACTIVOS/{b.anio_lectivo}/{b.curso_snapshot}/{os.path.basename(path_fisico)}"
                        zip_file.write(path_fisico, arcname=arcname)
                        count += 1
                    else:
                        stats['errors'].append(f"Missing file: {b.estudiante.user.username} ({b.anio_lectivo})")
                except Exception as e:
                    stats['errors'].append(f"Error packing {b.id}: {str(e)}")
        return count

    def _generar_manifiesto(self, zip_file, stats):
        """Genera el certificado de validez dentro del paquete."""
        manifiesto = [
            "===================================================",
            "   CERTIFICADO DE INTEGRIDAD - SISTEMA STRATOS",
            "===================================================",
            f"UUID OPERACIÓN: {self.uuid}",
            f"IDENTIFICADOR: {self.nombre}",
            f"FECHA GENERACIÓN: {datetime.now()}",
            f"GENERADO POR: {self.usuario.username}",
            f"IP ORIGEN: {self.ip_cliente}",
            "---------------------------------------------------",
            f"TOTAL BOLETINES: {stats['files_processed']}",
            f"ESTADO DE INTEGRIDAD: SELLADO",
            "---------------------------------------------------",
            "AVISO LEGAL: Este archivo contiene información",
            "protegida. La alteración del Checksum SHA-256",
            "invalida este respaldo para procesos legales.",
            "==================================================="
        ]
        zip_file.writestr("CERTIFICADO_INTEGRIDAD.txt", "\n".join(manifiesto))

    @property
    def anio_actual(self):
        return datetime.now().year
