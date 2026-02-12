# tasks/management/commands/registrar_profes.py
import os
import django
from django.core.management.base import BaseCommand
from django.db import transaction

# La configuración de Django ya se maneja al ejecutar el comando
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangocrud.settings")
# django.setup()

from django.contrib.auth.models import User
from tasks.models import Perfil, Curso, Materia, AsignacionMateria

class Command(BaseCommand):
    help = 'Registra profesores y asigna materias a cursos.'

    def handle(self, *args, **options):
        materias_base = [
            "Matemáticas", "Lengua Castellana", "Inglés", "Ciencias Naturales",
            "Sociales", "Educación Física", "Arte", "Tecnología"
        ]
        anio_escolar = "2025-2026"

        with transaction.atomic():
            self.stdout.write(self.style.SUCCESS("Iniciando registro de profesores y materias..."))

            cursos = Curso.objects.filter(anio_escolar=anio_escolar)
            if not cursos.exists():
                self.stdout.write(self.style.ERROR("❌ No se encontraron cursos para el año escolar 2025-2026. Por favor, cree los cursos primero."))
                return

            for curso in cursos:
                for materia_nombre in materias_base:
                    materia, _ = Materia.objects.get_or_create(nombre=materia_nombre, curso=curso)

                    username = f"prof_{curso.grado}_{materia_nombre.lower().replace(' ', '_')}"
                    email = f"{username}@colegio.com"

                    user, created = User.objects.get_or_create(username=username, defaults={
                        "email": email,
                        "first_name": "Profesor",
                        "last_name": materia_nombre,
                    })

                    user.set_password("123456")
                    user.is_active = True
                    user.save()

                    # Corregido: El campo 'curso' no pertenece a Perfil.
                    perfil, _ = Perfil.objects.update_or_create(
                        user=user,
                        defaults={"rol": "DOCENTE"}
                    )

                    asignacion, _ = AsignacionMateria.objects.get_or_create(
                        materia=materia,
                        curso=curso,
                        docente=user,
                        defaults={"periodo_academico": "2025-1"}
                    )

                    self.stdout.write(self.style.SUCCESS(f"✅ Profesor {username} asignado a {materia_nombre} en {curso.nombre}"))

        self.stdout.write(self.style.SUCCESS("\n✅ Registro de profesores y materias completado exitosamente."))