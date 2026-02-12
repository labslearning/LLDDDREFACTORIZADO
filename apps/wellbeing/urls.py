from django.urls import path
from . import views

app_name = 'wellbeing'

urlpatterns = [
    path('dashboard/', views.dashboard_bienestar, name='dashboard_bienestar'),
    path('historial-asistencia/', views.historial_asistencia, name='historial_asistencia'),
    path('alumno/<int:estudiante_id>/observador/', views.ver_observador, name='ver_observador'),
    path('alumno/<int:estudiante_id>/nueva-observacion/', views.crear_observacion, name='crear_observacion'),
    path('actas/', views.historial_actas, name='historial_actas'),
    path('actas/crear/', views.crear_acta, name='crear_acta'),
    # PDFs
    path('pdf/observador/<int:estudiante_id>/', views.generar_observador_pdf, name='generar_observador_pdf'),
    path('documentos-institucionales/', views.documentos_institucionales, name='documentos_institucionales'),
]
