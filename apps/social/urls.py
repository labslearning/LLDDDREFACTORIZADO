from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Rutas de Feed y Perfil
    path('feed/', views.social_feed, name='social_feed'),
    path('perfil/<str:username>/', views.ver_perfil_social, name='ver_perfil_social'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('search/', views.global_search, name='global_search'),
    
    # Grupos
    path('grupos/', views.lista_grupos, name='lista_grupos'),
    path('grupos/crear/', views.crear_grupo, name='crear_grupo'),
    path('grupos/<int:grupo_id>/', views.detalle_grupo, name='detalle_grupo'),
    
    # Chat
    path('chat/', views.buzon_mensajes, name='buzon_mensajes'),
    path('chat/enviar/', views.enviar_mensaje, name='enviar_mensaje'),
    path('chat/leer/<int:mensaje_id>/', views.leer_mensaje, name='leer_mensaje'),

    # 🔔 RUTAS DE NOTIFICACIONES (SOLUCIÓN A LOS ERRORES)
    path('notificaciones/marcar-leidas/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notificaciones/historial/', views.historial_notificaciones, name='historial_notificaciones'),
]