# tasks/urls.py
from django.urls import path
from . import views, views_pdf, views_shadow, views_import, views_admin
from . import ai_views

# Solo dejamos los imports del corazón (Core)
from .views import (
    home, signup, signin, signout, 
    dashboard_estudiante, dashboard_docente, admin_dashboard, 
    dashboard_director, dashboard_acudiente
)

urlpatterns = [

    # ======================================================
    # 🔑 NÚCLEO: AUTENTICACIÓN Y HOME
    # ======================================================
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('logout/', views.signout, name='logout'), 

    # ======================================================
    # 🏠 DASHBOARDS CENTRALES (CORAZÓN DEL SISTEMA)
    # ======================================================
    path('dashboard/estudiante/', views.dashboard_estudiante, name='dashboard_estudiante'),
    path('dashboard/docente/', views.dashboard_docente, name='dashboard_docente'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/director/', views.dashboard_director, name='dashboard_director'),
    path('dashboard/acudiente/', views.dashboard_acudiente, name='dashboard_acudiente'),

    # ======================================================
    # 🗣️ FORO Y COMUNIDAD (LEGACY CORE)
    # ======================================================
    path('forum/', views.forum, name='forum'),
    path('ask_question/', views.ask_question, name='ask_question'),
    path('question/<int:question_id>/', views.question_detail, name='question_detail'),
    path('answer/<int:question_id>/', views.answer_question, name='answer_question'),

    # ======================================================
    # 🛡️ PANEL DE SEGURIDAD Y CUENTA
    # ======================================================
    path('panel/gestion-perfiles/', views.gestion_perfiles, name='gestion_perfiles'),
    path('panel/eliminar-estudiante/', views.admin_eliminar_estudiante, name='admin_eliminar_estudiante'),
    path('panel/resetear-contrasena/', views.admin_reset_password, name='admin_reset_password'),
    path('panel/db-visual/', views.admin_db_visual, name='admin_db_visual'),
    path('panel/ex-alumnos/', views.admin_ex_estudiantes, name='admin_ex_estudiantes'),
    path('cuenta/cambiar-clave/', views.cambiar_clave, name='cambiar_clave'),

    # ======================================================
    # 🤖 INTELIGENCIA ARTIFICIAL (IA)
    # ======================================================
    path('prueba-ia/', views.test_ai_connection, name='test_ai'),
    path('orientacion/inteligente/', views.dashboard_ia_estudiante, name='dashboard_ia'),
    path('ia/engine/', views.ai_analysis_engine, name='ai_engine'),
    path('ia/reporte/pdf/', views.download_ai_report_pdf, name='download_ai_report_pdf'),
    path('api/ai-agent/', ai_views.api_ai_agent, name='api_ai_agent'),

    # ======================================================
    # 📦 SUITE DE IMPORTACIÓN Y CIERRE ANUAL
    # ======================================================
    path('importar/subir/', views_import.import_upload_view, name='import_upload'),
    path('importar/mapeo/', views_import.import_mapping_view, name='import_mapping'),
    path('importar/inspect/<uuid:batch_id>/', views_import.import_inspect_view, name='import_inspect'),
    path('panel/cierre-anual/', views_admin.panel_cierre_anual, name='panel_cierre_anual'),
    path('panel/boveda/', views_admin.panel_boveda, name='panel_boveda'),

    # ======================================================
    # 🏛️ INSTITUCIONAL Y CERTIFICADOS
    # ======================================================
    path('generar-certificado/<int:user_id>/', views.generar_certificado_estudiantil, name='generar_certificado_estudiantil'),
    path('institucion/documentos/', views.ver_documentos_institucionales, name='documentos_institucionales'),
    
    #==========================================
    # 🦄 RUTAS SHADOW (TENANT SIMULATION)
    # ==========================================
    path('shadow-demo/', views_shadow.shadow_tenant_dashboard, name='shadow_tenant'),
]