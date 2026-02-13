# apps/social/models.py
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.tenancy.mixins import TenantAwareModel

# ==========================================================
# 🌐 1. GRUPOS SOCIALES Y NETWORKING
# ==========================================================

class SocialGroup(TenantAwareModel):
    """Grupos de interés o salones virtuales por colegio."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='social/groups/', null=True, blank=True)
    
    # related_name único para evitar choques con el monolito
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_groups_created'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='social_groups_joined'
    )
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='social_groups_admin'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.tenant.name if self.tenant else 'Global'})"

class Follow(TenantAwareModel):
    """Sistema de seguidores aislado por colegio."""
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_following'
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

# ==========================================================
# 📰 2. MURO SOCIAL Y PUBLICACIONES
# ==========================================================

class Post(TenantAwareModel):
    """Publicaciones en el muro general o de grupo."""
    TIPOS = [('NORMAL', 'Publicación'), ('ANUNCIO', 'Anuncio Oficial')]
    
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_posts_creados'
    )
    grupo = models.ForeignKey(
        SocialGroup, 
        on_delete=models.CASCADE, 
        null=True, blank=True, 
        related_name='posts_del_grupo'
    )
    
    contenido = models.TextField()
    imagen = models.ImageField(upload_to='social/posts/', null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='NORMAL')
    es_destacado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post de {self.autor.username} - {self.creado_en.date()}"

class Comment(TenantAwareModel):
    """Comentarios en las publicaciones."""
    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='social_comentarios'
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_comentarios_creados'
    )
    contenido = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

class Reaction(TenantAwareModel):
    """Likes y otras reacciones genéricas."""
    REACCIONES = [('LIKE', 'Me gusta'), ('LOVE', 'Me encanta'), ('WOW', 'Sorprendido')]
    
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_reacciones_dadas'
    )
    tipo = models.CharField(max_length=10, choices=REACCIONES, default='LIKE')
    
    # 🛡️ FIX CRÍTICO E304: related_name único para el ContentType
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE,
        related_name='social_content_reactions'
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('usuario', 'content_type', 'object_id')

# ==========================================================
# 💬 3. CHAT INTERNO Y SEGURIDAD (AUDITORÍA SENTINEL)
# ==========================================================

class MensajeInterno(TenantAwareModel):
    """Bandeja de entrada privada entre usuarios del mismo colegio."""
    remitente = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_mensajes_enviados'
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_mensajes_recibidos'
    )
    
    asunto = models.CharField(max_length=200, blank=True)
    cuerpo = models.TextField()
    archivo = models.FileField(upload_to='chat_adjuntos/', null=True, blank=True)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    def __str__(self):
        return f"De {self.remitente.username} para {self.destinatario.username}"

class SecurityLog(TenantAwareModel):
    """Registro de mensajes bloqueados por toxicidad o bullying."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_logs_seguridad'
    )
    contenido_intentado = models.TextField()
    razon_bloqueo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bloqueo: {self.usuario.username} - {self.fecha.date()}"