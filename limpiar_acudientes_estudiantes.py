import os
import django
from django.db.models import Q
from tasks.models import Perfil, Matricula, Acudiente
from django.contrib.auth.models import User

# 1. Configuración de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangocrud.settings")
django.setup()

# --- Definición de Usuarios a Eliminar ---
# Identificar todos los perfiles de Estudiantes Y Acudientes
estudiantes = Perfil.objects.filter(rol="ESTUDIANTE")
acudientes = Perfil.objects.filter(rol="ACUDIENTE")

estudiante_users = [p.user for p in estudiantes]
acudiente_users = [p.user for p in acudientes]

usuarios_a_eliminar = list(set(estudiante_users + acudiente_users))
ids_a_eliminar = [u.id for u in usuarios_a_eliminar]

print(f"Buscando {len(estudiante_users)} estudiantes y {len(acudientes)} acudientes.")

try:
    # 2. ELIMINAR VÍNCULOS ACUDIENTE (Si aún existen)
    # Esto es redundante si se borran los usuarios, pero previene errores de integridad.
    Acudiente.objects.filter(Q(estudiante__in=usuarios_a_eliminar) | Q(acudiente__in=usuarios_a_eliminar)).delete()
    print("✅ Vínculos Acudiente-Estudiante eliminados.")

    # 3. ELIMINAR MATRÍCULAS (Necesario para que la cascada sea limpia)
    Matricula.objects.filter(estudiante__in=usuarios_a_eliminar).delete()
    print("✅ Matrículas eliminadas.")

    # 4. ELIMINAR USUARIOS (Esto eliminará los Perfiles por CASCADE)
    deleted_count, deleted_data = User.objects.filter(id__in=ids_a_eliminar).delete()
    
    print(f"\n✅ ¡Éxito! Se eliminaron {deleted_count} objetos, incluyendo Estudiantes y Acudientes.")
    print("El sistema está listo para la carga masiva corregida.")

except Exception as e:
    print(f"❌ Ocurrió un error inesperado durante la limpieza: {e}")
