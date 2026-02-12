from django.contrib.auth.models import User
from tasks.models import Perfil, Curso, Materia, AsignacionMateria, Matricula, Periodo, Nota

# Obtener el curso 6° A
curso = Curso.objects.filter(grado="6", seccion="A", anio_escolar="2025-2026").first()
if curso:
    print(f"Eliminando curso: {curso}")

    # Eliminar notas de los alumnos matriculados en este curso
    matriculas = Matricula.objects.filter(curso=curso)
    for matricula in matriculas:
        Nota.objects.filter(estudiante=matricula.estudiante).delete()

    # Eliminar matrículas de los alumnos
    Matricula.objects.filter(curso=curso).delete()

    # Eliminar asignaciones de materias
    AsignacionMateria.objects.filter(curso=curso).delete()

    # Eliminar materias del curso
    Materia.objects.filter(curso=curso).delete()

    # Eliminar períodos del curso
    Periodo.objects.filter(curso=curso).delete()

    # Eliminar perfiles de los alumnos
    perfiles = Perfil.objects.filter(curso=curso)
    for perfil in perfiles:
        perfil.delete()

    # Eliminar usuarios de los alumnos
    usuarios = User.objects.filter(perfil__curso=curso)
    for usuario in usuarios:
        usuario.delete()

    # Eliminar el curso
    curso.delete()
    print("Curso 6° A eliminado correctamente.")
else:
    print("No se encontró el curso 6° A.")
