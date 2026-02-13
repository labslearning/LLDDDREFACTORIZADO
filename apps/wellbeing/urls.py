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
    
    # --- RUTAS QUE FALTABAN Y CAUSAN EL ERROR ---
    path('observaciones/historial-global/', views.historial_global_observaciones, name='historial_global_observaciones'),
    path('reportes/consolidado/', views.reporte_consolidado, name='reporte_consolidado'),
    path('observaciones/guardar-seguimiento/', views.guardar_seguimiento, name='guardar_seguimiento'),
    path('pdf/descargar-bienestar/', views.descargar_pdf_bienestar, name='descargar_pdf_bienestar'),
    # --------------------------------------------

    path('pdf/observador/<int:estudiante_id>/', views.generar_observador_pdf, name='generar_observador_pdf'),
    path('documentos-institucionales/', views.documentos_institucionales, name='documentos_institucionales'),
]