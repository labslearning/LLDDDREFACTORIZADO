# ===================================================================
# djangocrud/urls.py (VERSIÓN MODULAR ENTERPRISE - CONEXIÓN GLOBAL)
# ===================================================================

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.views.generic import TemplateView

# Importamos las vistas del núcleo para las rutas administrativas
from tasks import views, views_admin 

urlpatterns = [
    # 1. 🔑 LA LLAVE MAESTRA: Panel de Administración nativo de Django
    path('admin/', admin.site.urls),

    # 2. 🏗️ EL NÚCLEO (Core): Autenticación, Dashboard General y Home
    path('', include('tasks.urls')),

    # 3. 🏫 CLÍNICA ACADÉMICA: Gestión de Cursos, Notas y Alumnos
    path('academico/', include('apps.academics.urls')),

    # 4. 📱 CLÍNICA SOCIAL: Muro, Perfiles, Grupos y Chat
    path('social/', include('apps.social.urls')),

    # 5. ❤️ CLÍNICA DE BIENESTAR: Observador, Actas y Psicología
    path('bienestar/', include('apps.wellbeing.urls')),

    # 6. 🛠️ UTILIDADES PWA Y SOPORTE MÓVIL
    path('sw.js', TemplateView.as_view(
        template_name='sw.js', 
        content_type='application/javascript'
    ), name='sw.js'),
    
    # 7. 🦅 RUTAS ADMINISTRATIVAS CENTRALIZADAS (Suturadas con views_admin)
    path('panel/cierre-anual/', views_admin.panel_cierre_anual, name='panel_cierre_anual'),
    path('panel/cierre-anual/revertir/<int:log_id>/', views_admin.revertir_cierre_anual, name='revertir_cierre'),
    path('panel/boveda/', views_admin.panel_boveda, name='panel_boveda'), 
    
    # Rutas de Gestión (Perfiles, Archivo, Asignaciones)
    path('gestion-perfiles/', views_admin.gestion_perfiles, name='gestion_perfiles'),
    path('archivo-historico/', views_admin.admin_ex_estudiantes, name='admin_ex_estudiantes'),
    path('asignar-curso-estudiante/', views_admin.asignar_curso_estudiante, name='asignar_curso_estudiante'),

    # Rutas de Apps Dashboard
    path('data-center/history/', views_admin.import_history, name='import_history'),
    path('shadow-monitor/', views_admin.shadow_tenant, name='shadow_tenant'),
    path('ai-engine/', views_admin.ai_engine, name='ai_engine'),

    # 👇 ESTAS SON LAS QUE ARREGLAN TU ERROR ACTUAL (Operatividad) 👇
    path('registro-individual/', views_admin.mostrar_registro_individual, name='mostrar_registro_individual'),
    path('db-visual/', views_admin.admin_db_visual, name='admin_db_visual'),
    path('staff-management/', views_admin.gestionar_staff, name='gestionar_staff'),
    path('reporte-consolidado/', views_admin.reporte_consolidado, name='reporte_consolidado'),

    # 👇 NUEVOS ENDPOINTS DE API PARA GESTIÓN DE PERMISOS 👇
    path('api/admin/toggle-boletin/', views_admin.panel_api_toggle_boletin_permiso, name='panel_api_toggle_boletin_permiso'),
    path('api/admin/toggle-observador/', views_admin.panel_api_toggle_observador, name='panel_api_toggle_observador'),
    path('staff-management/desactivar/<int:user_id>/', views_admin.desactivar_staff, name='desactivar_staff'),
    path('api/periodos/', views_admin.api_cargar_periodos, name='api_cargar_periodos'),
]

# ===================================================================
# 🩺 CIRUGÍA DE ARCHIVOS ESTÁTICOS Y MEDIA (SOPORTE PARA RAILWAY)
# ===================================================================

if settings.DEBUG:
    # MODO DESARROLLO
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # MODO PRODUCCIÓN (Railway / Nube)
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]

# ===================================================================
# 🩺 FIN DE LA CIRUGÍA - SISTEMA ESTABILIZADO
# ===================================================================