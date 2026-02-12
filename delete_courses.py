import os
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project_name.settings")
django.setup()

from tasks.models import Curso

# Delete all courses
try:
    cursos = Curso.objects.all()
    cursos.delete()
    print("✅ All courses have been successfully deleted.")
except Exception as e:
    print(f"❌ An error occurred: {e}")
