import sys
import time
from typing import Dict, Any, Tuple
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import QuerySet
from tasks.models import Nota, DefinicionNota, NotaDetallada

class Command(BaseCommand):
    help = 'Migración Enterprise: Transforma notas legacy (columnas fijas) al sistema relacional dinámico Tier 500k.'

    # Configuración de Mapeo (Extraterrestre)
    CONFIGURACION_PESOS: Dict[int, Dict[str, Any]] = {
        1: {'nombre': 'Corte 1 (Migrado)', 'porcentaje': 20, 'orden': 1},
        2: {'nombre': 'Corte 2 (Migrado)', 'porcentaje': 30, 'orden': 2},
        3: {'nombre': 'Corte 3 (Migrado)', 'porcentaje': 30, 'orden': 3},
        4: {'nombre': 'Evaluación Final (Migrada)', 'porcentaje': 20, 'orden': 4},
    }

    def print_progress_bar(self, iteration: int, total: int, prefix: str = '', suffix: str = '', decimals: int = 1, length: int = 50, fill: str = '█'):
        """
        Genera una barra de progreso visual en la terminal sin dependencias externas.
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filled_length = int(length * iteration // total)
        bar = fill * filled_length + '-' * (length - filled_length)
        sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
        sys.stdout.flush()
        if iteration == total:
            sys.stdout.write('\n')

    def handle(self, *args: Any, **kwargs: Any) -> None:
        start_time = time.time()
        self.stdout.write(self.style.HTTP_INFO('🚀 INICIANDO MIGRACIÓN "TIER 500K"'))
        self.stdout.write('--------------------------------------------------')

        # 1. QuerySet Optimizado
        # Usamos filter() para traer solo lo útil y select_related para evitar N+1
        notas_viejas_qs: QuerySet[Nota] = Nota.objects.filter(
            numero_nota__in=self.CONFIGURACION_PESOS.keys()
        ).select_related('materia', 'periodo', 'estudiante')
        
        total_registros = notas_viejas_qs.count()
        self.stdout.write(f"📊 Registros detectados: {total_registros}")

        contador_creadas = 0
        errores = 0
        
        # Cache local para evitar miles de consultas get_or_create a DefinicionNota
        # Key: (materia_id, periodo_id, orden) -> Value: DefinicionNota object
        definiciones_cache: Dict[Tuple[int, int, int], DefinicionNota] = {}

        # 2. Procesamiento Atómico y por Lotes
        # chunk_size=2000 protege la RAM. iterator() evita cargar todo en memoria.
        with transaction.atomic():
            self.print_progress_bar(0, total_registros, prefix='Progreso:', suffix='Completado', length=40)

            for i, nota_old in enumerate(notas_viejas_qs.iterator(chunk_size=2000), 1):
                try:
                    num = nota_old.numero_nota
                    
                    if num in self.CONFIGURACION_PESOS:
                        config = self.CONFIGURACION_PESOS[num]
                        
                        # A. Gestión de Definición (Cache-First)
                        key_def = (nota_old.materia_id, nota_old.periodo_id, config['orden'])
                        
                        if key_def not in definiciones_cache:
                            # Solo golpeamos la DB si no está en memoria
                            definicion, _ = DefinicionNota.objects.get_or_create(
                                materia_id=nota_old.materia_id,
                                periodo_id=nota_old.periodo_id,
                                orden=config['orden'],
                                defaults={
                                    'nombre': config['nombre'],
                                    'porcentaje': config['porcentaje'],
                                    'temas': 'Contenido migrado automáticamente',
                                    'subtemas': ''
                                }
                            )
                            definiciones_cache[key_def] = definicion
                        
                        definicion_actual = definiciones_cache[key_def]

                        # B. Migración del Dato (Idempotente)
                        # update_or_create garantiza que si corres esto 2 veces, no duplicas notas.
                        NotaDetallada.objects.update_or_create(
                            definicion=definicion_actual,
                            estudiante_id=nota_old.estudiante_id,
                            defaults={
                                'valor': nota_old.valor,
                                'registrado_por_id': nota_old.registrado_por_id
                            }
                        )
                        contador_creadas += 1

                except Exception as e:
                    errores += 1
                    # Logueamos el error pero no detenemos la migración masiva
                    self.stdout.write(self.style.ERROR(f"\n[!] Error en Nota ID {nota_old.id}: {str(e)}"))

                # Actualizar barra cada 50 items para no ralentizar la consola
                if i % 50 == 0 or i == total_registros:
                    self.print_progress_bar(i, total_registros, prefix='Procesando:', suffix=f'({i}/{total_registros})', length=40)

        # 3. Reporte Final
        end_time = time.time()
        duration = end_time - start_time
        
        self.stdout.write('\n--------------------------------------------------')
        if errores == 0:
            self.stdout.write(self.style.SUCCESS(f'✅ MIGRACIÓN EXITOSA'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ MIGRACIÓN FINALIZADA CON {errores} ERRORES'))
        
        self.stdout.write(f"📝 Notas migradas: {contador_creadas}")
        self.stdout.write(f"⏱️ Tiempo total: {duration:.2f} segundos")
        self.stdout.write(f"🚀 Velocidad: {contador_creadas / duration:.0f} notas/seg")
        self.stdout.write('--------------------------------------------------')