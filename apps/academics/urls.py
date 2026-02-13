# apps/academics/urls.py
from django.urls import path
from . import views

# EL DNI DEL MÓDULO: Habilita el uso de {% url 'academics:nombre' %}
app_name = 'academics'

urlpatterns = [
    # 📊 DASHBOARDS E INTELIGENCIA
    path('dashboard/', views.dashboard_academico, name='dashboard_academico'),
    path('gestion/', views.gestion_academica, name='gestion_academica'),
    
    # 🏫 GESTIÓN DE CURSOS Y PERSONAL
    path('cursos/', views.gestionar_cursos, name='gestionar_cursos'),
    path('staff/', views.gestion_staff, name='gestion_staff'),
    path('docentes/registrar/', views.registrar_docente, name='registrar_docente'),
    path('periodos/', views.gestionar_periodos, name='gestionar_periodos'),
    
    # 👨‍🏫 ASIGNACIÓN Y CARGA ACADÉMICA
    path('asignar-materias/', views.asignar_materia_docente, name='asignar_materia_docente'),
    
    # 🎓 GESTIÓN DE ESTUDIANTES Y MATRÍCULAS
    path('estudiante/asignar-curso/', views.asignar_curso_estudiante, name='asignar_curso_estudiante'),
    path('estudiante/registrar-masivo/', views.registrar_alumnos_masivo_form, name='registrar_alumnos_masivo_form'),
    path('estudiante/procesar-masivo/', views.registrar_alumnos_masivo, name='registrar_alumnos_masivo'),
    path('estudiante/retirar/', views.admin_eliminar_estudiante, name='admin_eliminar_estudiante'),
    
    # 📝 EVALUACIONES Y CALIFICACIONES
    path('notas/subir/', views.subir_notas, name='subir_notas'),
    path('reportes/consolidado/', views.reporte_consolidado, name='reporte_consolidado'),
    
    # ⚡ ENDPOINTS DE API (PARA FUNCIONES AJAX/MODALES)
    path('api/crear-curso/', views.api_crear_curso, name='api_crear_curso'),
    path('api/asignar-director/', views.api_asignar_director, name='api_asignar_director'),
    path('api/asistencia/', views.api_tomar_asistencia, name='api_tomar_asistencia'),
    path('api/estudiantes-por-curso/<int:curso_id>/', views.api_get_students_by_course, name='api_get_students_by_course'),
    path('api/periodos-por-curso/', views.cargar_periodos_por_curso, name='cargar_periodos_por_curso'),
    path('api/configurar-evaluacion/', views.configurar_plan_evaluacion, name='configurar_plan_evaluacion'),
]