import os
import django
from django.db.models import Q

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project_name.settings")
django.setup()

from tasks.models import Perfil
from django.contrib.auth.models import User

# Delete all professors
try:
    # Identify professor profiles.
    profesores_perfiles = Perfil.objects.filter(Q(rol='DOCENTE') | Q(es_director=True))
    
    # Get the user objects associated with these profiles.
    profesores_usuarios = User.objects.filter(id__in=profesores_perfiles.values('user'))
    
    # Delete the user objects, which will cascade and delete the profiles.
    profesores_usuarios.delete()
    
    print("✅ All professor accounts have been successfully deleted.")
except Exception as e:
    print(f"❌ An error occurred: {e}")
