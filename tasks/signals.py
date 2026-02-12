# ===================================================================
# 🧠 FASE IV (PASO 22): AUTOMATIZACIÓN Y GAMIFICACIÓN (SIGNALS)
# ===================================================================
##DEsde aqui para los SMS 
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Asistencia, Notificacion, MensajeInterno, Acudiente
# AGREGAR ESTA LÍNEA CRÍTICA:
from .utils import enviar_sms_twilio, verificar_y_alertar_acudiente



###Hasta Aqui 
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Perfil, Post, Reaction, Comment

# 1. AUTOMATIZACIÓN DE PERFIL
# Cada vez que se cree un User, se crea automáticamente su Perfil.
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.get_or_create(user=instance)

# 2. RASTREO DE ACTIVIDAD (Login)
# Actualiza 'last_seen' automáticamente cuando alguien inicia sesión.
@receiver(user_logged_in)
def actualizar_last_seen(sender, user, request, **kwargs):
    if hasattr(user, 'perfil'):
        user.perfil.last_seen = timezone.now()
        user.perfil.save(update_fields=['last_seen'])

# 3. GAMIFICACIÓN: PUNTOS POR PUBLICAR
# +5 Puntos por crear un Post nuevo.
@receiver(post_save, sender=Post)
def puntos_por_post(sender, instance, created, **kwargs):
    if created:
        perfil = instance.autor.perfil
        perfil.puntos_reputacion += 5 
        perfil.save(update_fields=['puntos_reputacion'])

# 4. GAMIFICACIÓN: PUNTOS POR COMENTAR
# +2 Puntos por comentar (fomenta la participación).
@receiver(post_save, sender=Comment)
def puntos_por_comentario(sender, instance, created, **kwargs):
    if created:
        perfil = instance.autor.perfil
        perfil.puntos_reputacion += 2 
        perfil.save(update_fields=['puntos_reputacion'])

# 5. GAMIFICACIÓN: PUNTOS POR RECIBIR REACCIONES
# Si alguien reacciona a tu contenido, ganas puntos.
@receiver(post_save, sender=Reaction)
def puntos_por_reaccion(sender, instance, created, **kwargs):
    if created:
        # Obtenemos el objeto al que se reaccionó (Post o Comentario)
        contenido = instance.content_object
        
        # Verificamos que tenga autor y no sea autolike (opcional)
        if hasattr(contenido, 'autor') and contenido.autor != instance.usuario:
            autor_perfil = contenido.autor.perfil
            
            # Sistema de puntos según la emoción
            puntos = 1 # Like (Básico)
            if instance.tipo == 'LOVE':
                puntos = 3 # Love vale más
            elif instance.tipo == 'WOW':
                puntos = 2
            
            autor_perfil.puntos_reputacion += puntos
            autor_perfil.save(update_fields=['puntos_reputacion'])

# 6. BALANCE: RESTAR PUNTOS SI BORRAN LA REACCIÓN
# Si te quitan el like, pierdes los puntos (justicia).
@receiver(post_delete, sender=Reaction)
def restar_puntos_reaccion(sender, instance, **kwargs):
    contenido = instance.content_object
    if hasattr(contenido, 'autor') and contenido.autor != instance.usuario:
        autor_perfil = contenido.autor.perfil
        
        puntos = 1
        if instance.tipo == 'LOVE': points = 3
        elif instance.tipo == 'WOW': points = 2
        
        # Evitar negativos si es posible, aunque la reputación puede bajar
        autor_perfil.puntos_reputacion -= puntos
        autor_perfil.save(update_fields=['puntos_reputacion'])


#estoy agregando el sms 

# ==========================================
# SIGNALS DE MENSAJERÍA SMS
# ==========================================

# 1. CASO URGENTE: FALLA DE ASISTENCIA (Siempre se envía, ignora el límite de 24h)
@receiver(post_save, sender=Asistencia)
def alerta_falla_estudiante(sender, instance, created, **kwargs):
    # Asumimos que el estado 'FALLA' indica inasistencia
    if created and instance.estado == 'FALLA':
        estudiante = instance.estudiante
        materia_nombre = instance.materia.nombre
        fecha_str = instance.fecha.strftime("%d/%m")

        # Buscar a los acudientes
        relaciones = Acudiente.objects.filter(estudiante=estudiante)

        for rel in relaciones:
            padre = rel.acudiente
            # Verificar si tiene perfil configurado
            if hasattr(padre, 'perfil') and padre.perfil.telefono_sms and padre.perfil.recibir_sms:
                mensaje = (
                    f"ALERTA ESCOLAR: {estudiante.first_name} {estudiante.last_name} "
                    f"no asistió a la clase de {materia_nombre} el {fecha_str}. "
                    f"Por favor verifica."
                )
                # Envío inmediato
                enviar_sms_twilio(padre.perfil.telefono_sms, mensaje)

# 2. CASO NO URGENTE: ACUMULACIÓN (Usa la lógica de protección de bolsillo)
@receiver(post_save, sender=Notificacion)
def trigger_notificacion_sms(sender, instance, created, **kwargs):
    if created:
        verificar_y_alertar_acudiente(instance.usuario)

@receiver(post_save, sender=MensajeInterno)
def trigger_mensaje_sms(sender, instance, created, **kwargs):
    if created:
        verificar_y_alertar_acudiente(instance.destinatario)