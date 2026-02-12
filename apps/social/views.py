# apps/social/views.py
import json
import logging
from operator import itemgetter
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Min, Max
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

# 🩸 CONEXIÓN CON EL LEGACY
from tasks.models import (
    User, Perfil, Post, Comment, SocialGroup, Reaction, Follow, 
    UserLogro, Notificacion, AuditLog, SecurityLog, Question,
    Matricula, AsignacionMateria, Acudiente, MensajeInterno
)

# 🟢 RECONEXIÓN QUIRÚRGICA DE FORMULARIOS
# 1. Formularios que viven en esta app (Social)
from .forms import (
    PostForm, CommentForm, SocialGroupForm, 
    UserEditForm, EditarPerfilForm, QuestionForm, AnswerForm
)

# 2. Formulario que vive en el núcleo (Tasks)
from tasks.forms import MensajeForm

from tasks.utils import Sentinel, generar_username_unico

logger = logging.getLogger(__name__)

# ==========================================================
# 📱 MURO SOCIAL (FEED) Y CONTENIDO
# ==========================================================

@login_required
def social_feed(request):
    """Muro Social Comunitario Global."""
    posts_qs = Post.objects.filter(grupo__isnull=True).select_related(
        'autor', 'autor__perfil'
    ).prefetch_related(
        'comentarios', 'comentarios__autor__perfil', 'reacciones__usuario'
    ).order_by('-es_destacado', '-creado_en')

    query = request.GET.get('q')
    if query:
        posts_qs = posts_qs.filter(
            Q(contenido__icontains=query) | 
            Q(autor__username__icontains=query) |
            Q(autor__first_name__icontains=query) |
            Q(autor__last_name__icontains=query)
        ).distinct()
        
    paginator = Paginator(posts_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    form = PostForm()

    if request.method == 'POST' and 'publicar_post' in request.POST:
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            nuevo_post = form.save(commit=False)
            nuevo_post.autor = request.user
            # Verificar si es anuncio oficial (solo admins)
            if request.user.perfil.rol == 'ADMINISTRADOR' and 'es_anuncio' in request.POST:
                nuevo_post.tipo = 'ANUNCIO'
            nuevo_post.save()
            messages.success(request, '¡Publicación creada!')
            return redirect('social_feed')
    
    # Manejo de comentarios desde el feed
    elif request.method == 'POST' and 'publicar_comentario' in request.POST:
        return crear_comentario(request, request.POST.get('post_id'))

    grupos_sugeridos = SocialGroup.objects.all().annotate(num_members=Count('members')).order_by('-num_members')[:5]
    
    # 🏥 SUTURA: Ruta corregida a 'social/social_feed.html'
    return render(request, 'social/social_feed.html', {
        'page_obj': page_obj, 'post_form': form, 'grupos_sugeridos': grupos_sugeridos, 'q': query
    })

@login_required
def crear_comentario(request, post_id):
    # Si viene directo del feed, post_id puede venir en POST o como argumento
    if not post_id:
        post_id = request.POST.get('post_id')
        
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        contenido = request.POST.get('contenido')
        if contenido:
            Comment.objects.create(autor=request.user, post=post, contenido=contenido)
            messages.success(request, 'Comentario agregado.')
        else:
             messages.warning(request, 'El comentario no puede estar vacío.')
             
    return redirect(request.META.get('HTTP_REFERER', 'social_feed'))

# ==========================================================
# 👥 GESTIÓN DE PERFILES Y RED (FOLLOW)
# ==========================================================

@login_required
def ver_perfil_social(request, username):
    perfil_user = get_object_or_404(User, username=username)
    perfil, _ = Perfil.objects.get_or_create(user=perfil_user)
    
    is_following = False
    if request.user != perfil_user:
        is_following = Follow.objects.filter(follower=request.user, following=perfil_user).exists()

    posts_qs = Post.objects.filter(autor=perfil_user).order_by('-creado_en')
    page_obj = Paginator(posts_qs, 5).get_page(request.GET.get('page'))
    mis_logros = UserLogro.objects.filter(usuario=perfil_user).select_related('logro').order_by('-fecha_obtenido')

    # 🏥 SUTURA: Ruta corregida a 'social/perfil_social.html'
    return render(request, 'social/perfil_social.html', {
        'perfil_user': perfil_user, 'perfil': perfil, 'is_following': is_following,
        'page_obj': page_obj, 'mis_logros': mis_logros,
        'followers_count': Follow.objects.filter(following=perfil_user).count(),
        'following_count': Follow.objects.filter(follower=perfil_user).count(),
        'posts_count': posts_qs.count()
    })

@login_required
def editar_perfil(request):
    user = request.user
    perfil = getattr(user, 'perfil', None) 
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = EditarPerfilForm(request.POST, request.FILES, instance=perfil)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user_form.save()
                profile_form.save()
                messages.success(request, '¡Tu perfil se ha actualizado correctamente!')
                return redirect('ver_perfil_social', username=user.username)
        else:
            messages.error(request, 'Hay errores en el formulario.')
    else:
        user_form = UserEditForm(instance=user)
        profile_form = EditarPerfilForm(instance=perfil)
    
    # 🏥 SUTURA: Ruta corregida a 'social/editar_perfil.html'
    return render(request, 'social/editar_perfil.html', {'user_form': user_form, 'profile_form': profile_form})

@login_required
@require_POST
def toggle_follow(request):
    try:
        data = json.loads(request.body)
        target = get_object_or_404(User, id=data.get('user_id'))
        if target == request.user: return JsonResponse({'error': 'Self-follow'}, status=400)
        
        follow = Follow.objects.filter(follower=request.user, following=target).first()
        if follow:
            follow.delete(); action = 'unfollowed'
            msg = f"Dejaste de seguir a {target.username}"
        else:
            Follow.objects.create(follower=request.user, following=target); action = 'followed'
            msg = f"Ahora sigues a {target.username}"

        return JsonResponse({
            'success': True, 'action': action, 'message': msg,
            'followers_count': Follow.objects.filter(following=target).count(),
            'following_count': Follow.objects.filter(follower=request.user).count()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ==========================================================
# 🏗️ GRUPOS Y COMUNIDADES
# ==========================================================

@login_required
def lista_grupos(request):
    grupos = SocialGroup.objects.all().order_by('-created_at')
    # 🏥 SUTURA: Ruta corregida a 'social/grupos/...'
    return render(request, 'social/grupos/lista_grupos.html', {'grupos': grupos})

@login_required
def crear_grupo(request):
    roles_permitidos = ['ADMINISTRADOR', 'DOCENTE', 'COORD_ACADEMICO', 'PSICOLOGO', 'COORD_CONVIVENCIA']
    if request.user.perfil.rol not in roles_permitidos:
        messages.error(request, "Solo docentes pueden crear grupos.")
        return redirect('social_feed')

    if request.method == 'POST':
        form = SocialGroupForm(request.POST, request.FILES)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.creator = request.user
            grupo.save()
            grupo.members.add(request.user)
            grupo.admins.add(request.user)
            messages.success(request, f'Grupo "{grupo.name}" creado exitosamente.')
            return redirect('detalle_grupo', grupo_id=grupo.id)
    else:
        form = SocialGroupForm()
    # 🏥 SUTURA: Ruta corregida a 'social/grupos/...'
    return render(request, 'social/grupos/crear_grupo.html', {'form': form})

@login_required
def detalle_grupo(request, grupo_id):
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    es_miembro = grupo.members.filter(id=request.user.id).exists()
    es_admin = (request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR')

    posts_qs = Post.objects.filter(grupo=grupo).select_related('autor').order_by('-creado_en')
    form = PostForm()

    if request.method == 'POST':
        if 'publicar_post' in request.POST:
            if not es_miembro:
                 messages.error(request, "Debes unirte para publicar.")
            else:
                form = PostForm(request.POST, request.FILES)
                if form.is_valid():
                    post = form.save(commit=False)
                    post.autor = request.user
                    post.grupo = grupo
                    post.save()
                    messages.success(request, 'Publicación creada.')
                    return redirect('detalle_grupo', grupo_id=grupo.id)
        
        elif 'unirse' in request.POST:
             return unirse_grupo(request, grupo_id)

        # Edición de grupo (Solo admins)
        elif 'editar_info_grupo' in request.POST and es_admin:
            nuevo_nombre = request.POST.get('nombre_grupo')
            nueva_desc = request.POST.get('descripcion_grupo')
            if nuevo_nombre:
                grupo.name = nuevo_nombre
                grupo.description = nueva_desc
                grupo.save()
                messages.success(request, "Grupo actualizado.")
                return redirect('detalle_grupo', grupo_id=grupo.id)

        # Cambio de portada (Solo admins)
        elif 'cambiar_portada' in request.POST and es_admin:
             p_form = SocialGroupForm(request.POST, request.FILES, instance=grupo)
             if p_form.is_valid():
                 p_form.save()
                 messages.success(request, "Portada actualizada.")
                 return redirect('detalle_grupo', grupo_id=grupo.id)

    # 🏥 SUTURA: Ruta corregida a 'social/grupos/...'
    return render(request, 'social/grupos/detalle_grupo.html', {
        'grupo': grupo, 'es_miembro': es_miembro, 'posts': posts_qs, 'post_form': form, 'es_administrador_grupo': es_admin
    })

@login_required
def unirse_grupo(request, grupo_id):
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    if grupo.members.filter(id=request.user.id).exists():
        grupo.members.remove(request.user)
        messages.info(request, f'Has salido de {grupo.name}.')
        return redirect('social_feed')
    else:
        grupo.members.add(request.user)
        messages.success(request, f'¡Bienvenido a {grupo.name}!')
        return redirect('detalle_grupo', grupo_id=grupo.id)

@login_required
def eliminar_grupo(request, grupo_id):
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    if request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR':
        grupo.delete()
        messages.success(request, 'Grupo eliminado.')
        return redirect('social_feed')
    messages.error(request, "No tienes permiso.")
    return redirect('detalle_grupo', grupo_id=grupo.id)

# ==========================================================
# 🔔 NOTIFICACIONES Y REACCIONES
# ==========================================================

@login_required
@require_POST
def api_reaction(request):
    try:
        data = json.loads(request.body)
        model = Post if data.get('type') == 'post' else Comment
        obj = get_object_or_404(model, id=data.get('id'))
        ct = ContentType.objects.get_for_model(model)

        reaction, created = Reaction.objects.get_or_create(
            usuario=request.user, content_type=ct, object_id=obj.id,
            defaults={'tipo': data.get('reaction', 'LIKE')}
        )
        
        action = ''
        if not created:
            if reaction.tipo == data.get('reaction', 'LIKE'):
                reaction.delete()
                action = 'removed'
            else:
                reaction.tipo = data.get('reaction', 'LIKE')
                reaction.save()
                action = 'updated'
        else:
            action = 'added'

        return JsonResponse({
            'success': True, 
            'action': action,
            'total': Reaction.objects.filter(content_type=ct, object_id=obj.id).count()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_obtener_likes(request, post_id):
    try:
        post = get_object_or_404(Post, id=post_id)
        ct = ContentType.objects.get_for_model(Post)
        likes = Reaction.objects.filter(content_type=ct, object_id=post.id, tipo='LIKE').select_related('usuario__perfil')
        
        users_data = []
        for reaction in likes:
            u = reaction.usuario
            avatar = u.perfil.foto_perfil.url if hasattr(u, 'perfil') and u.perfil.foto_perfil else None
            users_data.append({'username': u.username, 'full_name': u.get_full_name(), 'avatar_url': avatar})
            
        return JsonResponse({'users': users_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def historial_notificaciones(request):
    notificaciones = Notificacion.objects.filter(usuario=request.user).order_by('-fecha_creacion')
    # 🏥 SUTURA: Ruta corregida con namespace 'social/notificaciones/...'
    return render(request, 'social/notificaciones/historial.html', {'notificaciones': notificaciones})

@login_required
@require_POST
def mark_all_notifications_read(request):
    Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    return JsonResponse({'success': True})

# ==========================================================
# 🔍 BUSCADOR GLOBAL
# ==========================================================

@login_required
def global_search(request):
    query = request.GET.get('q', '').strip()
    results = {'users': [], 'groups': [], 'posts': [], 'questions': []}
    
    if query:
        results['users'] = User.objects.filter(
            (Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)),
            is_active=True
        ).exclude(id=request.user.id)[:5]
        
        results['groups'] = SocialGroup.objects.filter(name__icontains=query)[:5]
        results['posts'] = Post.objects.filter(contenido__icontains=query).order_by('-creado_en')[:5]
        results['questions'] = Question.objects.filter(Q(title__icontains=query)|Q(content__icontains=query))[:5]
        
    total = sum(len(v) for v in results.values())
    # 🏥 SUTURA: Ruta corregida a 'social/global_search.html'
    return render(request, 'social/global_search.html', {'query': query, 'results': results, 'total_results': total})

# ==========================================================
# 🛡️ MODERACIÓN
# ==========================================================
@login_required
@require_POST
def moderar_eliminar_contenido(request):
    try:
        data = json.loads(request.body)
        if data.get('type') == 'post':
            obj = get_object_or_404(Post, id=data.get('id'))
            nombre = "Post"
        else:
            obj = get_object_or_404(Comment, id=data.get('id'))
            nombre = "Comentario"
            
        # Verificar permisos (Admin o Autor)
        if request.user == obj.autor or request.user.perfil.rol == 'ADMINISTRADOR':
            AuditLog.objects.create(
                usuario=request.user, accion='DELETE_SOCIAL', modelo_afectado=nombre, 
                detalles=f"Borrado por {request.user.username}"
            )
            obj.delete()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==========================================================
# 💬 CHAT (BUZÓN Y ENVÍO)
# ==========================================================

@login_required
def buzon_mensajes(request):
    tipo = request.GET.get('tipo', 'recibidos')
    mensajes = []
    
    if tipo == 'enviados':
        # Agrupación por destinatario
        mensajes_agrupados = MensajeInterno.objects.filter(remitente=request.user).values(
            'asunto', 'cuerpo', 'fecha_envio'
        ).annotate(
            destinatarios_count=Count('destinatario', distinct=True), 
            ultimo_destinatario_id=Max('destinatario_id') 
        ).order_by('-fecha_envio')
        
        # Hidratar objetos de usuario
        dest_ids = [m['ultimo_destinatario_id'] for m in mensajes_agrupados if m['ultimo_destinatario_id']]
        users_map = {u.id: u for u in User.objects.filter(id__in=dest_ids)}
        
        mensajes = list(mensajes_agrupados)
        for m in mensajes:
            m['ultimo_destinatario_obj'] = users_map.get(m['ultimo_destinatario_id'])
            
    else:
        mensajes = MensajeInterno.objects.filter(destinatario=request.user).select_related('remitente__perfil').order_by('-fecha_envio')

    no_leidos = MensajeInterno.objects.filter(destinatario=request.user, leido=False).count()
    # 🏥 SUTURA: Ruta corregida a 'social/chat/buzon.html'
    return render(request, 'social/chat/buzon.html', {
        'mensajes': mensajes, 'tipo_bandeja': tipo, 'mensajes_no_leidos_count': no_leidos
    })

@login_required
def enviar_mensaje(request):
    initial = {}
    if request.GET.get('destinatario'): initial['destinatario'] = request.GET.get('destinatario')
    if request.GET.get('asunto'): initial['asunto'] = request.GET.get('asunto')
    
    mensaje_original = None
    if request.GET.get('reply_to'):
        try:
             mensaje_original = MensajeInterno.objects.get(id=request.GET.get('reply_to'))
        except: pass

    if request.method == 'POST':
        form = MensajeForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            # Filtro Sentinel
            texto = f"{form.cleaned_data.get('asunto')} {form.cleaned_data.get('cuerpo')}"
            es_toxico, motivo = Sentinel.is_toxic(texto)
            
            if es_toxico:
                messages.error(request, 'Mensaje bloqueado por contenido inapropiado.')
                SecurityLog.objects.create(usuario=request.user, contenido_intentado=texto, razon_bloqueo=motivo)
                # 🏥 SUTURA: Ruta corregida a 'social/chat/enviar.html'
                return render(request, 'social/chat/enviar.html', {'form': form})
            
            # Lógica de envío (Individual o Masivo)
            destinatario = form.cleaned_data.get('destinatario')
            destinos = []
            
            if destinatario:
                destinos = [destinatario.id]
            else:
                # Lógica masiva simplificada (reutiliza la que tenías)
                rol_masivo = form.cleaned_data.get('destinatario_rol_masivo')
                curso_masivo = form.cleaned_data.get('destinatario_curso_masivo')
                qs = User.objects.exclude(id=request.user.id)
                
                if rol_masivo == 'ALL_ESTUDIANTES': qs = qs.filter(perfil__rol='ESTUDIANTE')
                elif rol_masivo == 'ALL_DOCENTES': qs = qs.filter(perfil__rol='DOCENTE')
                elif curso_masivo: 
                    est_ids = Matricula.objects.filter(curso_id=curso_masivo).values_list('estudiante_id', flat=True)
                    qs = qs.filter(id__in=est_ids)
                
                destinos = list(qs.values_list('id', flat=True))

            if destinos:
                # Crear primer mensaje
                principal = form.save(commit=False)
                principal.remitente = request.user
                principal.destinatario_id = destinos[0]
                principal.save()
                
                # Bulk create para el resto
                clones = [
                    MensajeInterno(
                        remitente=request.user, destinatario_id=uid, 
                        asunto=principal.asunto, cuerpo=principal.cuerpo, archivo=principal.archivo
                    ) for uid in destinos[1:]
                ]
                MensajeInterno.objects.bulk_create(clones)
                messages.success(request, f'Mensaje enviado a {len(destinos)} usuarios.')
                return redirect('buzon_mensajes')
            else:
                messages.error(request, 'No se encontraron destinatarios.')
    else:
        form = MensajeForm(request.user, initial=initial)

    # 🏥 SUTURA: Ruta corregida a 'social/chat/enviar.html'
    return render(request, 'social/chat/enviar.html', {'form': form, 'mensaje_original': mensaje_original})

@login_required
def leer_mensaje(request, mensaje_id):
    msg = get_object_or_404(MensajeInterno, id=mensaje_id)
    if request.user not in [msg.destinatario, msg.remitente]:
        messages.error(request, "Acceso denegado.")
        return redirect('buzon_mensajes')

    otro = msg.remitente if msg.destinatario == request.user else msg.destinatario
    
    # Marcar leídos
    MensajeInterno.objects.filter(remitente=otro, destinatario=request.user, leido=False).update(leido=True)
    
    # Historial
    historial = MensajeInterno.objects.filter(
        (Q(remitente=request.user) & Q(destinatario=otro)) |
        (Q(remitente=otro) & Q(destinatario=request.user))
    ).order_by('fecha_envio')

    if request.method == 'POST':
        cuerpo = request.POST.get('cuerpo', '').strip()
        archivo = request.FILES.get('archivo')
        if cuerpo or archivo:
             # Sentinel check
             if cuerpo and Sentinel.is_toxic(cuerpo)[0]:
                 messages.error(request, 'Respuesta bloqueada por contenido ofensivo.')
             else:
                 MensajeInterno.objects.create(remitente=request.user, destinatario=otro, cuerpo=cuerpo, archivo=archivo)
                 return redirect('leer_mensaje', mensaje_id=mensaje_id)

    # 🏥 SUTURA: Ruta corregida a 'social/chat/leer.html'
    return render(request, 'social/chat/leer.html', {'mensaje_actual': msg, 'otro_usuario': otro, 'historial': historial})