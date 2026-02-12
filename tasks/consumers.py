# ===================================================================
# tasks/consumers.py (CHATS GRUPALES AVANZADOS Y NOTIFICACIONES)
# ===================================================================

import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ActiveUser

User = get_user_model()

# ===================================================================
# 📡 CONSUMER DE CHAT GRUPAL (AVANZADO - PASO 13)
# ===================================================================

class GroupChatConsumer(AsyncWebsocketConsumer):
    """
    Maneja la lógica de chat en tiempo real para grupos.
    Soporta: Mensajes, Usuarios Activos, Indicador 'Escribiendo...'.
    """
    async def connect(self):
        # Obtenemos el ID del grupo desde la URL (ws/chat/group/<room_name>/)
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        # Unirse al grupo de canales
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Registrar actividad del usuario (DB segura)
        await self.registrar_usuario_activo()

        # Notificar a todos que entró alguien nuevo
        active_users_list = await self.obtener_usuarios_activos()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'active_users_update',
                'users': active_users_list
            }
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Salir del grupo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Eliminar registro de actividad
        if hasattr(self, 'user') and not self.user.is_anonymous:
            await self.eliminar_usuario_activo()

            # Notificar salida a los demás
            active_users_list = await self.obtener_usuarios_activos()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'active_users_update',
                    'users': active_users_list
                }
            )

    # Recibir mensaje del WebSocket (Cliente -> Servidor)
    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            # Detectamos el tipo de mensaje (chat o typing)
            msg_type = data.get('type', 'chat_message') 

            if msg_type == 'chat_message':
                message = data.get('message')
                username = data.get('username')
                
                # Reenviar a todos en el grupo con timestamp
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': username,
                        'timestamp': datetime.now().strftime("%H:%M") # Hora actual
                    }
                )
            
            elif msg_type == 'typing':
                # Reenviar evento de "Escribiendo..." (efímero, no se guarda)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_typing',
                        'username': self.user.username,
                        'is_typing': data.get('is_typing', True)
                    }
                )

    # --- Manejadores de Eventos (Servidor -> Cliente) ---

    async def chat_message(self, event):
        """Envía un mensaje de chat al cliente."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message', # Etiqueta para el JS
            'message': event['message'],
            'username': event['username'],
            'timestamp': event.get('timestamp', '')
        }))

    async def active_users_update(self, event):
        """Actualiza la lista de usuarios conectados."""
        await self.send(text_data=json.dumps({
            'type': 'active_users',
            'users': event['users']
        }))

    async def user_typing(self, event):
        """Notifica que alguien está escribiendo."""
        # No notificar al propio usuario que está escribiendo
        if event['username'] != self.user.username:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'username': event['username'],
                'is_typing': event['is_typing']
            }))

    # --- Métodos de Base de Datos (Síncronos -> Asíncronos) ---
    
    @database_sync_to_async
    def registrar_usuario_activo(self):
        ActiveUser.objects.update_or_create(
            user=self.user, 
            defaults={'last_activity': datetime.now()}
        )

    @database_sync_to_async
    def eliminar_usuario_activo(self):
        ActiveUser.objects.filter(user=self.user).delete()

    @database_sync_to_async
    def obtener_usuarios_activos(self):
        return list(ActiveUser.objects.filter(user__is_active=True).values_list('user__username', flat=True))


# ===================================================================
# 🔔 CONSUMER DE NOTIFICACIONES (MANTENIDO INTACTO)
# ===================================================================

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Canal exclusivo user_<id> para alertas personales (Push Notifications).
    """
    async def connect(self):
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        # Canal único por usuario
        self.group_name = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        """Evento disparado desde utils.crear_notificacion (backend)"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'titulo': event['titulo'],
            'mensaje': event['mensaje'],
            'link': event.get('link', '#'),
            'tipo_alerta': event.get('tipo_alerta', 'info')
        }))# tasks/consumers.py (COMPLETO Y FINAL)

import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ActiveUser

# --- NUEVOS IMPORTS PARA LA IA (FASE 7) ---
from .ai.orchestrator import ai_orchestrator
from .ai.constants import ACCION_CHAT_SOCRATICO

User = get_user_model()

# ===================================================================
# 📡 CONSUMER DE CHAT GRUPAL (MANTENIDO INTACTO)
# ===================================================================

class GroupChatConsumer(AsyncWebsocketConsumer):
    """
    Maneja la lógica de chat en tiempo real para grupos humanos.
    Soporta: Mensajes, Usuarios Activos, Indicador 'Escribiendo...'.
    """
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.registrar_usuario_activo()

        active_users_list = await self.obtener_usuarios_activos()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'active_users_update',
                'users': active_users_list
            }
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        if hasattr(self, 'user') and not self.user.is_anonymous:
            await self.eliminar_usuario_activo()

            active_users_list = await self.obtener_usuarios_activos()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'active_users_update',
                    'users': active_users_list
                }
            )

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            msg_type = data.get('type', 'chat_message') 

            if msg_type == 'chat_message':
                message = data.get('message')
                username = data.get('username')
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': username,
                        'timestamp': datetime.now().strftime("%H:%M")
                    }
                )
            
            elif msg_type == 'typing':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_typing',
                        'username': self.user.username,
                        'is_typing': data.get('is_typing', True)
                    }
                )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'username': event['username'],
            'timestamp': event.get('timestamp', '')
        }))

    async def active_users_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'active_users',
            'users': event['users']
        }))

    async def user_typing(self, event):
        if event['username'] != self.user.username:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'username': event['username'],
                'is_typing': event['is_typing']
            }))

    @database_sync_to_async
    def registrar_usuario_activo(self):
        ActiveUser.objects.update_or_create(
            user=self.user, 
            defaults={'last_activity': datetime.now()}
        )

    @database_sync_to_async
    def eliminar_usuario_activo(self):
        ActiveUser.objects.filter(user=self.user).delete()

    @database_sync_to_async
    def obtener_usuarios_activos(self):
        return list(ActiveUser.objects.filter(user__is_active=True).values_list('user__username', flat=True))


# ===================================================================
# 🔔 CONSUMER DE NOTIFICACIONES (MANTENIDO INTACTO)
# ===================================================================

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'titulo': event['titulo'],
            'mensaje': event['mensaje'],
            'link': event.get('link', '#'),
            'tipo_alerta': event.get('tipo_alerta', 'info')
        }))


# ===================================================================
# 🤖 NUEVO: CHAT SOCRÁTICO CON IA (FASE 7)
# ===================================================================

class SocraticAIConsumer(AsyncWebsocketConsumer):
    """
    Canal privado 1 a 1 entre el Estudiante y el Orquestador IA.
    No requiere grupos porque es una conversación personal.
    """
    async def connect(self):
        self.user = self.scope['user']

        # 1. Seguridad: Solo usuarios autenticados
        if self.user.is_anonymous:
            await self.close()
            return

        await self.accept()
        
        # Saludo inicial (Opcional)
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': 'Conectado al Asistente Socrático. ¿En qué tema te ayudo hoy?'
        }))

    async def disconnect(self, close_code):
        pass # No necesitamos limpiar nada especial aquí

    async def receive(self, text_data):
        """
        Recibe la pregunta del estudiante, llama al Orquestador y devuelve la respuesta.
        """
        try:
            data = json.loads(text_data)
            user_message = data.get('message')
            subject_context = data.get('materia', None) # Ej: "Matemáticas"

            if not user_message:
                return

            # Indicador de "Pensando..."
            await self.send(text_data=json.dumps({'type': 'typing', 'status': True}))

            # 2. LLAMADA AL ORQUESTADOR (Es síncrono, así que lo envolvemos)
            # Esto dispara: RateLimit -> Contexto -> Prompt -> DeepSeek -> Log
            response = await self.call_ai_orchestrator(
                user=self.user,
                query=user_message,
                materia=subject_context
            )

            # 3. RESPUESTA AL CLIENTE
            if response['success']:
                await self.send(text_data=json.dumps({
                    'type': 'ai_response',
                    'message': response['content'],
                    'tokens': response.get('meta', {}).get('total_tokens', 0)
                }))
            else:
                # Manejo de Errores (Límite alcanzado, Política, Error API)
                error_type = response.get('source', 'ERROR')
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'code': error_type,
                    'message': response['content']
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Formato inválido'}))
        except Exception as e:
            await self.send(text_data=json.dumps({'type': 'error', 'message': f'Error interno: {str(e)}'}))

    # --- PUENTE SÍNCRONO <-> ASÍNCRONO ---
    
    @database_sync_to_async
    def call_ai_orchestrator(self, user, query, materia):
        """
        Envuelve la llamada al orquestador en un hilo seguro para no bloquear WebSockets.
        """
        return ai_orchestrator.process_request(
            user=user,
            action_type=ACCION_CHAT_SOCRATICO,
            user_query=query,
            materia_actual=materia,
            temperature=0.6 # Creatividad media para chat
        )