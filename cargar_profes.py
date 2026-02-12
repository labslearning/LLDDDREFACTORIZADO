# from django.contrib.auth.models import User
# from tasks.models import Perfil, Curso, Materia, AsignacionMateria

# Definimos materias base
materias_base = [
    "Matemáticas", "Lengua Castellana", "Inglés", "Ciencias Naturales",
    "Sociales", "Educación Física", "Arte", "Tecnología"
]

anio_escolar = "2025-2026"

# Crear cursos 6° a 11°
cursos = []
for grado in ["6", "7", "8", "9", "10", "11"]:
    curso, created = Curso.objects.get_or_create(
        grado=grado,
        seccion="A",
        anio_escolar=anio_escolar,
        defaults={
            "nombre": f"{grado}° A",
            "descripcion": f"Curso de {grado}° grado",
            "capacidad_maxima": 40,
        }
    )
    cursos.append(curso)

# Crear docentes y asignar materias
for curso in cursos:
    for materia_nombre in materias_base:
        # Crear materia si no existe
        materia, _ = Materia.objects.get_or_create(nombre=materia_nombre, curso=curso)

        # Crear usuario profesor
        username = f"prof_{curso.grado}_{materia_nombre.lower().replace(' ', '_')}"
        email = f"{username}@colegio.com"

        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(username=username, password="123456", email=email)
            Perfil.objects.create(user=user, rol="DOCENTE") # ✅ Campo 'curso' eliminado
        else:
            user = User.objects.get(username=username)

        # Asignación de materia al profesor
        AsignacionMateria.objects.get_or_create(
            materia=materia,
            curso=curso,
            docente=user,
            periodo_academico="2025-1",
        )

        print(f"✅ Profesor {username} asignado a {materia_nombre} en {curso.nombre}")