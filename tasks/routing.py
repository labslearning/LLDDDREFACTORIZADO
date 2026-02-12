# ===================================================================
# tasks/routing.py (RUTAS WEBSOCKET)
# ===================================================================

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Ruta para Notificaciones Personales (Campanita)
    # Conecta con NotificationConsumer en tasks/consumers.py
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),

    # Ruta para Chat Grupal (Salas)
    # Conecta con GroupChatConsumer. Captura el nombre de la sala en <room_name>
    re_path(r'ws/chat/group/(?P<room_name>\w+)/$', consumers.GroupChatConsumer.as_asgi()),
    re_path(r'ws/chat/ai/socratic/$', consumers.SocraticAIConsumer.as_asgi()),
]
