from django.contrib.auth.models import User
from tasks.models import Perfil

# Lista de docentes iniciales con username y nombre completo
DOCENTES = [
    ("prof_matematicas", "Profesor de Matemáticas"),
    ("prof_lengua", "Profesor de Lengua Castellana"),
    ("prof_ingles", "Profesor de Inglés"),
    ("prof_ciencias", "Profesor de Ciencias Naturales"),
    ("prof_sociales", "Profesor de Sociales"),
    ("prof_edfisica", "Profesor de Educación Física"),
    ("prof_arte", "Profesor de Arte"),
    ("prof_tecnologia", "Profesor de Tecnología"),
]

# Clave inicial para todos los docentes
CLAVE_INICIAL = "12345"

creados = 0
existentes = 0

for username, nombre_completo in DOCENTES:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": nombre_completo.split(" ")[-1],  # último elemento como nombre
            "last_name": " ".join(nombre_completo.split(" ")[:-1]) or "Docente",  # resto como apellido
            "email": f"{username}@colegio.com",
        }
    )

    if created:
        # Asignar clave inicial
        user.set_password(CLAVE_INICIAL)
        user.save()

        # Crear perfil como DOCENTE
        Perfil.objects.get_or_create(
            user=user,
            defaults={
                "rol": "DOCENTE",
                "requiere_cambio_clave": True
            }
        )

        print(f"✅ Docente {nombre_completo} creado con usuario: {username}")
        creados += 1
    else:
        print(f"⚠️ El usuario {username} ya existía")
        existentes += 1

print("\n📊 Resumen:")
print(f"   - Nuevos docentes creados: {creados}")
print(f"   - Usuarios ya existentes: {existentes}")
print(f"   - Contraseña inicial para todos: {CLAVE_INICIAL}")
