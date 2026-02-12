import random
import logging
import time
from typing import Dict, List, Any
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.apps import apps  # Para carga dinámica de modelos
from faker import Faker

# Importa tus modelos base
from tasks.models import Perfil, HistorialAcademico, ImportBatch

# Configuración de Logging
logger = logging.getLogger(__name__)
fake = Faker(['es_CO'])

class Command(BaseCommand):
    help = 'Sembrador de Datos Enterprise: Genera un ecosistema escolar completo con perfiles psicológicos.'

    # ==========================================
    # ⚙️ CONFIGURACIÓN MAESTRA
    # ==========================================
    MATERIAS = [
        'Matemáticas', 'Español', 'Inglés', 'Ciencias Naturales', 
        'Ciencias Sociales', 'Física', 'Química', 'Educación Física', 
        'Ética', 'Religión', 'Artes', 'Tecnología'
    ]
    
    # Arquetipos para dar realismo a la data
    ARQUETIPOS = {
        'EXCELENCIA': {'notas': (4.5, 5.0), 'disciplina': 0.05}, # 5% prob de falta
        'PROMEDIO':   {'notas': (3.5, 4.4), 'disciplina': 0.20}, # 20% prob de falta
        'RIESGO':     {'notas': (1.0, 3.4), 'disciplina': 0.60}, # 60% prob de falta
        'DEPORTISTA': {'notas': (2.8, 4.0), 'disciplina': 0.15, 'boost': 'Educación Física'}
    }

    FALTAS_DISCIPLINARIAS = [
        ("Llegada tarde reiterada", "LEVE"),
        ("Uso de celular en clase", "LEVE"),
        ("Porte inadecuado del uniforme", "LEVE"),
        ("Interrupción constante de clase", "LEVE"),
        ("Agresión verbal a compañero", "GRAVE"),
        ("Daño a recursos de la institución", "GRAVE"),
        ("Falta de respeto a autoridad", "GRAVE"),
        ("Fraude en evaluación académica", "GRAVISIMA"),
        ("Agresión física", "GRAVISIMA")
    ]

    def add_arguments(self, parser):
        """Permite parámetros desde la terminal"""
        parser.add_argument('--total', type=int, default=50, help='Número de estudiantes a crear')
        parser.add_argument('--delete', action='store_true', help='Borrar datos anteriores antes de crear nuevos')
        parser.add_argument('--anio', type=int, default=2024, help='Año lectivo para los historiales')

    def handle(self, *args, **kwargs):
        total_students = kwargs['total']
        should_delete = kwargs['delete']
        anio_lectivo = kwargs['anio']

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n🚀 INICIANDO PROTOCOLO DE GENERACIÓN DE DATOS v2.0'))
        self.stdout.write(f"   Objetivo: {total_students} Estudiantes | Año: {anio_lectivo}")

        # Intentar cargar modelo de Observación dinámicamente
        ObservacionModel = None
        try:
            # Ajusta 'tasks' y 'Observacion' si se llaman diferente
            ObservacionModel = apps.get_model('tasks', 'Observacion')
            self.stdout.write(self.style.SUCCESS("   ✅ Modelo 'Observacion' detectado e integrado."))
        except LookupError:
            self.stdout.write(self.style.WARNING("   ⚠️ Modelo 'Observacion' no encontrado. Se omitirá la disciplina."))

        with transaction.atomic():
            # 1. Limpieza (Opcional)
            if should_delete:
                self.stdout.write(self.style.WARNING("   🗑️  Eliminando datos anteriores..."))
                # Eliminamos solo estudiantes creados por este script (para no borrar admins reales)
                User.objects.filter(email__contains="@colegio.edu.co").delete()
                ImportBatch.objects.filter(tipo_modelo="SIMULACION").delete()

            # 2. Admin System User
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                self.stdout.write(self.style.ERROR('   ❌ Error Crítico: No existe un superusuario. Crea uno con createsuperuser.'))
                return

            # 3. Lote Maestro
            lote = ImportBatch.objects.create(
                usuario=admin_user,
                nombre_archivo=f"DATA_SEED_{anio_lectivo}_GEN.sys",
                tipo_modelo="SIMULACION",
                estado="COMPLETED",
                total_filas=total_students,
                filas_procesadas=total_students,
                filas_exitosas=total_students
            )

            # 4. Bucle de Generación
            self.stdout.write("   ⚡ Generando perfiles...")
            
            # Variables para barra de progreso simple
            progress_step = max(1, total_students // 10)
            
            for i in range(1, total_students + 1):
                # A. Selección de Arquetipo
                tipo_perfil = random.choices(
                    list(self.ARQUETIPOS.keys()), 
                    weights=[15, 60, 15, 10] # Distribución de probabilidad
                )[0]
                config_perfil = self.ARQUETIPOS[tipo_perfil]

                # B. Identidad
                sexo = random.choice(['M', 'F'])
                nombre = fake.first_name_male() if sexo == 'M' else fake.first_name_female()
                apellido = fake.last_name()
                
                # Username único con timestamp para evitar colisiones en limpiezas repetidas
                suffix = int(time.time() * 1000) % 100000
                username = f"est.{nombre[:3].lower()}{apellido[:3].lower()}.{suffix}"
                email = f"{username}@colegio.edu.co"

                # C. Persistencia User/Perfil
                user = User.objects.create_user(username=username, email=email, password='password123')
                user.first_name = nombre
                user.last_name = apellido
                user.save()

                perfil, _ = Perfil.objects.get_or_create(user=user)
                perfil.numero_documento = str(random.randint(10000000, 99999999))
                perfil.tipo_usuario = 'ESTUDIANTE'
                perfil.save()

                # D. Generación de Notas (Basado en Arquetipo)
                notas = {}
                meta = {}
                rango_min, rango_max = config_perfil['notas']

                for materia in self.MATERIAS:
                    # Lógica especial para deportistas
                    if tipo_perfil == 'DEPORTISTA' and materia == config_perfil.get('boost'):
                        nota = round(random.uniform(4.5, 5.0), 1)
                    else:
                        # Variación natural
                        nota = round(random.uniform(rango_min, rango_max), 1)
                        # Ocasional "accidente" (un genio puede sacar un 3.0)
                        if random.random() < 0.1: 
                            nota = round(random.uniform(2.5, 3.5), 1)
                    
                    notas[materia] = nota
                    meta[materia] = str(nota)

                # E. Guardar Historial
                HistorialAcademico.objects.create(
                    estudiante=perfil,
                    anio_lectivo=anio_lectivo,
                    nombre_institucion="Colegio San Simulador",
                    calificaciones_json=notas,
                    meta_confianza=meta,
                    lote_origen=lote,
                    is_active=True
                )

                # F. Generación de Disciplina (Si el modelo existe)
                if ObservacionModel and random.random() < config_perfil['disciplina']:
                    num_faltas = random.randint(1, 4) if tipo_perfil == 'RIESGO' else 1
                    for _ in range(num_faltas):
                        falta, severidad = random.choice(self.FALTAS_DISCIPLINARIAS)
                        
                        # Intentamos crear la observación dinámicamente
                        try:
                            ObservacionModel.objects.create(
                                estudiante=perfil,
                                titulo=f"Reporte de Convivencia - {severidad}",
                                descripcion=f"El estudiante comete la falta: {falta}. {fake.sentence()}",
                                tipo_falta=severidad, # Asegúrate que este campo exista en tu modelo
                                fecha=fake.date_between(start_date='-6m', end_date='today'),
                                creado_por=admin_user
                            )
                        except Exception:
                            pass # Si fallan los campos específicos, continuamos silenciosamente

                # Feedback Visual
                if i % progress_step == 0 or i == total_students:
                    percent = (i / total_students) * 100
                    self.stdout.write(f"   ... Procesando: {int(percent)}% ({i}/{total_students})")

        # RESUMEN FINAL
        self.stdout.write(self.style.SUCCESS('\n✨ PROCESO COMPLETADO EXITOSAMENTE ✨'))
        self.stdout.write(f"   ----------------------------------------")
        self.stdout.write(f"   👥 Estudiantes:  {total_students}")
        self.stdout.write(f"   📚 Notas:        Generadas con distribución estadística")
        self.stdout.write(f"   🔐 Password:     'password123' (para todos)")
        self.stdout.write(f"   🧬 Arquetipos:   Si")
        self.stdout.write(f"   📂 Lote ID:      {lote.id}")
        self.stdout.write(f"   ----------------------------------------")
