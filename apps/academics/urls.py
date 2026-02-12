# ===================================================================
# apps/academics/urls.py (MÓDULO DE GESTIÓN ACADÉMICA)
# ===================================================================

from django.urls import path
from . import views

# EL DNI DEL MÓDULO: Crucial para que el base.html reconozca el prefijo 'academics:'
app_name = 'academics'

urlpatterns = [
    # 🏫 GESTIÓN ESTRATÉGICA
    path('gestion/', views.gestion_academica, name='gestion_academica'),
    path('cursos/', views.gestionar_cursos, name='gestionar_cursos'),
    
    # 👨‍🏫 ASIGNACIÓN Y CARGA DOCENTE
    path('asignar-materias/', views.asignar_materia_docente, name='asignar_materia_docente'),
    
    # 🎓 GESTIÓN DE ESTUDIANTES (La ruta que curaba el error NoReverseMatch)
    path('asignar-estudiante/', views.asignar_curso_estudiante, name='asignar_curso_estudiante'),
    path('registrar-masivo/', views.registrar_alumnos_masivo_form, name='registrar_alumnos_masivo_form'),
    
    # 📝 EVALUACIONES Y NOTAS
    path('subir-notas/', views.subir_notas, name='sub_notas'), # Mantenemos el nombre interno de tu lógica
    
    # ⚡ ENDPOINTS DE API (PARA FUNCIONES ASÍNCRONAS)
    path('api/crear-curso/', views.api_crear_curso, name='api_crear_curso'),
    path('api/asistencia/', views.api_tomar_asistencia, name='api_tomar_asistencia'),
]

# ===================================================================
# 🩺 FIN DE LA CIRUGÍA - MÓDULO SINCRONIZADO
# ===================================================================