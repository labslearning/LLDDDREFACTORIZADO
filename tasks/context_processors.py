# tasks/context_processors.py
from .models import Notificacion, MensajeInterno

def datos_globales_usuario(request):
    """
    Inyecta notificaciones y mensajes en todas las plantillas.
    Esto permite que la campanita y el sobre del navbar funcionen en todo el sitio.
    """
    ctx = {}
    
    # Solo procesamos si hay un usuario logueado para ahorrar recursos
    if request.user.is_authenticated:
        # 1. Notificaciones (Campana)
        # Obtenemos las 5 más recientes no leídas para el dropdown
        notif = Notificacion.objects.filter(usuario=request.user, leida=False).order_by('-fecha_creacion')[:5]
        # Obtenemos el conteo total de no leídas para el badge rojo
        count_notif = Notificacion.objects.filter(usuario=request.user, leida=False).count()
        
        # 2. Mensajes Chat (Sobre)
        # Obtenemos el conteo de mensajes no leídos donde el usuario es destinatario
        count_mensajes = MensajeInterno.objects.filter(destinatario=request.user, leido=False).count()
        
        ctx = {
            'mis_notificaciones': notif,
            'notificaciones_count': count_notif,
            'mensajes_no_leidos_count': count_mensajes,
        }
    
    return ctx
