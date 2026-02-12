import os
import django

# Asegúrate de que el nombre del proyecto ('djangocrud') sea correcto
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangocrud.settings")
django.setup()

from django.contrib.auth.models import User
from tasks.models import Matricula

print("Buscando todos los usuarios con matrículas activas para una limpieza definitiva...")

# 1. Obtener los IDs de todos los usuarios que aparecen en la tabla de matrículas.
# Esto es más robusto porque no depende de que el perfil sea correcto.
student_user_ids = Matricula.objects.filter(activo=True).values_list('estudiante_id', flat=True).distinct()

if student_user_ids:
    # 2. Convertir el queryset de IDs a una lista para la consulta.
    ids_to_delete = list(student_user_ids)
    
    print(f"Se encontraron {len(ids_to_delete)} usuarios asociados a matrículas.")
    
    # 3. Eliminar todos los usuarios encontrados. CASCADE se encargará del resto.
    deleted_count, deleted_data = User.objects.filter(id__in=ids_to_delete).delete()
    
    print(f"✅ ¡Éxito! Se eliminaron {deleted_count} usuarios y todos sus datos relacionados (perfiles, matrículas, etc.).")
else:
    print("ℹ️ No se encontraron matrículas activas para eliminar.")
