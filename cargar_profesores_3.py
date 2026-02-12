from django.contrib.auth.models import User
from tasks.models import Perfil

# Definimos lista base de materias (solo para generar nombres de profesores, no para crearlas en BD)
materias_base = [
    "Matemáticas", "Lengua Castellana", "Inglés", "Ciencias Naturales",
    "Sociales", "Educación Física", "Arte", "Tecnología"
]

# Grados en los que queremos profesores
grados = ["6", "7", "8", "9", "10", "11"]

# Crear usuarios docentes sin asignarlos a cursos/materias
for grado in grados:
    for materia in materias_base:
        username = f"prof_{grado}_{materia.lower().replace(' ', '_')}"
        email = f"{username}@colegio.com"

        if not User.objects.filter(username=username).exists():
            # Crear usuario con clave inicial 123456
            user = User.objects.create_user(
                username=username,
                password="123456",
                email=email,
                first_name="Profesor",
                last_name=f"{materia} {grado}"
            )
            # Crear perfil con rol DOCENTE
            Perfil.objects.create(user=user, rol="DOCENTE", requiere_cambio_clave=True)
            print(f"✅ Profesor creado: {username} ({materia}, grado {grado})")
        else:
            print(f"⚠️ Profesor {username} ya existe, omitido.")
