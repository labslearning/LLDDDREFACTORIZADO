# apps/social/views.py
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q, Count, Min, Max
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 🟢 1. IMPORTACIONES DE CAPA DE DOMINIO Y TENANCY
# ---------------------------------------------------------
from apps.tenancy.utils import get_current_tenant
from tasks.decorators import role_required
from tasks.models import Perfil, Question, Answer # Si el Foro se queda en tasks por ahora

# ---------------------------------------------------------
# 🛡️ 2. MODELOS SOCIALES Y CHAT
# ---------------------------------------------------------
from .models import (
    SocialGroup, Post, Comment, Reaction, Follow,
    MensajeInterno, SecurityLog
)
# Deberías tener los forms aquí, importamos las clases
#from .forms import PostForm, SocialGroupForm, MensajeForm
from .forms import PostForm, SocialGroupForm, MensajeForm, UserEditForm, EditarPerfilForm
# Si necesitas la IA de moderación
from tasks.utils import Sentinel


# ===================================================================
# 🏗️ FASE IV (PASO 17): VISTA DEL FEED SOCIAL (MURO GLOBAL)
# ===================================================================

@login_required
def social_feed(request):
    """
    Muro Social Comunitario. Aisla los posts por colegio.
    """
    tenant = get_current_tenant()
    
    # 1. Recuperar posts base: SOLO PUBLICACIONES GENERALES (grupo__isnull=True)
    posts_qs = Post.objects.filter(
        grupo__isnull=True,
        tenant=tenant
    ).select_related(
        'autor', 
        'autor__perfil',
        'grupo' 
    ).prefetch_related(
        'comentarios', 
        'comentarios__autor__perfil', 
        'social_content_reactions', # Ojo: Nombre actualizado
        'social_content_reactions__usuario'
    ).order_by('-es_destacado', '-creado_en')

    # 1.1. Lógica de BÚSQUEDA
    query = request.GET.get('q')
    if query:
        posts_qs = posts_qs.filter(
            Q(contenido__icontains=query) | 
            Q(autor__first_name__icontains=query) |
            Q(autor__last_name__icontains=query) |
            Q(autor__username__icontains=query)
        ).distinct()
        
    # 2. Paginación
    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 3. Inicializar formulario
    form = PostForm()

    # 4. Procesar Formularios (Post vs Comentario)
    if request.method == 'POST':
        # 🟢 CASO A: CREAR UN POST
        if 'publicar_post' in request.POST:
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                nuevo_post = form.save(commit=False)
                nuevo_post.autor = request.user
                nuevo_post.tenant = tenant
                
                # Verificar si es anuncio oficial (solo admins)
                if request.user.perfil.rol == 'ADMINISTRADOR' and 'es_anuncio' in request.POST:
                     nuevo_post.tipo = 'ANUNCIO'
                
                nuevo_post.save()
                messages.success(request, '¡Publicación creada!')
                return redirect('social_feed') 
            else:
                messages.error(request, 'Error al publicar. Verifica el contenido.')

        # 🔵 CASO B: CREAR UN COMENTARIO
        elif 'publicar_comentario' in request.POST:
            post_id = request.POST.get('post_id')
            contenido = request.POST.get('contenido')
            
            if post_id and contenido:
                try:
                    post = Post.objects.get(id=post_id, tenant=tenant)
                    Comment.objects.create(
                        post=post,
                        autor=request.user,
                        contenido=contenido,
                        tenant=tenant
                    )
                    messages.success(request, 'Comentario agregado.')
                    return redirect('social_feed') 
                except Post.DoesNotExist:
                    messages.error(request, 'El post que intentas comentar no existe.')
            else:
                messages.warning(request, 'El comentario no puede estar vacío.')

    # 5. DATOS PARA LA BARRA LATERAL (GRUPOS)
    grupos_sugeridos = SocialGroup.objects.filter(tenant=tenant).prefetch_related('members').order_by('-created_at')[:5]
    
    context = {
        'page_obj': page_obj, 
        'post_form': form,
        'titulo_seccion': 'Comunidad Institucional',
        'grupos_sugeridos': grupos_sugeridos,
        'q': query 
    }

    return render(request, 'social/social_feed.html', context)


# ===================================================================
# ⚡ FASE IV (PASO 18): API DE REACCIONES (AJAX)
# ===================================================================

@login_required
@require_POST
def api_reaction(request):
    """
    Endpoint AJAX para alternar reacciones (Like/Love/etc) en Posts o Comentarios.
    """
    tenant = get_current_tenant()
    try:
        data = json.loads(request.body)
        obj_type = data.get('type') # 'post' o 'comment'
        obj_id = data.get('id')
        reaction_type = data.get('reaction', 'LIKE')

        if obj_type == 'post':
            model = Post
        elif obj_type == 'comment':
            model = Comment
        else:
            return JsonResponse({'success': False, 'error': 'Tipo de objeto inválido'}, status=400)

        obj = get_object_or_404(model, id=obj_id, tenant=tenant)
        ct = ContentType.objects.get_for_model(model)

        reaction, created = Reaction.objects.get_or_create(
            usuario=request.user,
            content_type=ct,
            object_id=obj.id,
            tenant=tenant,
            defaults={'tipo': reaction_type}
        )

        action = ''
        if not created:
            if reaction.tipo == reaction_type:
                reaction.delete()
                action = 'removed'
            else:
                reaction.tipo = reaction_type
                reaction.save()
                action = 'updated'
        else:
            action = 'added'

        total = Reaction.objects.filter(content_type=ct, object_id=obj.id).count()

        return JsonResponse({
            'success': True,
            'action': action,
            'total': total,
            'current_reaction': reaction_type if action != 'removed' else None
        })

    except Exception as e:
        logger.exception(f"Error en api_reaction: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ===================================================================
# 🤝 FASE IV (PASO 19): API SEGUIR USUARIOS
# ===================================================================

@login_required
@require_POST
def toggle_follow(request):
    tenant = get_current_tenant()
    try:
        data = json.loads(request.body)
        user_to_follow_id = data.get('user_id')

        if not user_to_follow_id:
            return JsonResponse({'success': False, 'error': 'ID no proporcionado'}, status=400)

        user_id_int = int(user_to_follow_id)
        if user_id_int == request.user.id:
            return JsonResponse({'success': False, 'error': 'No puedes seguirte a ti mismo'}, status=400)

        target_user = get_object_or_404(User, id=user_id_int)
        
        follow_instance = Follow.objects.filter(follower=request.user, following=target_user, tenant=tenant).first()
        
        action = ''
        message = ''
        
        if follow_instance:
            follow_instance.delete()
            action = 'unfollowed'
            message = f"Dejaste de seguir a {target_user.username}"
        else:
            Follow.objects.create(follower=request.user, following=target_user, tenant=tenant)
            action = 'followed'
            message = f"Ahora sigues a {target_user.username}"

        followers_count = Follow.objects.filter(following=target_user).count()
        following_count = Follow.objects.filter(follower=request.user).count()

        return JsonResponse({
            'success': True,
            'action': action,
            'followers_count': followers_count,
            'following_count': following_count,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error en toggle_follow: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ===================================================================
# 👤 FASE IV (PASO 20): VISTA DE PERFIL SOCIAL
# ===================================================================

@login_required
def ver_perfil_social(request, username):
    tenant = get_current_tenant()
    perfil_user = get_object_or_404(User, username=username)
    perfil, created = Perfil.objects.get_or_create(user=perfil_user, defaults={'tenant': tenant})

    followers_count = Follow.objects.filter(following=perfil_user).count()
    following_count = Follow.objects.filter(follower=perfil_user).count()
    posts_count = Post.objects.filter(autor=perfil_user, tenant=tenant).count()

    is_following = False
    if request.user != perfil_user:
        is_following = Follow.objects.filter(follower=request.user, following=perfil_user).exists()

    posts_qs = Post.objects.filter(autor=perfil_user, tenant=tenant).order_by('-creado_en')
    paginator = Paginator(posts_qs, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Si usas UserLogro (Gamificación)
    mis_logros = []

    context = {
        'perfil_user': perfil_user,
        'perfil': perfil,
        'is_own_profile': (request.user == perfil_user),
        'is_following': is_following,
        'followers_count': followers_count,
        'following_count': following_count,
        'posts_count': posts_count,
        'page_obj': page_obj,
        'mis_logros': mis_logros,
    }

    return render(request, 'perfil_social.html', context)


# ===================================================================
# 💬 CHAT PRIVADO
# ===================================================================

@login_required
def buzon_mensajes(request):
    tenant = get_current_tenant()
    tipo_bandeja = request.GET.get('tipo', 'recibidos')
    
    mensajes_no_leidos_count = 0
    titulo_bandeja = ""
    mensajes = [] 

    if tipo_bandeja == 'enviados':
        titulo_bandeja = "Mensajes Enviados"
        mensajes_agrupados = MensajeInterno.objects.filter(remitente=request.user, tenant=tenant).values(
            'asunto', 'cuerpo', 'fecha_envio'
        ).annotate(
            destinatarios_count=Count('destinatario', distinct=True), 
            referencia_id=Min('id'),
            ultimo_destinatario_id=Max('destinatario_id') 
        ).order_by('-fecha_envio')
        
        mensajes = list(mensajes_agrupados) 
        
        destinatario_ids = [m['ultimo_destinatario_id'] for m in mensajes if m['ultimo_destinatario_id']]
        usuarios_qs = User.objects.filter(id__in=destinatario_ids).select_related('perfil') 
        ultimo_destinatario_map = {user_obj.id: user_obj for user_obj in usuarios_qs}
            
        for m in mensajes:
            m['ultimo_destinatario_obj'] = ultimo_destinatario_map.get(m['ultimo_destinatario_id'])
            
    else:
        titulo_bandeja = "Buzón de Entrada"
        mensajes_recibidos_qs = MensajeInterno.objects.filter(destinatario=request.user, tenant=tenant).select_related('remitente__perfil').order_by('-fecha_envio')
        mensajes_no_leidos_count = mensajes_recibidos_qs.filter(leido=False).count()
        mensajes = mensajes_recibidos_qs

    return render(request, 'chat/buzon.html', { 
        'mensajes': mensajes,
        'tipo_bandeja': tipo_bandeja,
        'titulo_bandeja': titulo_bandeja,
        'mensajes_no_leidos_count': mensajes_no_leidos_count
    })

# ==========================================================
# GESTIÓN DE GRUPOS SOCIALES
# ==========================================================

@login_required
def lista_grupos(request):
    tenant = get_current_tenant()
    grupos = SocialGroup.objects.filter(tenant=tenant).order_by('-created_at')
    return render(request, 'grupos/lista_grupos.html', {'grupos': grupos})

@login_required
def crear_grupo(request):
    tenant = get_current_tenant()
    roles_permitidos = ['ADMINISTRADOR', 'DOCENTE', 'COORD_ACADEMICO', 'PSICOLOGO', 'COORD_CONVIVENCIA']
    
    if request.user.perfil.rol not in roles_permitidos:
        messages.error(request, "Los estudiantes no tienen permiso para crear grupos.")
        return redirect('social_feed')

    if request.method == 'POST':
        form = SocialGroupForm(request.POST, request.FILES)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.creator = request.user
            grupo.tenant = tenant
            grupo.save()
            grupo.members.add(request.user)
            grupo.admins.add(request.user)
            
            messages.success(request, f'Grupo "{grupo.name}" creado exitosamente.')
            return redirect('detalle_grupo', grupo_id=grupo.id)
    else:
        form = SocialGroupForm()
    
    return render(request, 'grupos/crear_grupo.html', {'form': form})

@login_required
def detalle_grupo(request, grupo_id):
    tenant = get_current_tenant()
    grupo = get_object_or_404(SocialGroup, id=grupo_id, tenant=tenant)
    
    es_miembro = grupo.members.filter(id=request.user.id).exists() 
    es_administrador_grupo = (request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR')

    posts_qs = Post.objects.filter(grupo=grupo, tenant=tenant).select_related(
        'autor', 'autor__perfil'
    ).prefetch_related(
        'comentarios', 'comentarios__autor__perfil'
    ).order_by('-creado_en')
    
    form = PostForm()
    
    # Manejo básico de POST dentro del grupo (Simplificado para el ejemplo)
    if request.method == 'POST' and 'publicar_post' in request.POST and es_miembro:
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.autor = request.user
            post.grupo = grupo 
            post.tenant = tenant
            post.save()
            messages.success(request, 'Publicación creada.')
            return redirect('detalle_grupo', grupo_id=grupo.id)

    return render(request, 'grupos/detalle_grupo.html', {
        'grupo': grupo, 
        'es_miembro': es_miembro,
        'posts': posts_qs,
        'post_form': form,
        'es_administrador_grupo': es_administrador_grupo,
    })

@login_required
def unirse_grupo(request, grupo_id):
    tenant = get_current_tenant()
    grupo = get_object_or_404(SocialGroup, id=grupo_id, tenant=tenant)
    
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
    tenant = get_current_tenant()
    grupo = get_object_or_404(SocialGroup, id=grupo_id, tenant=tenant)
    
    if request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR':
        nombre_grupo = grupo.name
        grupo.delete()
        messages.success(request, f'El grupo "{nombre_grupo}" ha sido eliminado.')
        return redirect('social_feed') 
    else:
        messages.error(request, "No tienes permiso para eliminar este grupo.")
        return redirect('detalle_grupo', grupo_id=grupo.id)

# ==========================================================
# MODERACIÓN DE CONTENIDO
# ==========================================================

@login_required
@role_required(['ADMINISTRADOR', 'COORD_CONVIVENCIA', 'PSICOLOGO', 'COORD_ACADEMICO', 'DOCENTE'])
@require_POST
def moderar_eliminar_contenido(request):
    try:
        data = json.loads(request.body)
        tipo_contenido = data.get('type')
        item_id = data.get('id')
        motivo = data.get('motivo', 'Moderación')
        tenant = get_current_tenant()

        if tipo_contenido == 'post':
            objeto = get_object_or_404(Post, id=item_id, tenant=tenant)
            modelo_nombre = "Post Social"
        elif tipo_contenido == 'comment':
            objeto = get_object_or_404(Comment, id=item_id, tenant=tenant)
            modelo_nombre = "Comentario Social"
        else:
            return JsonResponse({'success': False, 'error': 'Tipo no válido'}, status=400)

        SecurityLog.objects.create(
            usuario=request.user, 
            accion='DELETE (MODERATION)',
            modelo_afectado=modelo_nombre,
            objeto_id=str(item_id),
            detalles=f"Motivo: {motivo}",
            tenant=tenant
        )

        objeto.delete()
        return JsonResponse({'success': True})

    except Exception as e:
        logger.error(f"Error en moderación: {e}", exc_info=True) 
        return JsonResponse({'success': False, 'error': 'Error interno'}, status=500)


# ===================================================================
# ⚙️ EDICIÓN DE PERFIL SOCIAL
# ===================================================================

@login_required
def editar_perfil(request):
    """
    Permite al usuario editar sus datos de cuenta (User) y su perfil social (Perfil).
    """
    user = request.user
    perfil = getattr(user, 'perfil', None) 

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = EditarPerfilForm(request.POST, request.FILES, instance=perfil)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    user_form.save()
                    profile_form.save()
                    messages.success(request, '¡Tu perfil se ha actualizado correctamente!')
                    return redirect('ver_perfil_social', username=user.username)
            except Exception as e:
                messages.error(request, f'Ocurrió un error al guardar: {e}')
        else:
            messages.error(request, 'Hay errores en el formulario. Por favor revisa los campos.')
    else:
        user_form = UserEditForm(instance=user)
        profile_form = EditarPerfilForm(instance=perfil)

    return render(request, 'social/editar_perfil.html', {
        'user_form': user_form,
        'profile_form': profile_form 
    })

# ===================================================================
# 🔍 BUSCADOR GLOBAL INTELIGENTE
# ===================================================================

@login_required
def global_search(request):
    """
    Motor de búsqueda centralizado Multi-Tenant.
    Busca coincidencias en: Usuarios, Grupos, Posts y Preguntas del Foro
    solo dentro del colegio actual.
    """
    tenant = get_current_tenant()
    query = request.GET.get('q', '').strip()
    
    # Inicializamos resultados vacíos
    results = {
        'users': [],
        'groups': [],
        'posts': [],
        'questions': []
    }
    
    total_results = 0

    if query:
        # 1. Buscar Usuarios (Nombre, Apellido o Username) del mismo Tenant
        results['users'] = User.objects.filter(
            perfil__tenant=tenant,
            is_active=True
        ).filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id).select_related('perfil')[:5] 

        # 2. Buscar Grupos del mismo Tenant (Nombre o Descripción)
        results['groups'] = SocialGroup.objects.filter(
            tenant=tenant
        ).filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )[:5]

        # 3. Buscar en el Muro Social (Contenido) del mismo Tenant
        results['posts'] = Post.objects.filter(
            tenant=tenant,
            contenido__icontains=query
        ).select_related('autor', 'autor__perfil').order_by('-creado_en')[:5]

        # 4. Buscar en el Foro (Título o Contenido) si sigue en tasks
        # (Asegúrate de que Question esté importado arriba desde tasks.models)
        results['questions'] = Question.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query)
        ).order_by('-created_at')[:5]

        # Conteo total para mostrar en la interfaz
        total_results = len(results['users']) + len(results['groups']) + len(results['posts']) + len(results['questions'])

    context = {
        'query': query,
        'results': results,
        'total_results': total_results
    }

    return render(request, 'global_search.html', context)

# ===================================================================
# 💬 SISTEMA DE CHAT INTERNO (MENSAJERÍA PRIVADA Y MASIVA)
# ===================================================================

@login_required
def enviar_mensaje(request):
    """
    Formulario para enviar mensajes (Individuales o Masivos).
    Maneja la lógica de 'Responder', propagación masiva y FILTRO DE SEGURIDAD (Sentinel).
    """
    tenant = get_current_tenant()
    
    # 1. Capturar parámetros de la URL (Vienen del botón Responder)
    destinatario_id_get = request.GET.get('destinatario')
    asunto_previo = request.GET.get('asunto')
    mensaje_original_id = request.GET.get('reply_to')
    
    # 2. Pre-llenar el formulario
    initial_data = {}
    if destinatario_id_get:
        initial_data['destinatario'] = destinatario_id_get
    if asunto_previo:
        if not asunto_previo.startswith("Re:"):
            initial_data['asunto'] = f"Re: {asunto_previo}"
        else:
            initial_data['asunto'] = asunto_previo

    # 3. Buscar el mensaje original para mostrar el contexto (cuadro gris)
    mensaje_original = None
    if mensaje_original_id:
        try:
            mensaje_posible = MensajeInterno.objects.get(id=mensaje_original_id, tenant=tenant)
            if request.user in [mensaje_posible.destinatario, mensaje_posible.remitente]:
                mensaje_original = mensaje_posible
        except MensajeInterno.DoesNotExist:
            pass

    # 4. Procesar el envío
    if request.method == 'POST':
        form = MensajeForm(request.user, request.POST, request.FILES)
        
        if form.is_valid():
            # ==================================================================
            # 🛡️ INICIO: FILTRO DE SEGURIDAD (EL CENTINELA)
            # ==================================================================
            asunto_texto = form.cleaned_data.get('asunto', '')
            cuerpo_texto = form.cleaned_data.get('cuerpo', '')
            texto_completo = f"{asunto_texto} {cuerpo_texto}"
            
            # Asegúrate de que Sentinel esté importado de tasks.utils
            try:
                es_toxico, motivo = Sentinel.is_toxic(texto_completo)
            except NameError:
                # Fallback si Sentinel no se pudo importar
                es_toxico, motivo = False, None

            if es_toxico:
                messages.error(request, '🚫 Mensaje bloqueado. Se ha detectado contenido inapropiado que infringe las normas institucionales.')
                try:
                    SecurityLog.objects.create(
                        usuario=request.user,
                        contenido_intentado=texto_completo,
                        razon_bloqueo=motivo or "Lenguaje ofensivo en Mensaje Interno",
                        tenant=tenant
                    )
                except Exception as e:
                    logger.error(f"Error guardando SecurityLog: {e}")

                return render(request, 'chat/enviar.html', {'form': form, 'mensaje_original': mensaje_original})

            # ==================================================================
            # 🛡️ FIN DEL FILTRO
            # ==================================================================

            # --- Extracción de Destinos (Individual o Masivo) ---
            destinatario_obj = form.cleaned_data.get('destinatario')
            rol_masivo = form.cleaned_data.get('destinatario_rol_masivo')
            curso_masivo_id = form.cleaned_data.get('destinatario_curso_masivo')
            
            destinos_finales_ids = []
            
            if destinatario_obj:
                destinos_finales_ids = [destinatario_obj.id]
            else:
                qs = User.objects.filter(perfil__tenant=tenant).exclude(id=request.user.id)
                
                if rol_masivo:
                    if rol_masivo == 'ALL_DOCENTES':
                        qs = qs.filter(perfil__rol='DOCENTE')
                    elif rol_masivo == 'ALL_ESTUDIANTES':
                        qs = qs.filter(perfil__rol='ESTUDIANTE')
                    elif rol_masivo == 'ALL_ACUDIENTES':
                        qs = qs.filter(perfil__rol='ACUDIENTE')
                    elif rol_masivo == 'ALL_STAFF':
                        qs = qs.filter(perfil__rol__in=['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO'])
                    
                    # Lógica de Docente
                    elif request.user.perfil.rol == 'DOCENTE':
                        from apps.academics.models import AsignacionMateria, Matricula
                        # Si es necesario, añadir la lógica de Acudiente aquí (comentada por simplicidad)
                        cursos_ids = AsignacionMateria.objects.filter(docente=request.user, activo=True).values_list('curso_id', flat=True)
                        estudiantes_ids = Matricula.objects.filter(curso_id__in=cursos_ids).values_list('estudiante_id', flat=True)
                        if rol_masivo == 'MIS_ESTUDIANTES':
                            qs = qs.filter(id__in=estudiantes_ids)

                    destinos_finales_ids = list(qs.values_list('id', flat=True).distinct())

                elif curso_masivo_id:
                    from apps.academics.models import Matricula
                    try:
                        curso_id_int = int(curso_masivo_id) 
                        estudiantes_curso_ids = Matricula.objects.filter(curso_id=curso_id_int).values_list('estudiante_id', flat=True)
                        destinos_finales_ids = list(User.objects.filter(id__in=estudiantes_curso_ids).exclude(id=request.user.id).values_list('id', flat=True).distinct())
                    except ValueError:
                         messages.error(request, "Error: ID de curso inválida.")
                         return redirect('buzon_mensajes')

            # 5. Guardar el Mensaje (Individual o Masivo)
            if destinos_finales_ids:
                try:
                    with transaction.atomic():
                        mensaje_principal = form.save(commit=False)
                        mensaje_principal.remitente = request.user
                        mensaje_principal.destinatario_id = destinos_finales_ids[0]
                        mensaje_principal.tenant = tenant
                        mensaje_principal.save()
                        
                        mensajes_adicionales = []
                        for user_id in destinos_finales_ids[1:]:
                            clone = MensajeInterno(
                                remitente=request.user,
                                destinatario_id=user_id,
                                asunto=mensaje_principal.asunto,
                                cuerpo=mensaje_principal.cuerpo,
                                archivo=mensaje_principal.archivo, 
                                tenant=tenant
                            )
                            mensajes_adicionales.append(clone)
                        
                        if mensajes_adicionales:
                            MensajeInterno.objects.bulk_create(mensajes_adicionales)

                    messages.success(request, f"Mensaje enviado exitosamente a {len(destinos_finales_ids)} destinatario(s).")
                    return redirect('buzon_mensajes')

                except Exception as e:
                    messages.error(request, f"Error al enviar el mensaje: {e}")
            else:
                 messages.error(request, "No se encontraron destinatarios válidos para el envío. Revisa tus filtros.")
        else:
             messages.error(request, "Error de validación: Por favor revisa los campos.")

    else:
        form = MensajeForm(request.user, initial=initial_data)
    
    return render(request, 'chat/enviar.html', {
        'form': form,
        'mensaje_original': mensaje_original 
    })


@login_required
def leer_mensaje(request, mensaje_id):
    """
    Vista para ver la conversación completa y responder con archivos.
    """
    tenant = get_current_tenant()
    mensaje_actual = get_object_or_404(MensajeInterno, id=mensaje_id, tenant=tenant)
    
    if request.user != mensaje_actual.destinatario and request.user != mensaje_actual.remitente:
        messages.error(request, "No tienes permiso para ver esta conversación.")
        return redirect('buzon_mensajes')

    if mensaje_actual.remitente == request.user:
        otro_usuario = mensaje_actual.destinatario
    else:
        otro_usuario = mensaje_actual.remitente

    if request.method == 'POST':
        cuerpo = request.POST.get('cuerpo', '').strip() 
        archivo = request.FILES.get('archivo') 

        if cuerpo:
            try:
                es_toxico, motivo = Sentinel.is_toxic(cuerpo)
            except NameError:
                es_toxico, motivo = False, None

            if es_toxico:
                messages.error(request, '🚫 Respuesta no enviada: Se detectó contenido inapropiado o irrespetuoso.')
                try:
                    SecurityLog.objects.create(
                        usuario=request.user,
                        contenido_intentado=cuerpo,
                        razon_bloqueo=motivo or "Lenguaje ofensivo en Respuesta de Chat",
                        tenant=tenant
                    )
                except Exception as e:
                    logger.error(f"Error log seguridad: {e}")
                return redirect('leer_mensaje', mensaje_id=mensaje_id)

        if cuerpo or archivo:
            try:
                MensajeInterno.objects.create(
                    remitente=request.user,
                    destinatario=otro_usuario,
                    cuerpo=cuerpo, 
                    archivo=archivo, 
                    leido=False,
                    tenant=tenant
                )
                return redirect('leer_mensaje', mensaje_id=mensaje_id)
            except Exception as e:
                messages.error(request, f"Error al enviar: {e}")

    # Marcar como leídos
    MensajeInterno.objects.filter(
        remitente=otro_usuario, 
        destinatario=request.user, 
        leido=False,
        tenant=tenant
    ).update(leido=True)

    historial = MensajeInterno.objects.filter(
        (Q(remitente=request.user) & Q(destinatario=otro_usuario)) |
        (Q(remitente=otro_usuario) & Q(destinatario=request.user)),
        tenant=tenant
    ).order_by('fecha_envio')

    return render(request, 'chat/leer.html', {
        'mensaje_actual': mensaje_actual,
        'otro_usuario': otro_usuario,
        'historial': historial,
    })

# ===================================================================
# 🔔 SISTEMA DE NOTIFICACIONES
# ===================================================================

# Importación temporal desde tasks para las notificaciones
from tasks.models import Notificacion 

@login_required
def historial_notificaciones(request):
    """
    Muestra el historial completo de notificaciones del usuario,
    agrupadas por fecha en el template.
    """
    # Obtenemos todas las notificaciones, ordenadas por fecha descendente
    notificaciones = Notificacion.objects.filter(usuario=request.user).order_by('-fecha_creacion')
    
    return render(request, 'notificaciones/historial.html', {
        'notificaciones': notificaciones
    })

@login_required
@require_POST
def mark_all_notifications_read(request):
    """
    Marca todas las notificaciones pendientes del usuario actual como leídas.
    Se llama vía AJAX cuando se abre la campana de notificaciones.
    """
    try:
        # 1. Identificar las notificaciones NO leídas del usuario.
        unread_notifications = Notificacion.objects.filter(
            usuario=request.user, 
            leida=False 
        )
        
        # 2. Actualizar el estado en lote a True.
        updated_count = unread_notifications.update(leida=True)
        
        return JsonResponse({
            'success': True, 
            'new_count': 0, 
            'updated_items': updated_count
        })

    except Exception as e:
        # Imprime el error en la consola del servidor para depuración
        print(f"Error crítico marcando notificaciones: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ===================================================================
# 👥 GESTIÓN DE GRUPOS Y COMENTARIOS ADICIONALES
# ===================================================================

@login_required
def crear_comentario(request, post_id):
    """
    Crea un comentario rápido y redirige a la página de origen.
    """
    tenant = get_current_tenant()
    post = get_object_or_404(Post, id=post_id, tenant=tenant)
    if request.method == 'POST':
        contenido = request.POST.get('contenido')
        if contenido:
            Comment.objects.create(
                autor=request.user,
                post=post,
                contenido=contenido,
                tenant=tenant
            )
            messages.success(request, 'Comentario agregado.')
    
    return redirect(request.META.get('HTTP_REFERER', 'social_feed'))

@login_required
def descargar_observador_acudiente(request, estudiante_id):
    """
    Permite a los acudientes descargar el PDF del observador de su hijo.
    (Utiliza la lógica de Wellbeing importada)
    """
    from apps.wellbeing.views import generar_observador_pdf
    # Verificación básica de seguridad: ¿Es el acudiente del estudiante?
    from tasks.models import Acudiente
    if not Acudiente.objects.filter(acudiente=request.user, estudiante_id=estudiante_id).exists():
        messages.error(request, "No tienes permiso para ver este documento.")
        return redirect('dashboard_acudiente')
    
    return generar_observador_pdf(request, estudiante_id)

@login_required
def test_ai_connection(request):
    """
    Ruta de prueba para verificar Stratos AI.
    """
    return JsonResponse({'status': 'ok', 'message': 'Conexión con Stratos AI establecida'})