import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangocrud.settings")
django.setup()

from django.contrib.auth.models import User
from tasks.models import Perfil, Matricula

# Buscar todos los perfiles de estudiantes
estudiantes = Perfil.objects.filter(rol="ESTUDIANTE")

# Eliminar matrículas primero
Matricula.objects.filter(estudiante__in=[e.user for e in estudiantes]).delete()

# Eliminar usuarios (con cascade elimina también Perfil)
for perfil in estudiantes:
    perfil.user.delete()

print("✅ Todos los estudiantes fueron eliminados.")
