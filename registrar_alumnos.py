# your_app/management/commands/registrar_alumnos.py
import os
import django
import random
from django.core.management.base import BaseCommand
from django.db import transaction

# Django setup is not needed for a management command
from django.contrib.auth.models import User
from tasks.models import Perfil, Curso, Materia, AsignacionMateria, Matricula, Periodo, Nota, GRADOS_CHOICES

class Command(BaseCommand):
    help = 'Registers students and their initial assignments in the system.'

    def handle(self, *args, **options):
        nombres = ["Juan", "María", "Carlos", "Ana", "Pedro", "Luisa", "Sofía", "Andrés", "Camila", "Felipe"]
        apellidos = ["Gómez", "Rodríguez", "Martínez", "López", "Pérez", "Ramírez", "Torres", "Hernández", "Vargas", "Castro"]
        anio_escolar = "2025-2026"
        notas_base = [
            (1, "Quiz", 20),
            (2, "Examen", 30),
            (3, "Proyecto", 30),
            (4, "Sustentación", 20),
        ]
        
        with transaction.atomic():
            self.stdout.write(self.style.SUCCESS("Starting student registration..."))
            for grado_val, _ in GRADOS_CHOICES:
                for seccion in ["A", "B"]:
                    curso = Curso.objects.filter(grado=grado_val, seccion=seccion, anio_escolar=anio_escolar).first()
                    if not curso:
                        self.stdout.write(self.style.WARNING(f"⚠️ Course {grado_val}° {seccion} does not exist, skipping student creation for this course."))
                        continue

                    for i in range(1, 21):
                        nombre = random.choice(nombres)
                        apellido = random.choice(apellidos)
                        username = f"alum_{grado_val}_{seccion}_{i}".lower()
                        email = f"{username}@colegio.com"

                        user, created = User.objects.get_or_create(
                            username=username,
                            defaults={
                                "password": "123456",
                                "email": email,
                                "first_name": nombre,
                                "last_name": apellido
                            }
                        )

                        if created:
                            # Corrected: 'curso' is not a valid argument for Perfil.
                            perfil, _ = Perfil.objects.get_or_create(user=user, defaults={"rol": "ESTUDIANTE"})
                            Matricula.objects.get_or_create(estudiante=user, curso=curso, anio_escolar=anio_escolar, defaults={"activo": True})
                            self.stdout.write(self.style.SUCCESS(f"✅ Student {nombre} {apellido} ({username}) registered in {curso.nombre}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"⏩ Student {username} already exists, checking course assignment."))
                            Matricula.objects.get_or_create(estudiante=user, curso=curso, anio_escolar=anio_escolar, defaults={"activo": True})

                        # Create notes for each subject and period
                        for materia in Materia.objects.filter(curso=curso):
                            for periodo in Periodo.objects.filter(curso=curso):
                                for numero_nota, descripcion, peso in notas_base:
                                    Nota.objects.get_or_create(
                                        estudiante=user,
                                        materia=materia,
                                        periodo=periodo,
                                        numero_nota=numero_nota,
                                        defaults={"valor": 0, "descripcion": f"{descripcion} ({peso}%)"}
                                    )
            self.stdout.write(self.style.SUCCESS("\n✅ Student registration completed successfully."))