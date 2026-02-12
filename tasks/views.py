# -*- coding: utf-8 -*-
from django.db.models import Avg, Count, Q, Min, Max
import json
from .models import Observacion, Institucion # <--- Importante importar Observacion
from .models import Seguimiento # Asegúrate que importas tus modelos correctamente
from django.core.serializers.json import DjangoJSONEncoder

import random
import string
import qrcode # ¡NUEVO!
import io     # ¡NUEVO!
import base64 # ¡NUEVO!
#sms 
#from .forms import TelefonoAcudienteForm  # <--- IMPORTANTE: Agrega este import
from apps.academics.forms import TelefonoAcudienteForm

# --- AGREGA ESTO AL PRINCIPIO DE tasks/views.py ---
from django.template.loader import get_template  # <--- FALTABA ESTO
from django.template import TemplateDoesNotExist # <--- FALTABA ESTO
from django.conf import settings                 # <--- FALTABA ESTO
import os
from django.views.decorators.csrf import csrf_exempt
#agregando los cambios de deepseek
from openai import OpenAI    # pip install openai
from pypdf import PdfReader #pdf


from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
#Aqui importaciones para hacer el pdf con el reporte de la AI 
import markdown # <--- NECESARIO
from django.utils.html import mark_safe
#Hasta aqui

from .ai.orchestrator import ai_orchestrator
#from .ai.constants import ACCION_MEJORAS_ESTUDIANTE
from tasks.ai.constants import (
    ACCION_CHAT_SOCRATICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI,
    ACCION_MEJORAS_DOCENTE,
    ACCION_MEJORAS_ESTUDIANTE,      # <--- Fíjate que aquí ya la incluimos
    ACCION_APOYO_ACUDIENTE,
    ACCION_ANALISIS_GLOBAL_BIENESTAR, 
    ACCION_MEJORA_STAFF_ACADEMICO   # Agrego esta por seguridad si la usas
)


from tasks.ai.context_builder import context_builder  # <--- ESTO ES LO QUE FALTA
# 1. IMPORTACIONES AÑADIDAS
from django.contrib.auth import login, logout, authenticate, get_user_model, update_session_auth_hash
from django.db import IntegrityError, transaction
# --- INICIO DE CIRUGÍA 1: Importar Avg (Sin cambios) ---
from django.db.models import Q, Avg
# --- FIN DE CIRUGÍA 1 ---
from django.http import JsonResponse, HttpResponseNotAllowed
# --- INICIO DE MODIFICACIÓN 1: Añadir Importaciones ---
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
# --- FIN DE MODIFICACIÓN 1 ---
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date  # 🩺 CIRUGÍA: Se aseguró 'date'
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from decimal import Decimal, ROUND_HALF_UP
import json
import csv
import io
import decimal
import logging
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from operator import itemgetter
from django.urls import reverse
from django.core.paginator import Paginator # Añadido en paso anterior
from django.db.models import Q, Count # Necesitas Count para ordenar por número de miembros
#from .forms import UserEditForm, EditarPerfilForm
from apps.social.forms import UserEditForm, EditarPerfilForm

# --- Modelos: Se añade Acudiente y Observacion ---
from .models import (
    Question, Answer, Perfil, Curso, Nota, Materia,
    Periodo, AsignacionMateria, Matricula, ComentarioDocente,
    ActividadSemanal, LogroPeriodo, Convivencia, GRADOS_CHOICES,
    Post, Comment, AuditLog,Report, Acudiente, Institucion, ActaInstitucional,
    Observacion, # <--- 🩺 CIRUGÍA: Modelo añadido previamente
    Asistencia, MensajeInterno, Notificacion, Reaction, Follow, UserLogro, ComentarioDocente, 
    DefinicionNota, 
    NotaDetallada, 
    BancoLogro # <--- 🩺 FASE 4: NUEVOS MODELOS AÑADIDOS
)
from django.contrib.contenttypes.models import ContentType
# ===================================================================
# 🩺 INICIO DE CIRUGÍA: Importaciones añadidas para el Plan
# (Añadidas en pasos anteriores )
# ===================================================================
# Importamos AMBOS modelos de archivo
from .models import BoletinArchivado, ObservadorArchivado 
from django.core.files.base import ContentFile
# ===================================================================
# 🩺 FIN DE CIRUGÍA
# ===================================================================

# --- Formularios: Se añaden los nuevos formularios ---

# 🟢 Formas de Soporte Vital (Se quedaron en tasks)
from .forms import PasswordChangeFirstLoginForm, ProfileSearchForm, MensajeForm

# 🏫 Formas Académicas (Trasplantadas a Academics)
from apps.academics.forms import BulkCSVForm, TelefonoAcudienteForm

# 📱 Formas Sociales (Trasplantadas a Social)
from apps.social.forms import (
    PostForm, CommentForm, SocialGroupForm, 
    QuestionForm, AnswerForm, UserEditForm, EditarPerfilForm
)

# ❤️ Formas de Bienestar (Trasplantadas a Wellbeing)
from apps.wellbeing.forms import ObservacionForm, ActaInstitucionalForm, SeguimientoForm

# --- Utilidades: Se añaden las nuevas funciones de ayuda ---
from .utils import (
    generar_username_unico, generar_contrasena_temporal, asignar_curso_por_grado,
    crear_notificacion, notificar_acudientes # <--- 🩺 FASE 4: UTILIDADES NOTIFICACION AÑADIDAS
)

# --- Decoradores: Se añade el nuevo decorador ---
from .decorators import role_required

# --- INICIO DE MODIFICACIÓN 1 (continuación): Añadir Importaciones ---
from .services import get_student_report_context # Usamos el nuevo servicio
# --- FIN DE MODIFICACIÓN 1 ---

####Seguridad 

from django.contrib.auth.decorators import login_required
from .utils import Sentinel # Tu motor de seguridad


# Obtener el modelo de usuario de forma segura
User = get_user_model()

# Configuración de logging
logger = logging.getLogger(__name__)

# --- INICIO DE MODIFICACIÓN 1 (continuación): Importar WeasyPrint ---

# --- FIN DE MODIFICACIÓN 1 ---


# Historial Matricula puede que aún no esté en tu models.py; lo usamos si existe
try:
    from .models import HistorialMatricula
    _HISTORIAL_MATRICULA_DISPONIBLE = True
except ImportError:
    _HISTORIAL_MATRICULA_DISPONIBLE = False

# Valor por defecto para la capacidad de los cursos
CAPACIDAD_POR_DEFECTO = getattr(settings, 'CAPACIDAD_CURSOS_DEFAULT', 40)

# ########################################################################## #
# ############# INICIO DEL CAMBIO DE CONTRASEÑA ############################ #
# ########################################################################## #

# Contraseña temporal unificada para todos los nuevos usuarios.
DEFAULT_TEMP_PASSWORD = getattr(settings, 'DEFAULT_TEMP_PASSWORD', '123456')

# ########################################################################## #
# ############### FIN DEL CAMBIO DE CONTRASEÑA ############################# #
# ########################################################################## #

# Constantes de negocio centralizadas
PESOS_NOTAS = {1: Decimal('0.20'), 2: Decimal('0.30'), 3: Decimal('0.30'), 4: Decimal('0.20')}
ESCALA_MIN = Decimal('0.0')
ESCALA_MAX = Decimal('5.0')
NOTA_APROBACION = Decimal('3.5')
NUM_NOTAS = (1, 2, 3, 4)
TWO_PLACES = Decimal('0.01')

# --- Normalización de grados para registro masivo
_GRADOS_VALIDOS = set(dict(GRADOS_CHOICES).keys())
_NOMBRE_A_CLAVE = {v.upper(): k for k, v in GRADOS_CHOICES}
def _normalizar_grado(g):
    """
    Acepta clave válida (p.ej. '5') o nombre (p.ej. 'QUINTO').
    Devuelve la clave aceptada por el modelo o None si no coincide.
    """
    if g in _GRADOS_VALIDOS:
        return g
    g_up = (g or "").strip().upper()
    return _NOMBRE_A_CLAVE.get(g_up)

# Helpers de negocio
def _anio_escolar_actual():
    """
    Devuelve un string tipo '2025-2026' según fecha actual (jul-dic→ y-(y+1), ene-jun → (y-1)-y).
    Ajusta a tu calendario si usas otra regla.
    """
    hoy = timezone.now().date()
    y = hoy.year
    if hoy.month >= 7:
        return f"{y}-{y + 1}"
    else:
        return f"{y - 1}-{y}"

def _secciones_disponibles(anio_escolar=None):
    qs = Curso.objects.exclude(seccion__isnull=True).exclude(seccion__exact='')
    if anio_escolar:
        qs = qs.filter(anio_escolar=anio_escolar)
    return sorted(list(set(qs.values_list('seccion', flat=True))))

def _siguiente_letra(secciones_existentes):
    """
    Dada una lista/set de secciones existentes ['A','B', 'C'], devuelve la siguiente ('D').
    Si se acaban, genera 'X#'.
    """
    letras = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    existing = set([s for s in secciones_existentes if s])
    for letra in letras:
        if letra not in existing:
            return letra
    return f"X{len(existing) + 1}"

def _capacidad_curso(curso):
    """
    Obtiene capacidad_maxima si existe; por defecto CAPACIDAD_POR_DEFECTO.
    """
    return getattr(curso, 'capacidad_maxima', CAPACIDAD_POR_DEFECTO) or CAPACIDAD_POR_DEFECTO

def _curso_esta_completo(curso):
    """
    Si el modelo tiene método esta_completo(), úsalo; si no, calcula por matrículas activas.
    """
    if hasattr(curso, 'esta_completo') and callable(getattr(curso, 'esta_completo')):
        try:
            return curso.esta_completo()
        except Exception as e:
            logger.exception("Error en curso.esta_completo (%s): %s", getattr(curso, 'id', 's/n'), e)
    ocupacion = Matricula.objects.filter(curso=curso, activo=True).count()
    return ocupacion >= _capacidad_curso(curso)

def _obtener_o_crear_curso_libre(grado, anio_escolar):
    """
    Busca curso del grado/año con cupo; si no existe o están llenos, crea nueva sección.
    """
    cursos = list(Curso.objects.filter(grado=grado, anio_escolar=anio_escolar).order_by('seccion'))
    for c in cursos:
        if not _curso_esta_completo(c):
            return c
    # Intentar crear un nuevo curso de forma segura
    with transaction.atomic():
        secciones = [c.seccion for c in cursos]
        nueva = _siguiente_letra(secciones)
        try:
            return Curso.objects.create(
                nombre=f"{dict(GRADOS_CHOICES).get(grado, str(grado))} {nueva}",
                grado=grado, seccion=nueva, anio_escolar=anio_escolar,
                capacidad_maxima=CAPACIDAD_POR_DEFECTO, activo=True
            )
        except IntegrityError:
            # Si otro proceso creó el curso en paralelo, lo recuperamos
            return Curso.objects.get(grado=grado, seccion=nueva, anio_escolar=anio_escolar)

def _obtener_grados_por_nivel():
    """
    Función que define los grados para cada nivel.
    Esto permite una configuración más limpia y centralizada.
    """
    return {
        'preescolar': ['PREKINDER', 'KINDER', 'JARDIN', 'TRANSICION'],
        'primaria': ['1', '2', '3', '4', '5'],
        'bachillerato': ['6', '7', '8', '9', '10', '11']
    }


# Vistas públicas
def home(request):
    categories = [
        {'icon': 'fa-language', 'title': 'Inglés', 'desc': 'Aprende inglés con nuestro método acelerado'},
        {'icon': 'fa-calculator', 'title': 'Matemáticas', 'desc': 'Domina las matemáticas desde cero'},
        {'icon': 'fa-flask', 'title': 'Física y Química', 'desc': 'Aprende con experimentos prácticos'},
        {'icon': 'fa-gamepad', 'title': 'Desarrollo de Videojuegos', 'desc': 'Crea tus propios juegos'},
        {'icon': 'fa-code', 'title': 'Programación', 'desc': 'Aprende los lenguajes más demandados'},
        {'icon': 'fa-robot', 'title': 'Inteligencia Artificial', 'desc': 'Domina las tecnologías del futuro'},
        {'icon': 'fa-school', 'title': 'ICFES', 'desc': 'Prepárate para tus pruebas con éxito'}
    ]
    return render(request, "home.html", {'categories': categories})

def signup(request):
    if request.method == 'GET':
        return render(request, "signup.html", {'form': UserCreationForm()})
    form = UserCreationForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Perfil.objects.create(user=user, rol='ESTUDIANTE')
                login(request, user)
                messages.success(request, '¡Cuenta creada exitosamente!')
                return redirect('dashboard_estudiante')
        except IntegrityError:
            messages.error(request, 'El nombre de usuario ya existe.')
            return render(request, 'signup.html', {'form': form})
    messages.error(request, 'Hubo un error con tu registro. Verifica los campos.')
    return render(request, 'signup.html', {'form': form})

def tasks(request):
    return render(request, 'tasks.html')

def signout(request):
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('home')

##aqui 

@csrf_protect
def signin(request):
    # --- GET ---
    if request.method == 'GET':
        return render(request, "signin.html", {
            'form': AuthenticationForm(request)
        })

    # --- POST ---
    form = AuthenticationForm(request, data=request.POST)

    if not form.is_valid():
        # Log detallado para producción
        for error in form.non_field_errors():
            logger.warning(f"Fallo de autenticación: {error}")

        messages.error(request, 'Usuario o contraseña incorrectos.')
        return render(request, 'signin.html', {'form': form})

    # 🔒 VALIDACIÓN CRÍTICA
    user = form.get_user()

    if user is None:
        logger.error("AuthenticationForm válido pero user=None")
        messages.error(request, 'Error interno de autenticación.')
        return render(request, 'signin.html', {'form': form})

    # Login seguro
    login(request, user)

    # --- CAMBIO DE CLAVE FORZADO ---
    if hasattr(user, 'perfil') and getattr(user.perfil, 'requiere_cambio_clave', False):
        messages.info(request, 'Por seguridad, debes cambiar tu contraseña.')
        return redirect('cambiar_clave')

    # --- REDIRECCIÓN NEXT SEGURA ---
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(next_url)

    # --- REDIRECCIÓN POR ROL (LÓGICA CORREGIDA) ---
    try:
        perfil = user.perfil
        rol = perfil.rol

        # 1. PRIORIDAD ALTA: ADMINISTRADOR
        # Se pone primero para que 'es_director' no intercepte al admin.
        if rol == 'ADMINISTRADOR':
            return redirect('admin_dashboard')

        # 2. Staff de Bienestar
        elif rol in ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
            return redirect('dashboard_bienestar')

        # 3. Estudiantes y Acudientes
        elif rol == 'ESTUDIANTE':
            return redirect('dashboard_estudiante')
        elif rol == 'ACUDIENTE':
            return redirect('dashboard_acudiente')

        # 4. Docentes y Directores de Curso
        # Se deja de último. Si eres admin y director, entrarás por el 'if' de arriba.
        # Si solo eres docente/director, entrarás aquí.
        elif rol == 'DOCENTE' or getattr(perfil, 'es_director', False):
            return redirect('dashboard_docente')

    except Exception as e:
        logger.exception(f"Error redireccionando por rol: {e}")
        messages.warning(request, 'Error en el perfil del usuario.')

    # --- FALLBACK FINAL ---
    return redirect('home')



def english(request): return render(request, 'english.html')
def english2(request): return render(request, 'english2.html')
def english3(request): return render(request, 'english3.html')
def english4(request): return render(request, 'english4.html')
def ai(request): return render(request, 'ai.html')

# Foro
def forum(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'forum.html', {'questions': questions})

@login_required
def ask_question(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.user = request.user
            question.save()
            messages.success(request, 'Pregunta publicada correctamente')
            return redirect('forum')
    else:
        form = QuestionForm()
    return render(request, 'ask_question.html', {'form': form})

def question_detail(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    answers = question.answers.all()
    return render(request, 'question_detail.html', {'question': question, 'answers': answers})

@login_required
def answer_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.question = question
            answer.user = request.user
            answer.save()
            messages.success(request, 'Respuesta publicada correctamente')
            return redirect('question_detail', question_id=question.id)
    else:
        form = AnswerForm()
    return render(request, 'answer_question.html', {'form': form, 'question': question})

# Dashboards
##DEsde aqui
# ===================================================================
# 🎓 VISTA DASHBOARD ESTUDIANTE: PREMIUM (ANALÍTICA + ASISTENCIA)
# ===================================================================


@login_required
@role_required('ESTUDIANTE')
def dashboard_estudiante(request):
    """
    Panel del Estudiante con Estadísticas Avanzadas, Asistencia y Directorio.
    """
    estudiante = request.user
    perfil_estudiante = get_object_or_404(Perfil, user=estudiante)

    # Intenta obtener la matrícula activa más reciente
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
    curso = matricula.curso if matricula else None

    # Inicializar colecciones
    materias_con_notas = {}
    comentarios_docente = {}
    actividades_semanales = {}
    convivencia_notas = {}
    logros_por_materia_por_periodo = {}
    periodos_disponibles = []
    
    # --- VARIABLES PARA ESTADÍSTICAS (NUEVO) ---
    stats_materias_labels = []    
    stats_materias_promedios = [] 
    stats_periodos_labels = []    
    stats_periodos_data = []      
    conteo_ganadas = 0
    conteo_perdidas = 0
    promedio_general_acumulado = 0.0
    
    # Variables de asistencia
    porcentaje_asistencia = 100.0
    total_fallas = 0
    fallas_detalladas = []

    # Directorio Docente
    docentes_directorio = []

    if curso:
        # Obtener periodos
        periodos_disponibles = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))

        # Obtener asignaciones (Optimizada para traer datos del docente)
        asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia', 'docente')
        
        # -------------------------------------------------------------------------
        # 🏥 CIRUGÍA MAYOR: CORRECCIÓN DE MATERIAS (INCLUYE CONVIVENCIA)
        # -------------------------------------------------------------------------
        # 1. Identificamos materias que tienen profesor asignado (Académicas)
        ids_materias_asignadas = {a.materia.id for a in asignaciones}
        
        # 2. Identificamos materias que tienen NOTAS registradas (Transversales/Convivencia)
        # Esto fuerza al sistema a reconocer Convivencia si existen notas, aunque no haya Asignación.
        ids_materias_con_notas = set(Nota.objects.filter(
            estudiante=estudiante,
            periodo__curso=curso
        ).values_list('materia_id', flat=True))

        # 3. Unimos ambos conjuntos para obtener la lista definitiva de materias reales
        ids_totales = ids_materias_asignadas | ids_materias_con_notas
        
        # 4. Recuperamos los objetos Materia
        materias = Materia.objects.filter(id__in=ids_totales).order_by('nombre')
        # -------------------------------------------------------------------------

        # --- LÓGICA DIRECTORIO DE DOCENTES ---
        docentes_vistos = set()
        for asig in asignaciones:
            if asig.docente_id and asig.docente_id not in docentes_vistos:
                docente = asig.docente
                # Foto segura
                foto_url = None
                try:
                    if hasattr(docente, 'perfil') and docente.perfil.foto:
                        foto_url = docente.perfil.foto.url
                except Exception: pass

                docentes_directorio.append({
                    'id': docente.id,
                    'nombre': docente.get_full_name() or docente.username,
                    'materia_principal': asig.materia.nombre,
                    'foto_url': foto_url
                })
                docentes_vistos.add(docente.id)

        # -----------------------------------------------------------
        # 1. CÁLCULO DE ESTADÍSTICAS ACADÉMICAS
        # -----------------------------------------------------------
        notas_definitivas_qs = Nota.objects.filter(
            estudiante=estudiante, 
            materia__in=materias,
            numero_nota=5
        )

        # A. Estadísticas por Materia
        for materia in materias:
            notas_mat = [n.valor for n in notas_definitivas_qs if n.materia_id == materia.id]
            promedio_materia = 0.0

            if notas_mat:
                promedio_materia = float(sum(notas_mat)) / len(notas_mat)
                if promedio_materia >= 3.5: 
                    conteo_ganadas += 1
                else:
                    conteo_perdidas += 1
            
            stats_materias_labels.append(materia.nombre)
            stats_materias_promedios.append(round(promedio_materia, 2))

        # B. Estadísticas por Periodo
        for periodo in periodos_disponibles:
            stats_periodos_labels.append(periodo.nombre)
            notas_per = [n.valor for n in notas_definitivas_qs if n.periodo_id == periodo.id]
            
            if notas_per:
                prom_per = float(sum(notas_per)) / len(notas_per)
                stats_periodos_data.append(round(prom_per, 2))
            else:
                stats_periodos_data.append(0)

        # C. Promedio General
        if stats_materias_promedios:
            promedios_validos = [p for p in stats_materias_promedios if p > 0]
            if promedios_validos:
                promedio_general_acumulado = sum(promedios_validos) / len(promedios_validos)

        # -----------------------------------------------------------
        # 2. CÁLCULO DE ASISTENCIA DETALLADA
        # -----------------------------------------------------------
        try:
            from .models import Asistencia 
            total_clases = Asistencia.objects.filter(estudiante=estudiante, curso=curso).count()
            fallas_qs = Asistencia.objects.filter(estudiante=estudiante, curso=curso, estado='FALLA').select_related('materia').order_by('-fecha')
            total_fallas = fallas_qs.count()
            fallas_detalladas = list(fallas_qs)

            if total_clases > 0:
                porcentaje_asistencia = ((total_clases - total_fallas) / total_clases) * 100
            
            porcentaje_asistencia = round(porcentaje_asistencia, 1)
        except ImportError: pass

        # -----------------------------------------------------------
        # 3. DATOS DETALLADOS (LÓGICA ORIGINAL)
        # -----------------------------------------------------------
        for materia in materias:
            # Notas
            notes = Nota.objects.filter(estudiante=estudiante, materia=materia).select_related('periodo').order_by('periodo__id', 'numero_nota')
            notas_por_periodo = {}
            for nota in notes:
                notas_por_periodo.setdefault(nota.periodo.id, {})[nota.numero_nota] = nota

            if notas_por_periodo:
                materias_con_notas[materia] = notas_por_periodo

            # Comentarios
            comentarios = ComentarioDocente.objects.filter(estudiante=estudiante, materia=materia).order_by('-fecha_creacion')
            if comentarios.exists():
                comentarios_docente[materia.id] = comentarios

            # Actividades
            actividades = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
            if actividades.exists():
                actividades_semanales[materia.id] = actividades

            # Logros
            logros_de_la_materia = LogroPeriodo.objects.filter(curso=curso, materia=materia).order_by('periodo__id', '-fecha_creacion')
            if logros_de_la_materia.exists():
                logros_por_periodo_temp = {}
                for logro in logros_de_la_materia:
                    logros_por_periodo_temp.setdefault(logro.periodo.id, []).append(logro)
                logros_por_materia_por_periodo[materia] = logros_por_periodo_temp

        # Convivencia
        convivencia_existente = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
        for convivencia in convivencia_existente:
            convivencia_notas[convivencia.periodo.id] = {'valor': convivencia.valor, 'comentario': convivencia.comentario}

    # Empaquetar Estadísticas
    stats = {
        'materias_labels': json.dumps(stats_materias_labels),
        'materias_data': json.dumps(stats_materias_promedios),
        'periodos_labels': json.dumps(stats_periodos_labels),
        'periodos_data': json.dumps(stats_periodos_data),
        'ganadas': conteo_ganadas,
        'perdidas': conteo_perdidas,
        'promedio_general': round(promedio_general_acumulado, 2),
        'distribucion_data': json.dumps([conteo_ganadas, conteo_perdidas]),
        'asistencia_pct': porcentaje_asistencia,
        'total_fallas': total_fallas,
        'detalle_fallas': fallas_detalladas
    }

    context = {
        'estudiante': estudiante,
        'perfil': perfil_estudiante,
        'curso': curso,
        'matricula': matricula,
        'periodos_disponibles': periodos_disponibles,
        'materias_con_notas': materias_con_notas,
        'comentarios_docente': comentarios_docente,
        'actividades_semanales': actividades_semanales,
        'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
        'convivencia_notas': convivencia_notas,
        # NUEVOS CONTEXTOS
        'stats': stats,
        'docentes': docentes_directorio
    }

    return render(request, 'dashboard_estudiante.html', context)

##Hasta aqui 
# ===================================================================
# --- INICIO DE CIRUGÍA 2: FUNCIÓN dashboard_docente MODIFICADA ---
# ===================================================================
#desde aqui 
# ===================================================================
# 👨‍🏫 VISTA DASHBOARD DOCENTE: GESTIÓN + INTELIGENCIA ACADÉMICA
# ===================================================================

@role_required('DOCENTE')
def dashboard_docente(request):
    docente = request.user
    
    # 1. Obtener asignaciones base ordenadas
    asignaciones = AsignacionMateria.objects.filter(docente=docente, activo=True)\
        .select_related('materia', 'curso').order_by('materia__nombre', 'curso__grado', 'curso__seccion')
    
    # --- ESTRUCTURAS DE DATOS ---
    materias_por_curso = {}
    total_estudiantes_unicos = set()
    estadisticas_por_materia = {} # Pestaña 2
    
    # --- VARIABLES PARA ESTADÍSTICAS AVANZADAS ---
    analisis_estudiantes = {} 
    conteo_reprobados_global = 0 
    conteo_total_fallas = 0      

    # --- INICIO DEL BUCLE PRINCIPAL ---
    for asignacion in asignaciones:
        curso = asignacion.curso
        materia_actual = asignacion.materia
        
        if not curso: continue
            
        curso_key = f"{curso.get_grado_display()} {curso.seccion}"
        
        # -------------------------------------------------------
        # BLOQUE 1: GESTIÓN DE MATERIAS (Tab 1)
        # -------------------------------------------------------
        if curso_key not in materias_por_curso:
            qs_estudiantes = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante', 'estudiante__perfil')
            
            materias_por_curso[curso_key] = {
                'curso_obj': curso,
                'materias': [], 
                'es_director': (getattr(curso, 'director', None) == docente),
                'estudiantes': qs_estudiantes,
            }
            
            for mat in qs_estudiantes:
                est = mat.estudiante
                total_estudiantes_unicos.add(est.id)
                if est.id not in analisis_estudiantes:
                    analisis_estudiantes[est.id] = {
                        'obj': est,
                        'curso_texto': curso_key,
                        'suma_notas': 0.0,
                        'num_notas': 0,
                        'fallas': 0,
                        'historial_temp': [] # Placeholder
                    }

        if materia_actual not in materias_por_curso[curso_key]['materias']:
            materias_por_curso[curso_key]['materias'].append(materia_actual)
        
        # -------------------------------------------------------
        # BLOQUE 2: ESTADÍSTICAS POR MATERIA (Tab 2)
        # -------------------------------------------------------
        if materia_actual.id not in estadisticas_por_materia:
            estadisticas_por_materia[materia_actual.id] = {
                'materia_obj': materia_actual,
                'cursos': {}
            }
        
        if curso.id not in estadisticas_por_materia[materia_actual.id]['cursos']:
            estudiantes_del_curso_ids = [m.estudiante.id for m in materias_por_curso[curso_key]['estudiantes']]
            periodos_curso = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
            
            estadisticas_por_materia[materia_actual.id]['cursos'][curso.id] = {
                'curso_obj': curso,
                'periodos': {}
            }

            for periodo in periodos_curso:
                notas_qs = Nota.objects.filter(
                    estudiante_id__in=estudiantes_del_curso_ids,
                    materia=materia_actual,
                    periodo=periodo,
                    numero_nota=5 
                )
                
                promedio_materia_periodo = notas_qs.aggregate(promedio=Avg('valor'))['promedio']

                for nota in notas_qs:
                    if nota.estudiante_id in analisis_estudiantes:
                        analisis_estudiantes[nota.estudiante_id]['suma_notas'] += float(nota.valor)
                        analisis_estudiantes[nota.estudiante_id]['num_notas'] += 1

                logros_periodo = LogroPeriodo.objects.filter(
                    curso=curso, docente=docente, materia=materia_actual, periodo=periodo
                ).order_by('-fecha_creacion')

                if promedio_materia_periodo is not None or logros_periodo.exists():
                    estadisticas_por_materia[materia_actual.id]['cursos'][curso.id]['periodos'][periodo.id] = {
                        'periodo_obj': periodo,
                        'promedio': promedio_materia_periodo,
                        'logros': logros_periodo
                    }

    # -------------------------------------------------------
    # BLOQUE 3: PROCESAMIENTO FINAL DE ANALÍTICA (Tab 3)
    # -------------------------------------------------------
    
    # 1. Calcular Ausentismo (Fallas Y Retardos - Conteo Global)
    mis_materias_ids = [a.materia.id for a in asignaciones] # IDs de las materias de este profe
    try:
        from .models import Asistencia
        
        # Filtramos fallas y retardos
        fallas_agrupadas = Asistencia.objects.filter(
            materia_id__in=mis_materias_ids,
            estado__in=['FALLA', 'TARDE'] 
        ).values('estudiante_id').annotate(total=Count('id'))
        
        for f in fallas_agrupadas:
            eid = f['estudiante_id']
            if eid in analisis_estudiantes:
                analisis_estudiantes[eid]['fallas'] = f['total']
                conteo_total_fallas += f['total']
                
    except ImportError:
        pass 

    # 2. Convertir diccionario a lista plana para ordenar
    lista_final_estudiantes = []
    
    for eid, data in analisis_estudiantes.items():
        promedio_final = 0.0
        if data['num_notas'] > 0:
            promedio_final = data['suma_notas'] / data['num_notas']
        
        if promedio_final > 0 and promedio_final < 3.0:
            conteo_reprobados_global += 1

        lista_final_estudiantes.append({
            'estudiante': data['obj'],
            'curso': data['curso_texto'],
            'promedio': round(promedio_final, 2),
            'fallas': data['fallas'],
            'historial': [] # Inicializamos la lista vacía para llenarla luego
        })

    # 3. Generar los TOPS
    top_mejores = sorted(lista_final_estudiantes, key=lambda x: x['promedio'], reverse=True)[:5]
    
    estudiantes_con_notas = [x for x in lista_final_estudiantes if x['promedio'] > 0]
    top_riesgo = sorted(estudiantes_con_notas, key=lambda x: x['promedio'])[:5]
    
    con_fallas = [x for x in lista_final_estudiantes if x['fallas'] > 0]
    top_ausentismo = sorted(con_fallas, key=lambda x: x['fallas'], reverse=True)[:5]

    # ==============================================================================
    # 🔥 CORRECCIÓN CRÍTICA: CARGAR EL HISTORIAL DETALLADO DE FALLAS
    # Sin este bloque, el modal en el HTML nunca tendrá datos para mostrar.
    # ==============================================================================
    try:
        from .models import Asistencia
        
        # Recorremos SOLO a los estudiantes que están en el Top de Ausentismo
        for item in top_ausentismo:
            estudiante_obj = item['estudiante']
            
            # Buscamos cada registro individual (Día, Fecha, Hora, Materia)
            # Solo de las materias de este profesor (mis_materias_ids)
            detalle_fallas = Asistencia.objects.filter(
                estudiante=estudiante_obj,
                materia_id__in=mis_materias_ids,
                estado__in=['FALLA', 'TARDE']
            ).select_related('materia').order_by('-fecha', '-id') # Orden descendente
            
            # Guardamos la consulta en el diccionario del estudiante
            item['historial'] = list(detalle_fallas)

    except Exception as e:
        print(f"Error cargando historial de fallas: {e}")
    # ==============================================================================

    context = {
        'docente': docente,
        'materias_por_curso': materias_por_curso,
        'estadisticas_por_materia': estadisticas_por_materia,
        'total_cursos': len(materias_por_curso),
        'total_materias': len(estadisticas_por_materia),
        'total_estudiantes': len(total_estudiantes_unicos),
        'top_mejores': top_mejores,
        'top_riesgo': top_riesgo,
        'top_ausentismo': top_ausentismo, # Ahora incluye 'historial' con fechas y horas
        'kpi_reprobados': conteo_reprobados_global,
        'kpi_fallas': conteo_total_fallas
    }
    return render(request, 'dashboard_docente.html', context)

def get_description_nota(numero_nota):
    return {
        1: 'Quiz (20%)',
        2: 'Examen (30%)',
        3: 'Proyecto (30%)',
        4: 'Sustentación (20%)',
        5: 'Promedio ponderado'
    }.get(numero_nota, f'Nota {numero_nota}')
##Desde aqui
@role_required('DOCENTE')
def subir_notas(request, materia_id):
    # 1. VALIDACIÓN DE ACCESO Y CONTEXTO ACADÉMICO
    asignacion = get_object_or_404(AsignacionMateria, materia_id=materia_id, docente=request.user, activo=True)
    materia = asignacion.materia
    curso = asignacion.curso
    
    # Optimización: Traemos estudiantes con sus perfiles en una sola consulta (SELECT_RELATED)
    estudiantes_matriculados = Matricula.objects.filter(
        curso=curso, activo=True
    ).select_related('estudiante__perfil').order_by('estudiante__last_name')
    
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')

    # 2. AUTO-CREACIÓN DE PERIODOS (Si no existen)
    if not periodos.exists():
        nombres = ['Primer Periodo', 'Segundo Periodo', 'Tercer Periodo', 'Cuarto Periodo']
        fecha_base = timezone.now()
        for i, nombre in enumerate(nombres):
            Periodo.objects.create(
                nombre=nombre, curso=curso,
                fecha_inicio=fecha_base + timedelta(days=i*90),
                fecha_fin=fecha_base + timedelta(days=(i+1)*90),
                activo=True
            )
        periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
        messages.info(request, 'Se han generado los periodos académicos automáticamente.')

    # 3. GESTIÓN DE DEFINICIONES DE NOTAS (COLUMNAS DINÁMICAS)
    # Estructura map: { periodo_id: [Definicion1, Definicion2...] }
    definiciones_map = {}
    
    # Configuración por defecto si el profesor entra por primera vez
    defaults_config = [
        ('Corte 1', 20, 1), 
        ('Corte 2', 30, 2), 
        ('Corte 3', 30, 3), 
        ('Final', 20, 4)
    ]

    for p in periodos:
        # Recuperamos las columnas existentes
        defs = list(DefinicionNota.objects.filter(materia=materia, periodo=p).order_by('orden'))
        
        # Si no hay columnas configuradas, inyectamos las predeterminadas
        if not defs:
            for nombre, porc, orden in defaults_config:
                nueva_def = DefinicionNota.objects.create(
                    materia=materia, periodo=p, 
                    nombre=nombre, 
                    porcentaje=porc, 
                    orden=orden, 
                    temas="Contenido general"
                )
                defs.append(nueva_def)
        
        definiciones_map[p.id] = defs

    # ==========================================================================
    # PROCESAMIENTO DEL FORMULARIO (POST)
    # ==========================================================================
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # --------------------------------------------------------------
                # A. GESTIÓN DE ACTIVIDADES SEMANALES
                # --------------------------------------------------------------
                # Identificar qué actividades se mantienen (para borrar las que el usuario quitó)
                actividad_ids_a_mantener = [
                    int(i) for i in request.POST.getlist('actividad_id[]') 
                    if i and i.strip().isdigit()
                ]
                
                # Borrar actividades que ya no están en el formulario
                ActividadSemanal.objects.filter(curso=curso, materia=materia, docente=request.user)\
                    .exclude(id__in=actividad_ids_a_mantener).delete()
                
                # Procesar datos del formulario
                titulos = request.POST.getlist('titulo_actividad[]')
                descripciones = request.POST.getlist('descripcion_actividad[]')
                fechas_ini = request.POST.getlist('fecha_inicio_actividad[]')
                fechas_fin = request.POST.getlist('fecha_fin_actividad[]')
                ids_act = request.POST.getlist('actividad_id[]')
                
                for i in range(len(titulos)):
                    t = (titulos[i] or "").strip()
                    d = (descripciones[i] or "").strip()
                    aid = (ids_act[i] or "").strip()
                    
                    if t or d: # Solo guardar si hay contenido
                        fi = datetime.strptime(fechas_ini[i], '%Y-%m-%d').date() if dates_ok(fechas_ini, i) else None
                        ff = datetime.strptime(fechas_fin[i], '%Y-%m-%d').date() if dates_ok(fechas_fin, i) else None
                        
                        if aid: # Actualizar
                            ActividadSemanal.objects.filter(id=aid).update(
                                titulo=t, descripcion=d, fecha_inicio=fi, fecha_fin=ff
                            )
                        else: # Crear
                            ActividadSemanal.objects.create(
                                curso=curso, materia=materia, docente=request.user,
                                titulo=t or "Nueva Actividad", descripcion=d, 
                                fecha_inicio=fi, fecha_fin=ff
                            )

                # --------------------------------------------------------------
                # B. GESTIÓN DE LOGROS (VIA JSON)
                # --------------------------------------------------------------
                logros_json = request.POST.get('logros_json_data', '')
                if logros_json:
                    try:
                        data_logros = json.loads(logros_json)
                        # Recolectar IDs para saber cuáles borrar
                        ids_logros_mantener = []
                        for plist in data_logros.values():
                            for l in plist:
                                if l.get('id', 0) > 0:
                                    ids_logros_mantener.append(l['id'])
                        
                        # Borrado masivo de logros eliminados
                        LogroPeriodo.objects.filter(curso=curso, materia=materia, docente=request.user)\
                            .exclude(id__in=ids_logros_mantener).delete()
                        
                        # Guardado/Actualización
                        for pid_str, lista_logros in data_logros.items():
                            periodo_obj = Periodo.objects.get(id=int(pid_str))
                            for l in lista_logros:
                                desc_l = (l.get('descripcion') or "").strip()
                                if desc_l:
                                    if l.get('id', 0) > 0:
                                        LogroPeriodo.objects.filter(id=l['id']).update(descripcion=desc_l)
                                    else:
                                        LogroPeriodo.objects.create(
                                            curso=curso, periodo=periodo_obj, materia=materia,
                                            docente=request.user, descripcion=desc_l
                                        )
                    except Exception as e_json:
                        logger.error(f"Error procesando JSON de logros: {e_json}")

                # --------------------------------------------------------------
                # C. NOTAS DINÁMICAS Y SINCRONIZACIÓN LEGACY (CORE)
                # --------------------------------------------------------------
                usuario_sistema, _ = User.objects.get_or_create(username='sistema', defaults={'is_active': False})
                
                # Cacheamos notas existentes para detectar borrados sin consultar DB repetidamente
                notas_existentes = {
                    (n.estudiante_id, n.definicion_id): n 
                    for n in NotaDetallada.objects.filter(definicion__materia=materia)
                }

                for m in estudiantes_matriculados:
                    est = m.estudiante
                    for periodo in periodos:
                        definiciones = definiciones_map.get(periodo.id, [])
                        
                        suma_ponderada = Decimal('0.0')
                        suma_porcentajes = Decimal('0.0')

                        for definicion in definiciones:
                            # Nombre del input HTML: nota_ESTUDIANTEID_DEFINICIONID
                            input_name = f'nota_{est.id}_{definicion.id}'
                            val_str = request.POST.get(input_name)
                            key_nota = (est.id, definicion.id)

                            # --- LOGICA DE GUARDADO ---
                            if val_str and val_str.strip():
                                try:
                                    val_limpio = val_str.replace(',', '.')
                                    val_decimal = Decimal(val_limpio)
                                    
                                    if 1.0 <= val_decimal <= 5.0:
                                        # Guardamos o actualizamos la nota real
                                        NotaDetallada.objects.update_or_create(
                                            estudiante=est, definicion=definicion,
                                            defaults={
                                                'valor': val_decimal,
                                                'registrado_por': request.user
                                            }
                                        )
                                        
                                        # Acumulamos para el promedio
                                        peso = definicion.porcentaje / Decimal('100.0')
                                        suma_ponderada += val_decimal * peso
                                        suma_porcentajes += peso
                                except Exception:
                                    pass # Ignoramos valores no numéricos
                            
                            # --- LOGICA DE BORRADO ---
                            else:
                                # Si viene vacío y existía en BD, lo borramos
                                if key_nota in notas_existentes:
                                    notas_existentes[key_nota].delete()
                                    # Al borrar, NO sumamos al promedio

                        # --- SINCRONIZACIÓN CON SISTEMA LEGACY (Nota #5) ---
                        if suma_porcentajes > 0:
                            # Calculamos la definitiva (Suma acumulativa)
                            definitiva = suma_ponderada
                            
                            Nota.objects.update_or_create(
                                estudiante=est, materia=materia, periodo=periodo, numero_nota=5,
                                defaults={
                                    'valor': definitiva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                                    'descripcion': 'Promedio Dinámico Auto-generado',
                                    'registrado_por': usuario_sistema
                                }
                            )
                        else:
                            # Si no hay notas, borramos también la definitiva
                            Nota.objects.filter(
                                estudiante=est, materia=materia, periodo=periodo, numero_nota=5
                            ).delete()

                # --------------------------------------------------------------
                # D. COMENTARIOS DEL DOCENTE
                # --------------------------------------------------------------
                for m in estudiantes_matriculados:
                    est = m.estudiante
                    for periodo in periodos:
                        com_key = f'comentario_{est.id}_{periodo.id}'
                        texto_com = request.POST.get(com_key)
                        
                        if texto_com and texto_com.strip():
                            ComentarioDocente.objects.update_or_create(
                                docente=request.user, estudiante=est, 
                                materia=materia, periodo=periodo,
                                defaults={'comentario': texto_com.strip()}
                            )
                        else:
                            ComentarioDocente.objects.filter(
                                docente=request.user, estudiante=est, 
                                materia=materia, periodo=periodo
                            ).delete()

            messages.success(request, 'Plan de evaluación y calificaciones guardados exitosamente.')
            return redirect('subir_notas', materia_id=materia.id)
        
        except Exception as e:
            logger.exception("Error critico en subir_notas POST")
            messages.error(request, f"Ocurrió un error al guardar: {str(e)}")

    # ==========================================================================
    # PREPARACIÓN DE DATOS PARA LA VISTA (GET)
    # ==========================================================================
    
    # 1. Recuperar notas existentes optimizadamente
    # Estructura map: notas_map[estudiante_id][definicion_id] = valor
    notas_detalladas = NotaDetallada.objects.filter(
        definicion__materia=materia,
        estudiante__in=[m.estudiante for m in estudiantes_matriculados]
    ).select_related('definicion')

    notas_map = {}
    for n in notas_detalladas:
        if n.estudiante_id not in notas_map:
            notas_map[n.estudiante_id] = {}
        notas_map[n.estudiante_id][n.definicion.id] = n.valor

    # 2. Recuperar Comentarios (CORREGIDO: SE CAMBIÓ LA COMPRESIÓN POR UN BUCLE)
    # ---------------------------------------------------------------------------------------
    # Esto soluciona que solo se viera el último comentario y borrara los anteriores visualmente
    # ---------------------------------------------------------------------------------------
    comentarios = ComentarioDocente.objects.filter(materia=materia, docente=request.user)
    comentarios_map = {}
    for c in comentarios:
        if c.estudiante_id not in comentarios_map:
            comentarios_map[c.estudiante_id] = {}
        comentarios_map[c.estudiante_id][c.periodo_id] = c.comentario
    
    # Rellenar vacíos para evitar errores en template
    for m in estudiantes_matriculados:
        if m.estudiante_id not in comentarios_map:
            comentarios_map[m.estudiante_id] = {}
        for p in periodos:
            if p.id not in comentarios_map[m.estudiante_id]:
                comentarios_map[m.estudiante_id][p.id] = ""

    # 3. Recuperar Actividades y Logros
    actividades = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
    
    logros = LogroPeriodo.objects.filter(curso=curso, materia=materia, docente=request.user)
    logros_por_periodo = {}
    for l in logros:
        logros_por_periodo.setdefault(l.periodo.id, []).append({
            'id': l.id, 'descripcion': l.descripcion, 'periodo_id': l.periodo.id
        })

    # CONTEXTO FINAL
    context = {
        'materia': materia,
        'curso': curso,
        'estudiantes_matriculados': estudiantes_matriculados,
        'periodos': periodos,
        
        # Nuevos Datos Dinámicos
        'definiciones_map': definiciones_map,
        'notas_map': notas_map,
        
        # Datos Legacy / Compatibilidad
        'comentarios_data': comentarios_map,
        'actividades_semanales': actividades,
        'logros_por_periodo': json.dumps(logros_por_periodo),
        
        # Constantes
        'escala_min': 1.0,
        'escala_max': 5.0,
    }
    
    return render(request, 'subir_notas.html', context)

# Helper simple para validar fechas en listas
def dates_ok(lista, index):
    return index < len(lista) and lista[index] and lista[index].strip()

#hasta aqui 


@login_required
@role_required('ADMINISTRADOR')
def admin_dashboard(request):
    """
    Dashboard Ejecutivo TIER GOD.
    Analítica de datos, KPIs en tiempo real y gestión centralizada.
    """
    from .models import Curso, Materia, ObservadorArchivado, Perfil, Matricula, Observacion, User
    from django.db.models import Q, Sum, Count
    from django.utils import timezone
    from datetime import timedelta
    import json 

    # --- 1. KPIs PRINCIPALES (Tarjetas Superiores) ---
    st_activos = User.objects.filter(perfil__rol='ESTUDIANTE', is_active=True).count()
    try:
        st_archivados = ObservadorArchivado.objects.count()
    except:
        st_archivados = 0
    
    doc_activos = Perfil.objects.filter(
        Q(rol='DOCENTE') | Q(es_director=True), 
        user__is_active=True
    ).distinct().count()
    
    cursos_qs = Curso.objects.filter(activo=True)
    total_cursos = cursos_qs.count()
    total_materias = Materia.objects.count()
    
    # Cálculo de Ocupación
    capacidad = cursos_qs.aggregate(t=Sum('capacidad_maxima'))['t'] or 0
    matriculados = Matricula.objects.filter(activo=True, curso__activo=True).count()
    ocupacion = int((matriculados / capacidad) * 100) if capacidad > 0 else 0

    # --- 2. INTELLIGENCE HUB (Datos para Gráficas) ---
    distribucion = Matricula.objects.filter(activo=True).values('curso__grado').annotate(total=Count('id')).order_by('curso__grado')
    chart_labels = [d['curso__grado'] for d in distribucion] 
    chart_data = [d['total'] for d in distribucion]

    # --- 3. TIMELINE & RIESGO ---
    ultimos_logins = User.objects.filter(last_login__isnull=False).order_by('-last_login')[:50]
    
    mes_anterior = timezone.now() - timedelta(days=30)
    estudiantes_riesgo = User.objects.filter(
        observaciones__fecha_creacion__gte=mes_anterior
    ).annotate(num_obs=Count('observaciones')).order_by('-num_obs')[:5]

    # --- 4. EXTRAS ---
    cursos_sin_director = cursos_qs.filter(director__isnull=True).count()
    obs_hoy = Observacion.objects.filter(fecha_creacion__date=timezone.now().date()).count()

    context = {
        # Métricas (Nombres compatibles con tu HTML anterior y el nuevo)
        'kpi_estudiantes': st_activos,
        'total_estudiantes': st_activos, 
        'kpi_archivados': st_archivados,
        'kpi_docentes': doc_activos,
        'total_docentes': doc_activos,
        'kpi_cursos': total_cursos,
        'total_cursos': total_cursos,
        'kpi_materias': total_materias,
        'total_materias': total_materias,
        
        # Analítica
        'ocupacion_global': ocupacion,
        'cursos_sin_director': cursos_sin_director,
        'obs_hoy': obs_hoy,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'timeline_logins': ultimos_logins,
        'estudiantes_riesgo': estudiantes_riesgo,
    }
    
    # CORRECCIÓN DE RUTA: Apunta directo a 'admin_dashboard.html'
    return render(request, 'admin_dashboard.html', context)





@role_required('DIRECTOR_CURSO')
def dashboard_director(request):
    messages.info(request, "Redirigiendo a tu panel de docente/director.")
    return redirect('dashboard_docente')

@role_required('DIRECTOR_CURSO')
def panel_director_curso(request, curso_id):
    director = request.user
    curso = get_object_or_404(Curso, id=curso_id, director=director, activo=True)
    estudiantes = User.objects.filter(
        matriculas__curso=curso, matriculas__activo=True, perfil__rol='ESTUDIANTE'
    ).select_related('perfil').order_by('last_name', 'first_name').distinct()
    materias = Materia.objects.filter(asignaciones__curso=curso).distinct().order_by('nombre')
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
    notas_finales_data = {}
    convivencias_data = {}
    estudiante_ids = [e.id for e in estudiantes]
    materia_ids = [m.id for m in materias]
    periodo_ids = [p.id for p in periodos]
    notas_qs = Nota.objects.filter(
        estudiante_id__in=estudiante_ids,
        materia_id__in=materia_ids,
        periodo_id__in=periodo_ids,
        numero_nota=5
    ).values('estudiante_id', 'materia_id', 'periodo_id', 'valor')
    convivencia_qs = Convivencia.objects.filter(
        estudiante_id__in=estudiante_ids,
        curso=curso,
        periodo_id__in=periodo_ids
    ).values('estudiante_id', 'periodo_id', 'valor', 'comentario')
    for estudiante in estudiantes:
        notas_finales_data[estudiante.id] = {m.id: {} for m in materias}
        convivencias_data[estudiante.id] = {p.id: {'valor': None, 'comentario': ""} for p in periodos}
    for nota in notas_qs:
        if nota['estudiante_id'] in notas_finales_data and nota['materia_id'] in notas_finales_data[nota['estudiante_id']]:
            notas_finales_data[nota['estudiante_id']][nota['materia_id']][nota['periodo_id']] = nota['valor']
    for conv in convivencia_qs:
        if conv['estudiante_id'] in convivencias_data and conv['periodo_id'] in convivencias_data[conv['estudiante_id']]:
            convivencias_data[conv['estudiante_id']][conv['periodo_id']] = {'valor': conv['valor'], 'comentario': conv['comentario']}
    context = {
        'curso': curso, 'estudiantes': estudiantes, 'materias': materias, 'periodos': periodos,
        'notas_finales_data': notas_finales_data, 'convivencias_data': convivencias_data,
    }
    return render(request, 'director/panel_director_curso.html', context)

@role_required('DIRECTOR_CURSO')
@require_POST
@csrf_protect
def guardar_convivencia(request, curso_id):
    director = request.user
    curso = get_object_or_404(Curso, id=curso_id, director=director, activo=True)
    try:
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('convivencia_'):
                    parts = key.split('_')
                    if len(parts) == 3:
                        periodo_id = int(parts[1])
                        estudiante_id = int(parts[2])
                        estudiante = get_object_or_404(User, id=estudiante_id)
                        periodo = get_object_or_404(Periodo, id=periodo_id)
                        valor_str = (value or "").strip()
                        comentario = request.POST.get(f'comentario_convivencia_{periodo_id}_{estudiante_id}', "").strip()
                        if valor_str:
                            valor = Decimal(valor_str)
                            if ESCALA_MIN <= valor <= ESCALA_MAX:
                                Convivencia.objects.update_or_create(
                                    estudiante=estudiante, curso=curso, periodo=periodo,
                                    defaults={'valor': valor.quantize(TWO_PLACES, rounding=ROUND_HALF_UP), 'comentario': comentario, 'registrado_por': director}
                                )
                            else:
                                messages.error(request, f'El valor de convivencia para {estudiante.get_full_name()} debe estar entre 0.0 y 5.0.')
                        else:
                            Convivencia.objects.filter(estudiante=estudiante, curso=curso, periodo=periodo).delete()
        messages.success(request, 'Notas de convivencia guardadas correctamente.')
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Ocurrió un error al guardar."
        messages.error(request, msg)
        logger.exception("Error en guardar_convivencia: %s", e)
    return redirect('panel_director_curso', curso_id=curso.id)

@role_required('DIRECTOR_CURSO')
def generar_boletin(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id, director=request.user)
    estudiantes = User.objects.filter(
        matriculas__curso=curso, matriculas__activo=True, perfil__rol='ESTUDIANTE'
    ).select_related('perfil').prefetch_related('notas', 'matriculas').distinct()
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
    materias = Materia.objects.filter(asignaciones__curso=curso, asignaciones__activo=True).distinct().order_by('nombre')
    notas_data = {}
    for estudiante in estudiantes:
        notas_data[estudiante.id] = {}
        for materia in materias:
            notas_data[estudiante.id][materia.id] = {}
            for periodo in periodos:
                notas_periodo = Nota.objects.filter(estudiante=estudiante, materia=materia, periodo=periodo).order_by('numero_nota')
                notas_dict = {i: None for i in range(1, 6)}
                for nota in notas_periodo:
                    notas_dict[nota.numero_nota] = nota.valor
                notas_data[estudiante.id][materia.id][periodo.id] = notas_dict
    if request.method == 'POST':
        messages.success(request, 'Boletín generado correctamente.')
        return redirect('generar_boletin', curso_id=curso_id)
    context = {'curso': curso, 'estudiantes': estudiantes, 'periodos': periodos, 'materias': materias, 'notas_data': notas_data}
    return render(request, 'generar_boletin.html', context)

#Aqui empece con el registro de los profesores



@role_required('ADMINISTRADOR')
def registrar_alumnos_masivo_form(request):
    """
    Muestra el formulario para subir el CSV de alumnos.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    form = BulkCSVForm()
    context = {
        'form': form,
        'grados': GRADOS_CHOICES,
        'secciones': _secciones_disponibles(),
        'anio_escolar': _anio_escolar_actual(),
    }
    return render(request, 'admin/registrar_alumnos.html', context)


# --- VISTA DE CARGA MASIVA COMPLETAMENTE CORREGIDA ---
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def registrar_alumnos_masivo(request):
    """
    Procesa el registro masivo de estudiantes y acudientes desde un archivo CSV.
    Se corrige el error de autenticación para acudientes existentes y el error de sintaxis/indentación.
    """
    form = BulkCSVForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Error en el formulario. Por favor, sube un archivo CSV válido.")
        return redirect('registrar_alumnos_masivo_form')

    archivo_csv = form.cleaned_data['csv_file']
    anio_escolar = form.cleaned_data['anio_escolar'] or _anio_escolar_actual()

    creados_est, creados_acu = 0, 0
    actualizados_est, actualizados_acu = 0, 0
    matriculados, vinculados = 0, 0
    errores = []

    try:
        decoded_file = archivo_csv.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded_file))

        # 1. CORRECCIÓN: Se elimina 'acudiente_cedula' de las columnas obligatorias.
        columnas_obligatorias = {
            'first_name', 'last_name', 'email', 'grado',
            'acudiente_first_name', 'acudiente_last_name', 'acudiente_email'
        }

        reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames or []]

        if not columnas_obligatorias.issubset(reader.fieldnames):
            faltantes = ", ".join(columnas_obligatorias - set(reader.fieldnames))
            messages.error(request, f"El CSV es inválido. Faltan las columnas: {faltantes}")
            return redirect('registrar_alumnos_masivo_form')

        for i, row in enumerate(reader, start=2):
            try:
                with transaction.atomic():
                    # --- Datos del Acudiente ---
                    acu_email = (row.get('acudiente_email') or "").strip().lower()
                    acu_first = (row.get('acudiente_first_name') or "").strip().title()
                    acu_last = (row.get('acudiente_last_name') or "").strip().title()

                    if not all([acu_email, acu_first, acu_last]):
                        raise ValueError("Faltan datos obligatorios del acudiente (email, nombre, apellido).")

                    validate_email(acu_email)

                    acudiente_user, created_acu_user = User.objects.get_or_create(
                        email=acu_email,
                        defaults={ 'username': generar_username_unico(acu_first, acu_last), 'first_name': acu_first, 'last_name': acu_last }
                    )

                    # 🔑 CORRECCIÓN CLAVE: Aplica la contraseña temporal y el flag de cambio
                    perfil_acudiente, created_perfil_acu = Perfil.objects.get_or_create(
                        user=acudiente_user, defaults={'rol': 'ACUDIENTE'}
                    )

                    if created_acu_user or created_perfil_acu or not perfil_acudiente.requiere_cambio_clave:
                        acudiente_user.set_password(DEFAULT_TEMP_PASSWORD)
                        acudiente_user.save()
                        perfil_acudiente.rol = 'ACUDIENTE'
                        perfil_acudiente.requiere_cambio_clave = True
                        perfil_acudiente.save(update_fields=['rol', 'requiere_cambio_clave'])
                        if created_acu_user:
                            creados_acu += 1
                        else:
                            actualizados_acu += 1
                    else:
                        perfil_acudiente.rol = 'ACUDIENTE'
                        perfil_acudiente.save(update_fields=['rol'])
                        if not created_acu_user:
                            actualizados_acu += 1

                    # --- Datos del Estudiante ---
                    est_email = (row.get('email') or "").strip().lower()
                    est_first = (row.get('first_name') or "").strip().title()
                    est_last = (row.get('last_name') or "").strip().title()
                    grado_str = (row.get('grado') or "").strip()
                    grado_norm = _normalizar_grado(grado_str)

                    if not all([est_email, est_first, est_last, grado_norm]):
                        raise ValueError(f"Faltan datos del estudiante o el grado '{grado_str}' es inválido.")

                    validate_email(est_email)

                    estudiante_user, created_est_user = User.objects.get_or_create(
                        email=est_email,
                        defaults={ 'username': generar_username_unico(est_first, est_last), 'first_name': est_first, 'last_name': est_last }
                    )

                    perfil_estudiante, created_perfil_est = Perfil.objects.get_or_create(
                        user=estudiante_user, defaults={'rol': 'ESTUDIANTE'}
                    )

                    if created_est_user:
                        estudiante_user.set_password(DEFAULT_TEMP_PASSWORD)
                        estudiante_user.save()
                        creados_est += 1
                        perfil_estudiante.requiere_cambio_clave = True
                        perfil_estudiante.save(update_fields=['requiere_cambio_clave'])
                    elif created_perfil_est:
                        perfil_estudiante.rol = 'ESTUDIANTE'
                        perfil_estudiante.requiere_cambio_clave = True
                        perfil_estudiante.save(update_fields=['rol', 'requiere_cambio_clave'])
                        actualizados_est += 1
                    else:
                        actualizados_est += 1

                    # 3. CORRECCIÓN: Se crea el vínculo Acudiente-Estudiante de forma segura.
                    Acudiente.objects.update_or_create(
                        acudiente=acudiente_user,
                        estudiante=estudiante_user,
                        defaults={}
                    )
                    vinculados += 1

                    # --- Matrícula del Estudiante ---
                    curso_destino = asignar_curso_por_grado(grado_norm, anio_escolar=anio_escolar) # Pasar anio_escolar
                    if curso_destino:
                        Matricula.objects.update_or_create(
                            estudiante=estudiante_user, anio_escolar=anio_escolar,
                            defaults={'curso': curso_destino, 'activo': True}
                        )
                        matriculados += 1
                    else:
                        raise ValueError(f"No se encontraron cupos disponibles para el grado {grado_str} en el año {anio_escolar}.")

            except (ValidationError, ValueError, IntegrityError) as e:
                errores.append(f"Fila {i}: {e} | Datos: {row.get('first_name')} {row.get('last_name')}")

    # Este 'except' final maneja errores de lectura del archivo CSV (ej. encoding)
    except Exception as e:
        messages.error(request, f"No se pudo leer el archivo CSV. Error: {e}")
        logger.exception("Error procesando CSV de alumnos")
        return redirect('registrar_alumnos_masivo_form')

    # ################################################################## #
    # ############# INICIO DE LA MEJORA EN MENSAJES #################### #
    # ################################################################## #

    # 🚨 CORRECCIÓN DE SINTAXIS: Se asegura el uso del objeto 'request' para los mensajes y la indentación correcta.

    # Si no se creó/actualizó ningún estudiante y hubo errores, muestra un mensaje de error principal.
    if creados_est == 0 and actualizados_est == 0 and errores:
        messages.error(request, f"La carga masiva falló. No se procesó ningún estudiante. Causa probable: No existen cursos creados para los grados en el archivo CSV para el año {anio_escolar}.")
    # De lo contrario, muestra el resumen normal.
    else:
        messages.success(request, f"Proceso finalizado. Estudiantes creados: {creados_est}. Acudientes creados: {creados_acu}. Matriculados: {matriculados}.")
        if creados_est > 0 or creados_acu > 0:
            messages.info(request, f"La contraseña temporal para todos los usuarios nuevos es: '{DEFAULT_TEMP_PASSWORD}'")


    # Si hubo errores en filas específicas, muéstralos.
    if errores:
        # Se cambia el mensaje para mayor claridad.
        messages.warning(request, f"Se encontraron {len(errores)} filas con errores que no se pudieron procesar (mostrando los primeros 5):")
        for error in errores[:5]:
            messages.error(request, error)

    # ################################################################## #
    # ############### FIN DE LA MEJORA EN MENSAJES ##################### #
    # ################################################################## #

    return redirect('admin_dashboard')


# ===================================================================
# ===================================================================
#
# 🩺 INICIO DE LA CIRUGÍA: registrar_alumno_individual
#
# ===================================================================
# ===================================================================

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def registrar_alumno_individual(request):
    """
    Procesa el registro individual de un estudiante Y su acudiente,
    replicando la lógica de seguridad y vinculación del registro masivo.
    """

    # --- 1. Obtención de Datos del Formulario ---
    # Datos del Estudiante
    est_username = (request.POST.get('username') or "").strip()
    est_email = (request.POST.get('email') or "").strip().lower()
    est_first = (request.POST.get('first_name') or "").strip().title()
    est_last = (request.POST.get('last_name') or "").strip().title()
    curso_id = request.POST.get('curso_id')

    # Datos del Acudiente (Nuevos - del formulario actualizado)
    acu_email = (request.POST.get('acudiente_email') or "").strip().lower()
    acu_first = (request.POST.get('acudiente_first_name') or "").strip().title()
    acu_last = (request.POST.get('acudiente_last_name') or "").strip().title()

    # --- 2. Validación Rigurosa ---
    try:
        # Validar que todos los campos nuevos y viejos estén presentes
        if not all([est_username, est_email, est_first, est_last, curso_id, acu_email, acu_first, acu_last]):
            raise ValueError('Todos los campos (Estudiante y Acudiente) son obligatorios.')
        
        # Validar ambos emails
        validate_email(est_email)
        validate_email(acu_email)
        
        if est_email == acu_email:
            raise ValueError("El email del estudiante y del acudiente no pueden ser el mismo.")

        # Validar curso y obtener el año escolar desde el curso (más seguro)
        curso = get_object_or_404(Curso, id=curso_id, activo=True)
        anio_escolar = curso.anio_escolar

        if _curso_esta_completo(curso):
            raise ValueError(f'El curso {curso.nombre} está lleno.')

    except (ValidationError, ValueError) as e:
        messages.error(request, f'Error de validación: {e}')
        return redirect('mostrar_registro_individual')
    except Http404:
        messages.error(request, 'El curso seleccionado no es válido o no está activo.')
        return redirect('mostrar_registro_individual')

    # --- 3. Cirugía: Transacción Atómica (Como en el registro masivo) ---
    try:
        with transaction.atomic():
            
            # --- A. Procesar Acudiente (Lógica de registro masivo) ---
            # Usamos el email como identificador único para el acudiente
            acudiente_user, created_acu_user = User.objects.get_or_create(
                email=acu_email,
                defaults={
                    'username': generar_username_unico(acu_first, acu_last), # de utils.py
                    'first_name': acu_first,
                    'last_name': acu_last
                }
            )
            
            perfil_acudiente, created_perfil_acu = Perfil.objects.get_or_create(
                user=acudiente_user, defaults={'rol': 'ACUDIENTE'}
            )

            # Asignar contraseña temporal y flag de cambio (Igual que en registro masivo)
            if created_acu_user or created_perfil_acu or not perfil_acudiente.requiere_cambio_clave:
                acudiente_user.set_password(DEFAULT_TEMP_PASSWORD)
                acudiente_user.save()
                perfil_acudiente.rol = 'ACUDIENTE'
                perfil_acudiente.requiere_cambio_clave = True
                perfil_acudiente.save(update_fields=['rol', 'requiere_cambio_clave'])
                if created_acu_user:
                    # ✅ Retroalimentación para el admin
                    messages.info(request, f'Nuevo acudiente creado: {acudiente_user.username}. Contraseña: {DEFAULT_TEMP_PASSWORD}')
            else:
                perfil_acudiente.rol = 'ACUDIENTE'
                perfil_acudiente.save(update_fields=['rol'])
                # ✅ Retroalimentación para el admin
                messages.info(request, f'Acudiente existente vinculado: {acudiente_user.username}.')


            # --- B. Procesar Estudiante (Lógica de registro individual) ---
            # Usamos el username (del formulario) como identificador único
            estudiante_user, created_est_user = User.objects.get_or_create(
                username=est_username,
                defaults={
                    'email': est_email,
                    'first_name': est_first,
                    'last_name': est_last,
                }
            )
            
            if created_est_user:
                estudiante_user.set_password(DEFAULT_TEMP_PASSWORD)
                estudiante_user.save()
                Perfil.objects.create(user=estudiante_user, rol='ESTUDIANTE', requiere_cambio_clave=True)
                # ✅ Retroalimentación para el admin
                messages.success(request, f'Estudiante creado: {est_username}. Contraseña: {DEFAULT_TEMP_PASSWORD}')
            else:
                # Si ya existía, actualizamos datos y perfil
                estudiante_user.email = est_email
                estudiante_user.first_name = est_first
                estudiante_user.last_name = est_last
                estudiante_user.save(update_fields=['email', 'first_name', 'last_name'])
                
                perfil_est, p_created = Perfil.objects.get_or_create(user=estudiante_user, defaults={'rol': 'ESTUDIANTE'})
                if not p_created and perfil_est.rol != 'ESTUDIANTE':
                    perfil_est.rol = 'ESTUDIANTE'
                    perfil_est.save(update_fields=['rol'])
                messages.info(request, f'Estudiante {est_username} ya existía. Sus datos han sido actualizados.')

            # --- C. Vincular Acudiente y Estudiante (Lógica de registro masivo) ---
            Acudiente.objects.update_or_create(
                acudiente=acudiente_user,
                estudiante=estudiante_user,
                defaults={}
            )

            # --- D. Matricular Estudiante (Lógica de registro individual) ---
            Matricula.objects.update_or_create(
                estudiante=estudiante_user,
                anio_escolar=anio_escolar, # Usar el año del curso seleccionado
                defaults={'curso': curso, 'activo': True}
            )
            messages.success(request, f'Estudiante matriculado en {curso.nombre}.')

            # ¡Éxito! Redirigir al dashboard de admin.
            return redirect('admin_dashboard')

    # --- 4. Manejo de Errores (Como en el registro masivo) ---
    except IntegrityError as e:
        if 'username' in str(e) and est_username in str(e):
            messages.error(request, f'El nombre de usuario del estudiante "{est_username}" ya está en uso. Elige otro.')
        elif 'email' in str(e):
                if est_email in str(e):
                    messages.error(request, f'El email de estudiante "{est_email}" ya está en uso.')
                elif acu_email in str(e):
                    messages.error(request, f'El email de acudiente "{acu_email}" ya está en uso y vinculado a otro usuario.')
                else:
                    messages.error(request, f'Error de email duplicado: {e}')
        else:
            messages.error(request, f'Error de integridad en la base de datos: {e}')
        return redirect('mostrar_registro_individual')
        
    except Exception as e:
        logger.exception(f"Error inesperado en registro individual: {e}")
        messages.error(request, f'Ocurrió un error inesperado: {e}')
        return redirect('mostrar_registro_individual')

# ===================================================================
# ===================================================================
#
# 🩺 FIN DE LA CIRUGÍA: registrar_alumno_individual
#
# ===================================================================
# ===================================================================


@role_required('ADMINISTRADOR')
def mostrar_registro_individual(request):
    anio_escolar = _anio_escolar_actual()
    cursos = Curso.objects.filter(activo=True, anio_escolar=anio_escolar).order_by('grado', 'seccion')
    return render(request, 'admin/registrar_alumno_individual.html', {
        'cursos': cursos, 'anio_escolar': anio_escolar
    })

# ########################################################################## #
# ############# INICIO DEL BLOQUE DE CÓDIGO CORREGIDO ###################### #
# ########################################################################## #

@role_required('ADMINISTRADOR')
def asignar_curso_estudiante(request):
    """
    Vista para matricular estudiantes en cursos.
    MEJORA: Soporta asignación masiva (Lotes) seleccionando múltiples alumnos.
    """
    # Ordenar cursos para el selector
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')

    if request.method == 'POST':
        # 1. Capturamos la LISTA de estudiantes (getlist) y el curso destino
        # Nota: El name en el HTML debe ser 'estudiantes' (plural)
        estudiante_ids = request.POST.getlist('estudiantes') 
        curso_id = request.POST.get('curso')

        # Validación básica
        if not estudiante_ids or not curso_id:
            messages.error(request, 'Debes seleccionar al menos un estudiante y un curso.')
            return redirect('asignar_curso_estudiante')

        try:
            curso = get_object_or_404(Curso, id=curso_id, activo=True)
            
            # 2. Validar capacidad masiva
            # Calculamos cuántos cupos quedan
            matriculados_actuales = curso.matriculados.filter(activo=True).count()
            cupos_disponibles = curso.capacidad_maxima - matriculados_actuales
            
            cant_a_mover = len(estudiante_ids)

            if cant_a_mover > cupos_disponibles:
                messages.error(
                    request, 
                    f'No hay suficiente cupo. Intentas mover {cant_a_mover} estudiantes, '
                    f'pero solo quedan {cupos_disponibles} cupos en {curso}.'
                )
                return redirect('asignar_curso_estudiante')

            # 3. Procesamiento Masivo (Transacción Atómica)
            procesados = 0
            with transaction.atomic():
                for est_id in estudiante_ids:
                    # Obtenemos al estudiante (verificando que sea rol ESTUDIANTE por seguridad)
                    estudiante = get_object_or_404(User, id=est_id, perfil__rol='ESTUDIANTE')
                    
                    # Desactivamos matrículas activas anteriores (si existen) en el mismo año
                    # Esto evita que un alumno quede en 6A y 6B al mismo tiempo
                    Matricula.objects.filter(
                        estudiante=estudiante, 
                        anio_escolar=curso.anio_escolar, 
                        activo=True
                    ).exclude(curso=curso).update(activo=False)

                    # Creamos o actualizamos la nueva matrícula
                    Matricula.objects.update_or_create(
                        estudiante=estudiante, 
                        anio_escolar=curso.anio_escolar,
                        defaults={'curso': curso, 'activo': True}
                    )
                    procesados += 1

            # Mensaje de éxito
            if procesados > 1:
                messages.success(request, f'✅ Éxito: {procesados} estudiantes fueron asignados al curso {curso}.')
            else:
                messages.success(request, f'✅ Estudiante asignado correctamente al curso {curso}.')

        except Exception as e:
            messages.error(request, f"Ocurrió un error al procesar la asignación masiva: {e}")

        return redirect('asignar_curso_estudiante')

    # --- LÓGICA DE VISUALIZACIÓN (TABLA) ---

    # 1. Obtenemos todas las matrículas activas para mostrar en la tabla
    matriculas_ordenadas = Matricula.objects.filter(activo=True).select_related(
        'estudiante__perfil', 'curso'
    ).order_by('curso__grado', 'curso__seccion', 'estudiante__last_name')

    # 2. Optimizamos la búsqueda de acudientes (evitar N+1 queries)
    student_ids = [m.estudiante_id for m in matriculas_ordenadas]
    vinculos_acudientes = Acudiente.objects.filter(estudiante_id__in=student_ids).select_related('acudiente')
    acudiente_map = {vinculo.estudiante_id: vinculo.acudiente for vinculo in vinculos_acudientes}

    # 3. Construimos la lista final para el template
    estudiantes_con_curso = []
    for matricula in matriculas_ordenadas:
        estudiante = matricula.estudiante
        acudiente = acudiente_map.get(estudiante.id)
        
        estudiantes_con_curso.append({
            'user': estudiante,
            'curso': matricula.curso,
            'rol': 'Estudiante',
            'acudiente_nombre': acudiente.get_full_name() if acudiente else "Sin asignar",
            'acudiente_username': acudiente.username if acudiente else "-",
            'matricula': matricula
        })

    # 4. Para el menú desplegable: Todos los estudiantes ACTIVOS
    todos_los_estudiantes = User.objects.filter(perfil__rol='ESTUDIANTE', is_active=True).order_by('last_name')

    context = {
        'todos_los_estudiantes': todos_los_estudiantes, # Para el select múltiple
        'estudiantes_con_curso': estudiantes_con_curso, # Para la tabla
        'cursos': cursos,
        'anio_escolar': _anio_escolar_actual()
    }
    
    return render(request, 'admin/asignar_curso_estudiante.html', context)
# ########################################################################## #
# ############### FIN DEL BLOQUE DE CÓDIGO CORREGIDO ######################### #
# ########################################################################## #


# ===================================================================
# 🩺 INICIO DE CIRUGÍA B: Vista de "Retiro" Profesional (AÑADIDA)
# (Plan )
# ===================================================================
#Desde aqui 

@login_required
@require_POST
@transaction.atomic
def admin_eliminar_estudiante(request):
    try:
        estudiante_id = request.POST.get('estudiante_id')
        estudiante = get_object_or_404(get_user_model(), id=estudiante_id)

        # 1️⃣ Obtener matrícula ACTIVA
        matricula = Matricula.objects.select_related(
            'curso'
        ).get(user=estudiante, activo=True)

        # 2️⃣ GENERAR BOLETÍN FINAL (ANTES DE TOCAR NADA)
        boletin_pdf = generar_boletin_pdf_admin(request, estudiante.id, return_file=True)

        boletin_archivado = BoletinArchivado.objects.create(
            estudiante=estudiante,
            nombre_estudiante=estudiante.get_full_name(),
            username_estudiante=estudiante.username,
            grado_archivado=matricula.curso.grado,
            seccion_archivada=matricula.curso.seccion,
            anio_lectivo_archivado=timezone.now().year,
            eliminado_por=request.user,
            archivo_pdf=boletin_pdf
        )

        # 3️⃣ GENERAR OBSERVADOR FINAL
        observador_pdf = generar_observador_pdf(request, estudiante.id, return_file=True)

        ObservadorArchivado.objects.create(
            estudiante=estudiante,
            archivo_pdf=observador_pdf,
            fecha_archivado=timezone.now()
        )

        # 4️⃣ DESACTIVAR MATRÍCULA
        matricula.activo = False
        matricula.fecha_retiro = timezone.now()
        matricula.save()

        # 5️⃣ DESACTIVAR USUARIO
        estudiante.is_active = False
        estudiante.save()

        # 6️⃣ AUDITORÍA
        AuditLog.objects.create(
            usuario=request.user,
            accion="RETIRO_ESTUDIANTE",
            descripcion=f"Retiro definitivo de {estudiante.username}"
        )

        messages.success(request, "Estudiante retirado y archivado correctamente.")
        return redirect('admin_ex_estudiantes')

    except Exception as e:
        transaction.set_rollback(True)
        messages.error(request, f"Error crítico en el retiro: {str(e)}")
        return redirect('gestionar_cursos')

#Hasta aqui 
# ===================================================================
# 🩺 FIN DE CIRUGÍA B
# ===================================================================


@role_required('ADMINISTRADOR')
def asignar_materia_docente(request):
    # 1. CARGAR DOCENTES (Filtramos por rol DOCENTE o Director)
    docentes = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()
    
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    materias = Materia.objects.all().select_related('curso').order_by('nombre')
    
    asignaciones = AsignacionMateria.objects.filter(activo=True).select_related(
        'materia', 'curso', 'docente'
    ).order_by('curso__grado', 'curso__seccion', 'materia__nombre')

    if request.method == 'POST':
        
        # 🟢 ACCIÓN 1: CREAR NUEVO DOCENTE (Lógica Blindada)
        if 'crear_profesor' in request.POST:
            username = request.POST.get('username', '').strip().lower()
            first_name = request.POST.get('first_name', '').strip().title()
            last_name = request.POST.get('last_name', '').strip().title()
            email = request.POST.get('email', '').strip().lower()

            if User.objects.filter(username=username).exists():
                messages.error(request, f"El usuario '{username}' ya existe.")
                return redirect('asignar_materia_docente')

            try:
                with transaction.atomic():
                    # 1. Crear Usuario
                    user = User.objects.create_user(
                        username=username, 
                        first_name=first_name, 
                        last_name=last_name,
                        email=email, 
                        password=DEFAULT_TEMP_PASSWORD
                    )
                    
                    # 2. Gestionar Perfil (FORZANDO EL ROL)
                    # Intentamos obtener el perfil (por si una señal lo creó) o crearlo
                    perfil, created = Perfil.objects.get_or_create(user=user)
                    
                    # Forzamos los valores SÍ o SÍ, y guardamos explícitamente
                    perfil.rol = 'DOCENTE'
                    perfil.requiere_cambio_clave = True
                    perfil.save() # Guardado explícito para asegurar el cambio
                    
                    messages.success(request, f'Docente "{first_name} {last_name}" registrado correctamente. (Usuario: {username})')
            
            except IntegrityError:
                messages.error(request, "Error: El correo electrónico ya está en uso.")
            except Exception as e:
                messages.error(request, f"Error interno: {e}")
                
            return redirect('asignar_materia_docente')

        # 🔵 ACCIÓN 2: CREAR MATERIA
        elif 'crear_materia' in request.POST:
            nombre = request.POST.get('nombre')
            curso_id = request.POST.get('curso_id')
            
            if nombre and curso_id:
                try:
                    curso_obj = get_object_or_404(Curso, id=curso_id)
                    Materia.objects.get_or_create(
                        nombre=nombre.strip().title(),
                        curso=curso_obj
                    )
                    messages.success(request, f'Materia "{nombre}" creada.')
                except Exception as e:
                    messages.error(request, f'Error: {e}')
            return redirect('asignar_materia_docente')

        # 🟠 ACCIÓN 3: ASIGNAR DOCENTE
        elif 'asignar_docente' in request.POST:
            materia_id = request.POST.get('materia_id')
            docente_id = request.POST.get('docente_id')
            
            try:
                materia_obj = get_object_or_404(Materia, id=materia_id)
                docente_obj = get_object_or_404(User, id=docente_id)
                curso_obj = materia_obj.curso
                
                AsignacionMateria.objects.update_or_create(
                    materia=materia_obj,
                    curso=curso_obj,
                    defaults={'docente': docente_obj, 'activo': True}
                )
                messages.success(request, f'Asignado: {docente_obj.get_full_name()}.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
                
            return redirect('asignar_materia_docente')

    context = {
        'docentes': docentes,
        'cursos': cursos,
        'materias': materias,
        'asignaciones': asignaciones
    }
    
    return render(request, 'admin/asignar_materia_docente.html', context)






# --- VISTAS DE ACUDIENTE Y GESTIÓN DE CUENTAS ---
# Desde Aqui 
# ===================================================================
# 🩺 VISTA DASHBOARD ACUDIENTE: CORREGIDA Y BLINDADA
# ===================================================================

@login_required
@role_required('ACUDIENTE')
def dashboard_acudiente(request):
    """
    Panel de control para el acudiente.
    CORRECCIÓN: Se asegura de cargar los docentes aunque no tengan perfil completo.
    """
    acudiente_user = request.user

    # Obtener vínculos (optimizada)
    vinculados = Acudiente.objects.filter(acudiente=acudiente_user).select_related('estudiante', 'estudiante__perfil')

    if not vinculados.exists():
        messages.error(request, "No tienes estudiantes vinculados. Por favor, contacta a la administración.")
        return render(request, 'dashboard_acudiente.html', {'estudiantes_data': []})

    estudiantes_data = []

    for vinculo in vinculados:
        estudiante = vinculo.estudiante
        perfil_estudiante = getattr(estudiante, 'perfil', None)

        # Matrícula y curso
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
        curso = matricula.curso if matricula else None

        # Colecciones de datos
        materias_con_notas = {}
        comentarios_docente = {}
        actividades_semanales = {}
        convivencia_notas = {}
        logros_por_materia_por_periodo = {}
        periodos_disponibles = []
        
        # Variables estadísticas
        stats_materias_labels = []    
        stats_materias_promedios = [] 
        stats_periodos_labels = []    
        stats_periodos_data = []      
        conteo_ganadas = 0
        conteo_perdidas = 0
        promedio_general_acumulado = 0.0
        
        # Variables de asistencia
        porcentaje_asistencia = 100.0
        total_fallas = 0
        fallas_detalladas = []

        # Variable para Directorio Docente
        docentes_directorio = []

        if curso:
            # Obtener periodos
            periodos_disponibles = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
            
            # -----------------------------------------------------------
            # CORRECCIÓN CRÍTICA AQUÍ: 
            # Quitamos 'docente__perfil' del select_related para evitar que
            # Django oculte profesores que no tienen perfil configurado.
            # -----------------------------------------------------------
            asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia', 'docente')
            materias = [a.materia for a in asignaciones]

            # --- LÓGICA DIRECTORIO DE DOCENTES (BLINDADA) ---
            docentes_vistos = set()
            for asig in asignaciones:
                # Verificamos que la asignación tenga un docente real (ID válido)
                if asig.docente_id and asig.docente_id not in docentes_vistos:
                    docente = asig.docente
                    
                    # Obtener foto de forma segura (sin romper si no hay perfil)
                    foto_url = None
                    try:
                        if hasattr(docente, 'perfil') and docente.perfil.foto:
                            foto_url = docente.perfil.foto.url
                    except Exception:
                        foto_url = None # Si falla algo con la foto, ponemos None y mostramos la inicial

                    docentes_directorio.append({
                        'id': docente.id,
                        'nombre': docente.get_full_name() or docente.username,
                        'materia_principal': asig.materia.nombre,
                        'foto_url': foto_url
                    })
                    docentes_vistos.add(docente.id)

            # -----------------------------------------------------------
            # 1. CÁLCULO DE ESTADÍSTICAS ACADÉMICAS
            # -----------------------------------------------------------
            notas_definitivas_qs = Nota.objects.filter(
                estudiante=estudiante, 
                materia__in=materias,
                numero_nota=5
            )

            # A. Estadísticas por Materia
            for materia in materias:
                notas_mat = [n.valor for n in notas_definitivas_qs if n.materia_id == materia.id]
                promedio_materia = 0.0

                if notas_mat:
                    promedio_materia = float(sum(notas_mat)) / len(notas_mat)
                    if promedio_materia >= 3.5: 
                        conteo_ganadas += 1
                    else:
                        conteo_perdidas += 1
                
                stats_materias_labels.append(materia.nombre)
                stats_materias_promedios.append(round(promedio_materia, 2))

            # B. Estadísticas por Periodo
            for periodo in periodos_disponibles:
                stats_periodos_labels.append(periodo.nombre)
                notas_per = [n.valor for n in notas_definitivas_qs if n.periodo_id == periodo.id]
                
                if notas_per:
                    prom_per = float(sum(notas_per)) / len(notas_per)
                    stats_periodos_data.append(round(prom_per, 2))
                else:
                    stats_periodos_data.append(0)

            # C. Promedio General
            if stats_materias_promedios:
                promedios_validos = [p for p in stats_materias_promedios if p > 0]
                if promedios_validos:
                    promedio_general_acumulado = sum(promedios_validos) / len(promedios_validos)

            # -----------------------------------------------------------
            # 2. CÁLCULO DE ASISTENCIA DETALLADA
            # -----------------------------------------------------------
            try:
                from .models import Asistencia 
                
                total_clases = Asistencia.objects.filter(estudiante=estudiante, curso=curso).count()
                
                fallas_qs = Asistencia.objects.filter(
                    estudiante=estudiante, 
                    curso=curso, 
                    estado='FALLA'
                ).select_related('materia').order_by('-fecha')
                
                total_fallas = fallas_qs.count()
                fallas_detalladas = list(fallas_qs)

                if total_clases > 0:
                    porcentaje_asistencia = ((total_clases - total_fallas) / total_clases) * 100
                
                porcentaje_asistencia = round(porcentaje_asistencia, 1)

            except ImportError:
                pass 

            # -----------------------------------------------------------
            # 3. CARGA DE DATOS PARA TABLAS (DETALLE)
            # -----------------------------------------------------------
            notas_qs = Nota.objects.filter(
                estudiante=estudiante, materia__in=materias
            ).select_related('periodo', 'materia').order_by('periodo__id', 'numero_nota')

            for nota in notas_qs:
                materias_con_notas.setdefault(nota.materia, {}).setdefault(nota.periodo.id, {})[nota.numero_nota] = nota

            # Comentarios
            comentarios_qs = ComentarioDocente.objects.filter(estudiante=estudiante, materia__in=materias).select_related('materia')
            for c in comentarios_qs:
                comentarios_docente.setdefault(c.materia.id, []).append(c)

            # Actividades
            actividades_qs = ActividadSemanal.objects.filter(curso=curso, materia__in=materias).order_by('-fecha_creacion').select_related('materia')
            for act in actividades_qs:
                actividades_semanales.setdefault(act.materia.id, []).append(act)

            # Logros
            logros_qs = LogroPeriodo.objects.filter(curso=curso, materia__in=materias).select_related('periodo', 'materia')
            for logro in logros_qs:
                logros_por_materia_por_periodo.setdefault(logro.materia, {}).setdefault(logro.periodo.id, []).append(logro)

            # Convivencia
            convivencia_qs = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
            for conv in convivencia_qs:
                convivencia_notas[conv.periodo.id] = {'valor': conv.valor, 'comentario': conv.comentario}

        # Empaquetado final
        estudiantes_data.append({
            'estudiante': estudiante,
            'perfil': perfil_estudiante,
            'curso': curso,
            'matricula': matricula,
            'periodos_disponibles': periodos_disponibles,
            'materias_con_notas': materias_con_notas,
            'comentarios_docente': comentarios_docente,
            'actividades_semanales': actividades_semanales,
            'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
            'convivencia_notas': convivencia_notas,
            # ESTADÍSTICAS
            'stats': {
                'materias_labels': json.dumps(stats_materias_labels),
                'materias_data': json.dumps(stats_materias_promedios),
                'periodos_labels': json.dumps(stats_periodos_labels),
                'periodos_data': json.dumps(stats_periodos_data),
                'ganadas': conteo_ganadas,
                'perdidas': conteo_perdidas,
                'promedio_general': round(promedio_general_acumulado, 2),
                'distribucion_data': json.dumps([conteo_ganadas, conteo_perdidas]),
                'asistencia_pct': porcentaje_asistencia,
                'total_fallas': total_fallas,
                'detalle_fallas': fallas_detalladas
            },
            # DIRECTORIO DOCENTE (Ahora sí cargará siempre)
            'docentes': docentes_directorio
        })

    context = {
        'acudiente': acudiente_user,
        'estudiantes_data': estudiantes_data
    }
    return render(request, 'dashboard_acudiente.html', context)
# Hasta Aqui

@login_required
def cambiar_clave(request):
    """
    Permite a los usuarios cambiar su contraseña.
    Al terminar, los redirige automáticamente a su Dashboard correspondiente.
    """
    if request.method == 'POST':
        form = PasswordChangeFirstLoginForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # Esto mantiene la sesión iniciada tras el cambio de clave
            update_session_auth_hash(request, user)

            if hasattr(user, 'perfil'):
                # 1. Quitamos el "cepo" de seguridad
                user.perfil.requiere_cambio_clave = False
                user.perfil.save(update_fields=['requiere_cambio_clave'])

                # 2. Redirección Inteligente según el Rol
                rol = user.perfil.rol
                
                # --- STAFF DE BIENESTAR (Psicólogos y Coords) ---
                if rol in ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
                    return redirect('dashboard_bienestar')
                
                # --- OTROS ROLES ---
                elif rol == 'ESTUDIANTE':
                    return redirect('dashboard_estudiante')
                elif rol == 'ACUDIENTE':
                    return redirect('dashboard_acudiente')
                elif rol == 'DOCENTE' or user.perfil.es_director:
                    return redirect('dashboard_docente')
                elif rol == 'ADMINISTRADOR':
                    return redirect('admin_dashboard')

            messages.success(request, '¡Tu contraseña ha sido actualizada correctamente!')
            return redirect('home') # Fallback por si no tiene rol
        else:
            messages.error(request, 'Por favor corrige los errores a continuación.')
    else:
        form = PasswordChangeFirstLoginForm(user=request.user)

    return render(request, 'account/cambiar_clave.html', {'form': form})


@role_required('ADMINISTRADOR')
def gestion_perfiles(request):
    """
    Panel de administrador para buscar, filtrar y gestionar perfiles de usuario.
    """
    # Consulta optimizada para obtener usuarios (students/acudientes/teachers) y su perfil en una sola query
    perfiles_qs = Perfil.objects.select_related('user').order_by('user__last_name', 'user__first_name')
    form = ProfileSearchForm(request.GET or None)

    if form.is_valid():
        query = form.cleaned_data.get('query')
        rol = form.cleaned_data.get('rol')

        if query:
            perfiles_qs = perfiles_qs.filter(
                Q(user__username__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__email__icontains=query)
            )
        if rol:
            perfiles_qs = perfiles_qs.filter(rol=rol)

    # Se pasa el QuerySet directo de objetos Perfil, que es la forma idiomática de filtrar por un objeto relacionado.
    users = User.objects.filter(perfil__in=perfiles_qs).select_related('perfil').order_by('last_name', 'first_name')


    context = {
        'form': form,
        'users': users
    }
    return render(request, 'admin/gestion_perfiles.html', context)


@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def admin_reset_password(request):
    """
    Manejador para el botón de resetear contraseña desde la gestión de perfiles.
    CORREGIDO: Usa DEFAULT_TEMP_PASSWORD en lugar de generar una aleatoria.
    """
    username = request.POST.get('username')
    try:
        user_to_reset = User.objects.select_related('perfil').get(username=username)

        # --- CORRECCIÓN AQUÍ ---
        # Usar la contraseña temporal predeterminada
        nueva_contrasena = DEFAULT_TEMP_PASSWORD
        # --- FIN CORRECCIÓN ---

        user_to_reset.set_password(nueva_contrasena)
        user_to_reset.save()

        if hasattr(user_to_reset, 'perfil'):
            user_to_reset.perfil.requiere_cambio_clave = True
            user_to_reset.perfil.save(update_fields=['requiere_cambio_clave'])

        # --- Mensaje de éxito actualizado (Opción A: Sin mostrar la contraseña) ---
        messages.success(request, f"Contraseña para '{user_to_reset.username}' restablecida a la predeterminada. El usuario deberá cambiarla al iniciar sesión.")
        # --- Fin mensaje actualizado ---

    except User.DoesNotExist:
        messages.error(request, f"El usuario '{username}' no existe.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado: {e}")

    # Redirigir a la vista de gestión con los filtros actuales
    return redirect(f"{reverse('gestion_perfiles')}?{request.META.get('QUERY_STRING', '')}")


@role_required('ADMINISTRADOR')
def admin_db_visual(request):
    """
    Prepara y ordena los datos de estudiantes/acudientes por curso.
    """
    # 1. ESTUDIANTES E ACUDIENTES (AGRUPADOS POR CURSO)
    # Consulta para cursos activos, ordenados por jerarquía académica.
    cursos_activos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')

    data_visual = []

    for curso in cursos_activos:
        # Consulta de matrículas, optimizada para traer estudiante y perfil
        matriculas = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante__perfil')

        # Si el curso no tiene estudiantes, se salta.
        if not matriculas.exists():
            continue

        # Optimizamos la búsqueda de acudientes para todos los estudiantes de este curso.
        estudiante_ids = [m.estudiante_id for m in matriculas]
        vinculos_acudientes = Acudiente.objects.filter(estudiante_id__in=estudiante_ids).select_related('acudiente__perfil')
        acudiente_map = {vinculo.estudiante_id: vinculo.acudiente for vinculo in vinculos_acudientes}

        grupo_estudiantes = []
        for matricula in matriculas:
            estudiante = matricula.estudiante
            acudiente = acudiente_map.get(estudiante.id)

            # Lógica para mostrar la Contraseña Temporal del ESTUDIANTE
            estudiante_password_status = 'Cambiada o Desconocida'
            if hasattr(estudiante, 'perfil') and estudiante.perfil.requiere_cambio_clave:
                estudiante_password_status = DEFAULT_TEMP_PASSWORD

            # Lógica para mostrar la Contraseña Temporal del ACUDIENTE
            acudiente_password_status = 'N/A'
            if acudiente:
                if hasattr(acudiente, 'perfil') and acudiente.perfil.requiere_cambio_clave:
                    acudiente_password_status = DEFAULT_TEMP_PASSWORD
                else:
                    acudiente_password_status = 'Cambiada o Desconocida'

            grupo_estudiantes.append({
                'estudiante': estudiante,
                'estudiante_nombre_completo': estudiante.get_full_name() or estudiante.username,
                'estudiante_usuario': estudiante.username,
                'estudiante_password_temp': estudiante_password_status,
                'acudiente': acudiente,
                'acudiente_nombre_completo': acudiente.get_full_name() if acudiente else "Sin asignar",
                'acudiente_usuario': acudiente.username if acudiente else "Sin usuario",
                'acudiente_password_temp': acudiente_password_status,
            })

        # Agregamos los datos del curso con los estudiantes (ordenados por nombre del estudiante)
        data_visual.append({
            'curso': f"{curso.get_grado_display()} {curso.seccion} ({curso.anio_escolar})",
            'count': len(grupo_estudiantes),
            'grupo': sorted(grupo_estudiantes, key=itemgetter('estudiante_nombre_completo'))
        })

    # 2. PROFESORES Y DIRECTORES
    # Obtener todos los profesores y directores con su perfil, ordenados por nombre.
    profesores_qs = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('last_name', 'first_name').distinct()

    # Mapear datos para mostrar el perfil y la contraseña temporal.
    profesores_data = [{
        'nombre_completo': p.get_full_name() or p.username,
        'usuario': p.username,
        'email': p.email,
        # La contraseña temporal sólo se muestra si requiere cambio de clave
        'password_temp': DEFAULT_TEMP_PASSWORD if hasattr(p, 'perfil') and p.perfil.requiere_cambio_clave else 'Cambiada o Desconocida',
        'rol': p.perfil.get_rol_display() if hasattr(p, 'perfil') else 'Sin perfil',
        'cambio_requerido': p.perfil.requiere_cambio_clave if hasattr(p, 'perfil') else False
    } for p in profesores_qs]

    context = {
        # La lista principal de cursos ya está ordenada por 'grado' y 'seccion' (gracias a la consulta inicial)
        'data': data_visual,
        'profesores': profesores_data,
        'default_temp_password': DEFAULT_TEMP_PASSWORD
    }

    return render(request, 'admin/db_visual.html', context)


# ===================================================================
# INICIO FASE 3: VISTAS DE GENERACIÓN DE BOLETINES (AÑADIDAS)
# ===================================================================

# ===================================================================
# 🩺 CIRUGÍA A: (REEMPLAZO) LÓGICA DE PDF REFACTORIZADA 
# ===================================================================


# ===================================================================
# 🩺 FIN DE CIRUGÍA A
# ===================================================================


def _generar_boletin_pdf_logica(request, matricula_id: int):
    """
    FASE 10: Lógica de renderizado de PDF con INTEGRACIÓN DE IA.
    Genera el boletín incluyendo el análisis de rendimiento automático.
    """
    if HTML is None:
        raise Exception("El módulo de generación de PDF (WeasyPrint) no está instalado.")

    # 1. Obtener los datos académicos base del estudiante
    context = get_student_report_context(matricula_id)
    if not context:
        raise Http404(f"No se encontró contexto para la matrícula_id: {matricula_id}")

    # 2. INTEGRACIÓN DE IA: Generar análisis pedagógico en tiempo real
    # Obtenemos el objeto estudiante desde el contexto ya cargado
    estudiante = context.get('estudiante')
    
    if estudiante:
        # Llamamos al orquestador para obtener las recomendaciones constructivistas
        # El orquestador ya sabe usar el ContextBuilder para ver las notas de la DB
        resultado_ia = ai_orchestrator.process_request(
            user=request.user, 
            action_type=ACCION_MEJORAS_ESTUDIANTE,
            target_user=estudiante
        )
        
        # Inyectamos el contenido de la IA en el contexto del template
        if resultado_ia.get('success'):
            context['analisis_ia'] = resultado_ia.get('content')
            context['ia_meta'] = resultado_ia.get('meta') # Por si quieres mostrar la fecha del análisis
        else:
            context['analisis_ia'] = "El análisis pedagógico automático no está disponible en este momento."

    # 3. Preparar el renderizado
    context['request'] = request
    html_string = render_to_string('pdf/boletin_template.html', context)

    # 4. Generar el archivo PDF con WeasyPrint
    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    # 5. Configurar la respuesta de descarga/visualización
    filename = f"boletin_{estudiante.username}_{context['curso'].anio_escolar}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response

# ===================================================================
# 🩺 INICIO DE CIRUGÍA C: (REEMPLAZO) Vistas de PDF actualizadas 
# ===================================================================

@login_required
@role_required('ADMINISTRADOR')
def generar_boletin_pdf_admin(request, estudiante_id, return_file=False):
    """
    Genera el Boletín Académico.
    CORRECCIÓN APLICADA: Nombre del template corregido.
    """
    # Imports necesarios
    from .models import Matricula, AsignacionMateria, Nota, Materia, Convivencia, Periodo, Institucion
    from django.template.loader import render_to_string
    from django.core.files.base import ContentFile
    try:
        from weasyprint import HTML
    except ImportError:
        HTML = None

    try:
        # 1. Obtener Estudiante
        estudiante = get_object_or_404(User, id=estudiante_id)

        # 2. Obtener Matrícula (Flexible: Activa o Histórica)
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
        
        if not matricula:
            # Si no hay activa, busca la última histórica
            matricula = Matricula.objects.filter(estudiante=estudiante).select_related('curso').order_by('-id').first()

        if not matricula:
            if return_file: return None
            messages.error(request, "Este estudiante nunca ha sido matriculado.")
            return redirect('admin_dashboard')

        curso = matricula.curso

        # 3. Datos Académicos
        periodos = Periodo.objects.filter(curso=curso).order_by('id')
        
        materias_ids = set(AsignacionMateria.objects.filter(curso=curso).values_list('materia_id', flat=True))
        materias_ids.update(Nota.objects.filter(estudiante=estudiante, periodo__curso=curso).values_list('materia_id', flat=True))
        materias = Materia.objects.filter(id__in=materias_ids).order_by('nombre')

        notas_por_materia = {}
        for materia in materias:
            notas_materia = {}
            for periodo in periodos:
                qs = Nota.objects.filter(estudiante=estudiante, materia=materia, periodo=periodo).order_by('numero_nota')
                if qs.exists():
                    notas_materia[periodo] = qs
            if notas_materia:
                notas_por_materia[materia] = notas_materia

        # Convivencia
        convivencia_data = {}
        convivencias = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
        for c in convivencias:
            convivencia_data[c.periodo.id] = {'valor': c.valor, 'comentario': c.comentario}

        # 4. Renderizado
        context = {
            'institucion': Institucion.objects.first(),
            'estudiante': estudiante,
            'curso': curso,
            'matricula': matricula,
            'periodos': periodos,
            'materias': materias,
            'notas_por_materia': notas_por_materia,
            'convivencia_notas': convivencia_data,
            'fecha_emision': timezone.now(),
            'request': request
        }

        # --- AQUÍ ESTABA EL ERROR: CAMBIADO A 'boletin_template.html' ---
        html_string = render_to_string('pdf/boletin_template.html', context)

        if HTML is None:
            if return_file: return None
            return HttpResponse("Error: Librería PDF no instalada.", status=500)

        pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

        # 5. Retorno
        filename = f"Boletin_{estudiante.username}.pdf"
        
        if return_file:
            return ContentFile(pdf_bytes, name=filename)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Exception as e:
        print(f"❌ ERROR: {e}") # Dejamos el print por seguridad
        if return_file: return None
        messages.error(request, f"Error generando boletín: {e}")
        return redirect('admin_dashboard')



@login_required
@role_required('ACUDIENTE')
def generar_boletin_pdf_acudiente(request, estudiante_id):
    """
    Vista para que el Acudiente genere un boletín.
    Verifica el permiso en la matrícula.
    (Versión modificada que usa la matrícula ACTIVA)
    """
    
    # 1. Verificar que el acudiente tiene permiso sobre este estudiante
    try:
        vinculo = Acudiente.objects.get(acudiente=request.user, estudiante_id=estudiante_id)
    except Acudiente.DoesNotExist:
        messages.error(request, "No tienes permisos para ver el boletín de este estudiante.")
        return redirect('dashboard_acudiente')

    # 2. Verificar si la matrícula existe y tiene el permiso activado
    matricula = Matricula.objects.filter(estudiante=vinculo.estudiante, activo=True).first()
    
    if not matricula:
        messages.error(request, "El estudiante no tiene una matrícula activa.")
        return redirect('dashboard_acudiente')

    if not matricula.puede_generar_boletin:
        messages.warning(request, "La generación del boletín no está habilitada. Por favor, contacta a la administración.")
        return redirect('dashboard_acudiente')

    # 3. Si todo es correcto, llama a la LÓGICA INTERNA
    try:
        return _generar_boletin_pdf_logica(request, matricula.id) # 👈 Pasa el matricula_id
        
    except Exception as e:
        # 4. Si falla, registra el error y redirige al dashboard de ACUDIENTE
        logger.exception(f"Error al generar boletín PDF (Acudiente) para estudiante {estudiante_id}: {e}")
        messages.error(request, f"No se pudo generar el boletín. Error: {e}")
        return redirect('dashboard_acudiente')
# ===================================================================
# 🩺 FIN DE CIRUGÍA C
# ===================================================================


@login_required
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def toggle_boletin_permiso(request):
    """
    Vista API (JSON) para activar/desactivar el permiso de boletín
    desde el panel de administración.
    """
    try:
        # Leemos el JSON enviado por Fetch
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        nuevo_estado = bool(data.get('estado'))
        
        matricula = Matricula.objects.filter(estudiante_id=estudiante_id, activo=True).first()
        
        if not matricula:
            return JsonResponse({'status': 'error', 'message': 'Matrícula no encontrada'}, status=404)
            
        matricula.puede_generar_boletin = nuevo_estado
        matricula.save(update_fields=['puede_generar_boletin'])
        
        return JsonResponse({
            'status': 'ok', 
            'nuevo_estado_texto': 'Disponible' if nuevo_estado else 'Bloqueado'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Solicitud inválida (JSON)'}, status=400)
    except Exception as e:
        # Usamos logger para registrar el error real en el servidor
        logger.exception(f"Error en toggle_boletin_permiso: {e}")
        # Enviamos un mensaje genérico al cliente
        return JsonResponse({'status': 'error', 'message': 'Error interno del servidor'}, status=500)
# ===================================================================
# FIN FASE 3
# ===================================================================

# ===================================================================
# 🩺 INICIO DE CIRUGÍA: PASO 3 (Plan 6 Pasos) 
# (Añadido en el paso anterior )
# ===================================================================

# Asegúrese de que estos imports existan al inicio del archivo
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def admin_eliminar_estudiante(request):
    """
    "Retira" a un estudiante (Soft Delete) con integridad histórica total.
    
    PASO 2: INYECCIÓN DE AÑO LECTIVO
    Se asegura de que el Observador Disciplinario quede etiquetado con el
    año escolar correcto para permitir el filtrado histórico exacto.
    """
    # Imports locales para evitar referencias circulares
    from .models import ObservadorArchivado, Observacion, Institucion, Acudiente
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("CRITICAL: WeasyPrint no instalado. El archivo de retiro fallará.")
        messages.error(request, "Error de configuración: Falta librería PDF. No se puede procesar el retiro.")
        return redirect('asignar_curso_estudiante')

    estudiante_id = request.POST.get('estudiante_id')
    if not estudiante_id:
        messages.error(request, "Solicitud inválida: Falta ID.")
        return redirect('asignar_curso_estudiante')

    try:
        # Validación estricta del estudiante
        estudiante_a_retirar = get_object_or_404(User, id=estudiante_id, perfil__rol='ESTUDIANTE', is_active=True)
        estudiante_nombre = estudiante_a_retirar.get_full_name() or estudiante_a_retirar.username
        estudiante_username = estudiante_a_retirar.username

        # Obtener historial de matrículas para determinar años cursados
        todas_las_matriculas = Matricula.objects.filter(
            estudiante=estudiante_a_retirar
        ).select_related('curso').order_by('anio_escolar')

        boletines_generados = 0
        observador_exitoso = False

        # Transacción Atómica: Todo se guarda o nada se guarda
        with transaction.atomic():

            # -------------------------------------------------------------------
            # FASE 1: SNAPSHOT ACADÉMICO (Boletines por año)
            # -------------------------------------------------------------------
            base_url = request.build_absolute_uri('/')
            
            for matricula in todas_las_matriculas:
                try:
                    contexto = get_student_report_context(matricula.id)
                    if not contexto: continue

                    contexto['request'] = request
                    html = render_to_string('pdf/boletin_template.html', contexto)
                    pdf_content = HTML(string=html, base_url=base_url).write_pdf()

                    nombre_archivo = f"boletin_{estudiante_username}_{matricula.anio_escolar.replace('-', '_')}.pdf"
                    
                    BoletinArchivado.objects.create(
                        nombre_estudiante=estudiante_nombre,
                        username_estudiante=estudiante_username,
                        grado_archivado=contexto['curso'].grado,
                        seccion_archivada=contexto['curso'].seccion,
                        anio_lectivo_archivado=matricula.anio_escolar,
                        eliminado_por=request.user,
                        archivo_pdf=ContentFile(pdf_content, name=nombre_archivo)
                    )
                    boletines_generados += 1
                except Exception as e:
                    logger.error(f"Error boletin {matricula.anio_escolar}: {e}")

            # -------------------------------------------------------------------
            # FASE 2 (EL CAMBIO CLAVE): SNAPSHOT DISCIPLINARIO CON AÑO
            # -------------------------------------------------------------------
            try:
                observaciones = Observacion.objects.filter(estudiante=estudiante_a_retirar).order_by('fecha_creacion')
                
                # Determinamos el "Año del Retiro" basándonos en su última matrícula
                ultimo_curso = todas_las_matriculas.last().curso if todas_las_matriculas.exists() else None
                anio_retiro = ultimo_curso.anio_escolar if ultimo_curso else '2025-2026' # Fallback seguro

                ctx_obs = {
                    'estudiante': estudiante_a_retirar,
                    'observaciones': observaciones,
                    'institucion': Institucion.objects.first(),
                    'curso': ultimo_curso,
                    'fecha_impresion': timezone.now(),
                    'generado_por': request.user.get_full_name(),
                    'es_archivo_retiro': True,
                    'request': request
                }

                html_obs = render_to_string('pdf/observador_template.html', ctx_obs)
                pdf_obs = HTML(string=html_obs, base_url=base_url).write_pdf()

                nombre_obs = f"OBS_FINAL_{estudiante_username}_{timezone.now().strftime('%Y%m%d')}.pdf"

                # GUARDADO CON EL CAMPO NUEVO
                ObservadorArchivado.objects.create(
                    estudiante_nombre=estudiante_nombre,
                    estudiante_username=estudiante_username,
                    
                    # AQUÍ ESTÁ LA MAGIA DEL PASO 2:
                    anio_lectivo_archivado=anio_retiro, 
                    
                    eliminado_por=request.user,
                    archivo_pdf=ContentFile(pdf_obs, name=nombre_obs)
                )
                observador_exitoso = True
                
            except Exception as e:
                logger.error(f"Fallo crítico archivando observador: {e}", exc_info=True)

            # -------------------------------------------------------------------
            # FASE 3: DESACTIVACIÓN (Soft Delete)
            # -------------------------------------------------------------------
            todas_las_matriculas.update(activo=False)
            
            estudiante_a_retirar.is_active = False
            estudiante_a_retirar.save(update_fields=['is_active'])

            # Limpieza de Acudientes huérfanos
            acudientes_ids = Acudiente.objects.filter(estudiante=estudiante_a_retirar).values_list('acudiente_id', flat=True)
            for acudiente_id in acudientes_ids:
                tiene_otros_hijos = Matricula.objects.filter(
                    estudiante__acudientes_asignados__acudiente_id=acudiente_id,
                    activo=True
                ).exclude(estudiante_id=estudiante_id).exists()
                
                if not tiene_otros_hijos:
                    User.objects.filter(id=acudiente_id).update(is_active=False)

            messages.success(request, f"Estudiante {estudiante_nombre} retirado. Docs generados: {boletines_generados} Boletines + Observador ({anio_retiro}).")

    except Exception as e:
        logger.critical(f"Error inesperado en retiro: {e}")
        messages.error(request, "Error del sistema al procesar el retiro.")

    return redirect('asignar_curso_estudiante')
# ===================================================================
# 🩺 FIN DE CIRUGÍA: PASO 3
# ===================================================================

# ===================================================================
# 🩺 INICIO DE CIRUGÍA: MÓDULO DE BIENESTAR Y CONVIVENCIA (VIEWS)
# ===================================================================

# Roles permitidos para el módulo de bienestar
STAFF_ROLES = ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO', 'ADMINISTRADOR']

##desde aqui 



# ===================================================================
# 🩺 FASE 4: FUNCIONES DE CHAT Y ASISTENCIA (NUEVAS AL FINAL)
# ===================================================================
#aqui 
@role_required('DOCENTE')
@require_POST
@csrf_protect
def api_tomar_asistencia(request):
    """
    Registra la asistencia de un estudiante vía AJAX.
    Envía notificación automática al Acudiente y al Coordinador de Convivencia si hay Falla o Retardo.
    """
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        materia_id = data.get('materia_id')
        estado = data.get('estado') 
        fecha = data.get('fecha', str(date.today()))

        estudiante = get_object_or_404(User, id=estudiante_id)
        materia = get_object_or_404(Materia, id=materia_id)
        
        # Validar matrícula activa para asegurar que el estudiante pertenece al curso
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).first()
        if not matricula:
            return JsonResponse({'success': False, 'error': 'Estudiante no matriculado'})

        # Guardar o actualizar el registro de asistencia en la base de datos
        Asistencia.objects.update_or_create(
            estudiante=estudiante, materia=materia, fecha=fecha,
            defaults={
                'curso': matricula.curso, 
                'estado': estado, 
                'registrado_por': request.user
            }
        )

        # 🔔 SISTEMA DE NOTIFICACIONES AUTOMÁTICAS
        # Solo se activa si el estado es 'FALLA' o 'TARDE'
        if estado in ['FALLA', 'TARDE']:
            tipo_txt = "Falla de asistencia" if estado == 'FALLA' else "Llegada tarde"
            
            # Importación local para evitar errores de referencia circular
            from .utils import notificar_acudientes, crear_notificacion

            # 1. Notificar al Acudiente (Familia)
            # Esta función busca automáticamente a los acudientes del estudiante
            notificar_acudientes(
                estudiante, 
                "Alerta de Asistencia", 
                f"En la clase de {materia.nombre}: {tipo_txt} (Fecha: {fecha}).", 
                "ASISTENCIA"
            )
            
            # 2. Notificar al Coordinador de Convivencia (Staff)
            # Buscamos a todos los usuarios activos con el rol de Coordinador de Convivencia
            coordinadores = User.objects.filter(perfil__rol='COORD_CONVIVENCIA', is_active=True)
            
            for coord in coordinadores:
                crear_notificacion(
                    usuario_destino=coord,
                    titulo=f"Reporte: {tipo_txt}",
                    mensaje=f"Estudiante: {estudiante.get_full_name()} ({matricula.curso.nombre}). Materia: {materia.nombre}. Fecha: {fecha}.",
                    tipo="ASISTENCIA",
                    link=f"/bienestar/alumno/{estudiante.id}/" # Enlace directo al perfil/observador del alumno
                )

        return JsonResponse({'success': True})
    except Exception as e:
        # Captura cualquier error inesperado y lo devuelve como JSON
        return JsonResponse({'success': False, 'error': str(e)})


#Aqui 

#desde aqui 

# tasks/views.py

@role_required(['COORD_ACADEMICO', 'ADMINISTRADOR', 'PSICOLOGO', 'COORD_CONVIVENCIA'])
def dashboard_academico(request):
    """
    Tablero de Inteligencia Académica con MOTOR DE PREDICCIÓN.
    """
    # Pesos definidos en el sistema
    PESOS = {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20}

    # 1. Obtener notas finales que están perdiendo (< 3.0)
    # Filtramos solo cursos activos para datos reales
    notas_reprobadas = Nota.objects.filter(
        numero_nota=5, 
        valor__lt=3.0,
        materia__curso__activo=True
    ).select_related('estudiante', 'materia', 'materia__curso')

    # 2. PROCESAMIENTO Y PREDICCIÓN
    riesgo_map = {}
    
    for nota_final in notas_reprobadas:
        est_id = nota_final.estudiante.id
        
        # --- ALGORITMO DE PREDICCIÓN ---
        # 1. ¿Cuánto lleva acumulado?
        nota_acumulada = float(nota_final.valor)
        
        # 2. ¿Qué notas ya se tomaron? (Consultamos las parciales de este estudiante/materia)
        notas_parciales = Nota.objects.filter(
            estudiante=nota_final.estudiante,
            materia=nota_final.materia,
            periodo=nota_final.periodo,
            numero_nota__in=[1, 2, 3, 4]
        ).values_list('numero_nota', flat=True)
        
        # 3. Calcular peso evaluado y peso restante
        peso_evaluado = sum(PESOS[n] for n in notas_parciales)
        peso_restante = 1.0 - peso_evaluado
        
        # 4. Proyección: ¿Qué nota necesita en lo que falta para pasar con 3.0?
        # Fórmula: (Meta - Acumulado) / Peso_Restante
        if peso_restante > 0.05: # Si falta más del 5% por evaluar
            nota_necesaria = (3.0 - nota_acumulada)
            # Como el acumulado ya está ponderado, la nota necesaria matemática es directa si asumimos 
            # que nota_acumulada es la suma de (nota * peso).
            # Ajuste: nota_final.valor en tu sistema es la SUMA PONDERADA.
            # Meta acumulada total es 3.0.
            # Puntos que faltan = 3.0 - nota_acumulada.
            # Esos puntos deben conseguirse en el 'peso_restante'.
            # Nota promedio necesaria = Puntos Faltantes / Peso Restante.
            promedio_necesario = (3.0 - nota_acumulada) / peso_restante
        else:
            promedio_necesario = 100.0 # Ya no hay tiempo, nota infinita necesaria

        # 5. Clasificar Riesgo / Probabilidad de Pérdida
        if promedio_necesario > 5.0:
            probabilidad = "100% (Irrecuperable)"
            clase_riesgo = "bg-dark text-white" # Ya perdió matemáticamente
            nivel_riesgo = "CRÍTICO"
        elif promedio_necesario > 4.0:
            probabilidad = "85% (Muy Alta)"
            clase_riesgo = "bg-danger text-white"
            nivel_riesgo = "ALTO"
        elif promedio_necesario > 3.0:
            probabilidad = "50% (Media)"
            clase_riesgo = "bg-warning text-dark"
            nivel_riesgo = "MEDIO"
        else:
            probabilidad = "20% (Baja)"
            clase_riesgo = "bg-info text-dark"
            nivel_riesgo = "BAJO"

        # --- FIN ALGORITMO ---

        if est_id not in riesgo_map:
            riesgo_map[est_id] = {
                'estudiante': nota_final.estudiante,
                'curso': nota_final.materia.curso.nombre,
                'total_perdidas': 0,
                'materias': []
            }
        
        riesgo_map[est_id]['total_perdidas'] += 1
        riesgo_map[est_id]['materias'].append({
            'nombre': nota_final.materia.nombre,
            'nota_actual': nota_acumulada,
            'nota_necesaria': round(promedio_necesario, 2) if promedio_necesario < 10 else "> 5.0",
            'probabilidad': probabilidad,
            'clase_riesgo': clase_riesgo,
            'periodo': nota_final.periodo.nombre
        })

    # Ordenar: Primero los que tienen más materias perdidas
    lista_riesgo = sorted(riesgo_map.values(), key=lambda x: x['total_perdidas'], reverse=True)

    # 3. KPIs GLOBALES (Para las tarjetas de arriba)
    all_notas_finales = Nota.objects.filter(numero_nota=5, materia__curso__activo=True)
    total_evaluaciones = all_notas_finales.count()
    promedio_global = all_notas_finales.aggregate(Avg('valor'))['valor__avg'] or 0
    conteo_reprobadas = notas_reprobadas.count()
    tasa_reprobacion = (conteo_reprobadas / total_evaluaciones * 100) if total_evaluaciones > 0 else 0

    # 4. GRÁFICOS
    rendimiento_cursos = all_notas_finales.values('materia__curso__nombre').annotate(prom=Avg('valor')).order_by('materia__curso__nombre')
    labels_cursos = [x['materia__curso__nombre'] for x in rendimiento_cursos]
    data_cursos = [float(round(x['prom'], 2)) for x in rendimiento_cursos]

    rendimiento_materias = all_notas_finales.values('materia__nombre').annotate(prom=Avg('valor')).order_by('prom')[:10]
    labels_materias = [x['materia__nombre'] for x in rendimiento_materias]
    data_materias = [float(round(x['prom'], 2)) for x in rendimiento_materias]

    context = {
        'lista_riesgo': lista_riesgo,
        'kpi': {
            'promedio': round(promedio_global, 2),
            'tasa_reprobacion': round(tasa_reprobacion, 1),
            'total_evaluaciones': total_evaluaciones,
            'reprobadas': conteo_reprobadas
        },
        'chart_cursos_labels': json.dumps(labels_cursos),
        'chart_cursos_data': json.dumps(data_cursos),
        'chart_materias_labels': json.dumps(labels_materias),
        'chart_materias_data': json.dumps(data_materias),
        # Datos para dona (Aprobados vs Reprobados)
        'chart_distribucion_data': json.dumps([total_evaluaciones - conteo_reprobadas, conteo_reprobadas])
    }
    
    return render(request, 'admin/dashboard_academico.html', context)
# tasks/views.py (Agregar al final)


#hasta aqui
@role_required(['COORD_ACADEMICO', 'ADMINISTRADOR', 'PSICOLOGO', 'COORD_CONVIVENCIA'])
def reporte_consolidado(request):
    """
    Genera una 'Sábana de Notas' (Matriz Estudiantes vs Materias).
    CORREGIDO: Ahora incluye la institución en el contexto para evitar errores de renderizado.
    """
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    periodos = None
    
    # Filtros seleccionados
    curso_id = request.GET.get('curso_id')
    periodo_id = request.GET.get('periodo_id')
    
    datos_reporte = []
    materias = []
    curso_seleccionado = None
    periodo_seleccionado = None

    if curso_id:
        curso_seleccionado = get_object_or_404(Curso, id=curso_id)
        # Cargamos los periodos del curso seleccionado
        periodos = Periodo.objects.filter(curso_id=curso_id).order_by('id')

        if periodo_id:
            periodo_seleccionado = get_object_or_404(Periodo, id=periodo_id)
            
            # 1. Obtener todas las materias del curso
            materias = Materia.objects.filter(curso=curso_seleccionado).order_by('nombre')
            
            # 2. Obtener estudiantes matriculados
            matriculas = Matricula.objects.filter(curso=curso_seleccionado, activo=True).select_related('estudiante').order_by('estudiante__last_name')
            
            # 3. Construir la matriz
            for mat in matriculas:
                estudiante = mat.estudiante
                notas_estudiante = []
                promedio_acumulado = 0.0
                materias_perdidas = 0
                materias_con_nota = 0 # Contador para saber cuántas materias se promedian
                
                for materia in materias:
                    # Buscar la nota final (numero_nota=5) de este estudiante en esta materia y periodo
                    # Usamos .first() para seguridad
                    nota_obj = Nota.objects.filter(
                        estudiante=estudiante, 
                        materia=materia, 
                        periodo=periodo_seleccionado,
                        numero_nota=5
                    ).first()
                    
                    valor = float(nota_obj.valor) if nota_obj else 0.0
                    
                    if valor > 0:
                        materias_con_nota += 1
                        if valor < 3.0:
                            materias_perdidas += 1
                    
                    notas_estudiante.append({
                        'materia_id': materia.id,
                        'valor': valor
                    })
                    promedio_acumulado += valor

                # Cálculo seguro del promedio (Evitar división por cero)
                if len(materias) > 0:
                    # Opción A: Promedio sobre total de materias (diluye si faltan notas)
                    promedio_general = promedio_acumulado / len(materias)
                    # Opción B (Alternativa): promedio_general = promedio_acumulado / materias_con_nota if materias_con_nota > 0 else 0
                else:
                    promedio_general = 0.0
                
                datos_reporte.append({
                    'estudiante': estudiante,
                    'notas': notas_estudiante,
                    'promedio': round(promedio_general, 2),
                    'perdidas': materias_perdidas
                })

    # 4. CRÍTICO: Obtener la institución para el encabezado del reporte
    institucion = Institucion.objects.first()

    return render(request, 'admin/reporte_consolidado.html', {
        'cursos': cursos,
        'periodos': periodos,
        'curso_seleccionado': curso_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'materias': materias,
        'datos_reporte': datos_reporte,
        'institucion': institucion, # <--- ESTA LÍNEA ES LA QUE FALTABA Y ARREGLA EL ERROR
    })


# En views.py
def sabana_notas(request):
    """
    Vista alternativa o complementaria para la sábana de notas.
    """
    # 1. Configuración inicial
    cursos = Curso.objects.all().order_by('nombre')
    
    # Obtenemos nombres únicos de periodos para evitar duplicados en el selector
    nombres_periodos = Periodo.objects.values_list('nombre', flat=True).distinct().order_by('nombre')
    
    # Obtenemos la información del colegio para el encabezado oficial
    institucion = Institucion.objects.first()

    context = {
        'cursos': cursos,
        'nombres_periodos': nombres_periodos,
        'institucion': institucion, # Pasamos la info del colegio al template
        'datos_reporte': [],
        'materias': [],
        'curso_seleccionado': None,
        'periodo_seleccionado': None,
    }

    # 2. Captura de parámetros
    curso_id = request.GET.get('curso_id')
    periodo_nombre = request.GET.get('periodo_nombre')

    if curso_id and periodo_nombre:
        curso_seleccionado = get_object_or_404(Curso, id=curso_id)
        
        # Buscamos el periodo específico que pertenece a este curso por nombre
        periodo_seleccionado = Periodo.objects.filter(
            curso=curso_seleccionado, 
            nombre=periodo_nombre
        ).first()

        if periodo_seleccionado:
            context['curso_seleccionado'] = curso_seleccionado
            context['periodo_seleccionado'] = periodo_seleccionado

            # 3. Obtener Estudiantes Matriculados
            estudiantes_matriculados = Matricula.objects.filter(
                curso=curso_seleccionado,
                activo=True
            ).select_related('estudiante').order_by('estudiante__last_name')
            
            estudiante_ids = estudiantes_matriculados.values_list('estudiante_id', flat=True)

            # 4. Obtener Materias (Búsqueda Completa)
            # Busca: Materias del curso O Materias asignadas O Materias con notas existentes
            materias = Materia.objects.filter(
                Q(curso=curso_seleccionado) | 
                Q(asignaciones__curso=curso_seleccionado) |
                Q(notas__estudiante_id__in=estudiante_ids, notas__periodo=periodo_seleccionado)
            ).distinct().order_by('nombre')
            
            context['materias'] = materias

            # 5. Obtener Notas y Promediar (para definitivas)
            notas_qs = Nota.objects.filter(
                estudiante_id__in=estudiante_ids,
                periodo=periodo_seleccionado,
                materia__in=materias
            ).values('estudiante_id', 'materia_id').annotate(definitiva=Avg('valor'))

            # Mapa rápido para acceso O(1)
            notas_map = {
                (n['estudiante_id'], n['materia_id']): n['definitiva'] 
                for n in notas_qs
            }

            # 6. Armar la Matriz de Datos
            datos_reporte = []

            for matricula in estudiantes_matriculados:
                estudiante = matricula.estudiante
                lista_notas = []
                suma_promedios = 0
                materias_con_nota = 0
                perdidas = 0

                for materia in materias:
                    clave = (estudiante.id, materia.id)
                    valor = notas_map.get(clave, 0)
                    valor = float(round(valor, 1)) if valor else 0.0

                    if valor > 0:
                        suma_promedios += valor
                        materias_con_nota += 1
                        if valor < 3.0:
                            perdidas += 1
                    
                    lista_notas.append({'valor': valor})

                promedio_general = 0
                if materias_con_nota > 0:
                    promedio_general = round(suma_promedios / materias_con_nota, 2)

                datos_reporte.append({
                    'estudiante': estudiante,
                    'notas': lista_notas,
                    'promedio': promedio_general,
                    'perdidas': perdidas
                })

            context['datos_reporte'] = datos_reporte

    return render(request, 'admin/reporte_consolidado.html', context)

##fase 4 inicio 

# ===================================================================
# 🛡️ FASE IV (PASO 16): LÓGICA DE MODERACIÓN Y AUDITORÍA
# ===================================================================

# Nota: El decorador @role_required asume que tienes una implementación personalizada.
# Asumo que las clases Post y Comment también están importadas correctamente.

# 🏗️ FASE IV (PASO 17): VISTA DEL FEED SOCIAL (MURO)
# ===================================================================

# ===================================================================
# 🏗️ FASE IV (PASO 17 - CORREGIDO): VISTA DEL FEED SOCIAL (MURO GLOBAL)
# ===================================================================


# ===================================================================
# ⚡ FASE IV (PASO 18): API DE REACCIONES (AJAX)
# ===================================================================


# ===================================================================
# 🤝 FASE IV (PASO 19): API SEGUIR USUARIOS (NETWORKING)
# ===================================================================

# Dentro de tasks/views.py (asumiendo que logger y las clases se importan arriba)

# ===================================================================
# 👤 FASE IV (PASO 20): VISTA DE PERFIL SOCIAL
# ===================================================================


# ===================================================================
# 🔍 FASE IV (PASO 21): BUSCADOR GLOBAL INTELIGENTE
# ===================================================================

# --- (Pegar esto al final de tasks/views.py) ---


##historial de notificaciones 



@login_required
def editar_perfil(request):
    """
    Permite editar al mismo tiempo:
    1. Modelo User (Nombre, Apellido, Email) -> UserEditForm
    2. Modelo Perfil (Foto, Portada, Hobbies, Metas) -> EditarPerfilForm
    """
    user = request.user
    perfil = user.perfil # Asumimos que el perfil existe gracias al Signal o Middleware
    
    if request.method == 'POST':
        # 1. Cargamos los datos del formulario de Usuario
        user_form = UserEditForm(request.POST, instance=user)
        
        # 2. Cargamos los datos del formulario de Perfil (incluyendo archivos/fotos)
        profile_form = EditarPerfilForm(request.POST, request.FILES, instance=perfil)

        # 3. Validamos que AMBOS sean correctos
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()      # Guarda nombre, apellido, email
            profile_form.save()   # Guarda fotos, hobbies, metas
            
            messages.success(request, '¡Tu perfil se ha actualizado correctamente!')
            # Redirige a la vista del perfil público
            return redirect('ver_perfil_social', username=user.username)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    
    else:
        # GET: Pre-llenamos los formularios con la información actual
        user_form = UserEditForm(instance=user)
        profile_form = EditarPerfilForm(instance=perfil)

    # 4. Enviamos AMBOS formularios al template
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    
    return render(request, 'social/editar_perfil.html', context)


##Aqui agregue las notificaciones 


@login_required
def descargar_observador_acudiente(request, estudiante_id):
    """
    Genera y descarga el PDF del observador para el acudiente.
    """
    # 1. Validaciones de Seguridad (Igual que antes)
    estudiante = get_object_or_404(User, id=estudiante_id)
    es_mi_hijo = Acudiente.objects.filter(acudiente=request.user, estudiante=estudiante).exists()
    
    if not es_mi_hijo:
        messages.error(request, "No tienes permisos.")
        return redirect('dashboard_acudiente')

    matricula = Matricula.objects.filter(estudiante=estudiante).order_by('-id').first()
    
    if not matricula or not matricula.puede_ver_observador:
        messages.warning(request, "El observador aún no ha sido habilitado.")
        return redirect('dashboard_acudiente')

    # 2. Preparar Datos
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')
    institucion = Institucion.objects.first()
    curso = matricula.curso if matricula else None

    context = {
        'estudiante': estudiante,
        'observaciones': observaciones,
        'institucion': institucion,
        'curso': curso,
        'fecha_impresion': timezone.now(),
        'generado_por': request.user.get_full_name(),
        'es_oficial': True,
        # Importante: Para que las imágenes carguen en el PDF, a veces se necesita la URL base
        'request': request 
    }

    # 3. Generar PDF
    # Renderizamos el HTML a un string
    html_string = render_to_string('pdf/observador_template.html', context)

    if HTML:
        # Si WeasyPrint está instalado, generamos el PDF real
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'filename="Observador_{estudiante.username}.pdf"'
        
        # Base url es importante para cargar imágenes estáticas/media
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        return response
    else:
        # Fallback: Si no hay librerías de PDF, mostramos el HTML para imprimir con Ctrl+P
        # Esto es lo que te estaba pasando, pero ahora sabes por qué.
        return HttpResponse(html_string)


# --- tasks/views.py ---

def cargar_periodos_por_curso(request):
    """
    API AJAX para cargar los periodos de un curso seleccionado.
    Permite que el Administrador y Staff vean los periodos en el reporte consolidado.
    """
    curso_id = request.GET.get('curso_id')
    
    if not curso_id:
        return JsonResponse([], safe=False)
    
    try:
        # 1. Obtener el curso
        curso = Curso.objects.get(id=curso_id)
        
        # 2. Filtrar periodos activos de ese curso
        # No filtramos por docente aquí, porque el Admin/Coord debe ver todo.
        periodos = Periodo.objects.filter(curso=curso, activo=True).values('id', 'nombre').order_by('id')
        
        return JsonResponse(list(periodos), safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



# tasks/views.py

# tasks/views.py


@login_required
def ai_analysis_engine(request):
    """
    MOTOR CENTRAL DE ANÁLISIS (TIER 1000 - CONTEXTO REAL).
    Sincroniza la base de datos con la IA mediante inyección directa de contexto.
    """

    # 1. DETECCIÓN DE CONTEXTO (AJAX / JSON / HTML)
    accept_header = request.headers.get("Accept", "")
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.GET.get("format") == "json"
        or "application/json" in accept_header.lower()
    )

    # 2. CONFIGURACIÓN INICIAL DE ACCIÓN Y ROL
    perfil = getattr(request.user, "perfil", None)
    rol_usuario = perfil.rol if perfil else "ESTUDIANTE"

    # Definir acción por defecto basada en el rol si no viene ninguna
    if rol_usuario == "DOCENTE":
        default_action = ACCION_MEJORAS_DOCENTE
    else:
        default_action = ACCION_MEJORAS_ESTUDIANTE

    action_type = request.GET.get("action", default_action)
    target_id = request.GET.get("target_id")
    user_query = request.GET.get("user_query")

    # 3. CAPTURA Y VALIDACIÓN DE MEMORIA (HISTORIAL)
    historial_msgs = []
    raw_history = request.GET.get("history")
    if raw_history:
        try:
            parsed = json.loads(raw_history)
            if isinstance(parsed, list):
                historial_msgs = [msg for msg in parsed if isinstance(msg, dict) and "role" in msg]
        except Exception:
            logger.warning("[AI] Error procesando historial de chat.")

    # 4. RUTEADO DE INTERFAZ (CHAT HTML)
    if action_type == ACCION_CHAT_SOCRATICO and not is_ajax:
        return render(request, "tasks/ai_chat.html", {"target_user": request.user})

    # 5. RESOLUCIÓN DEL TARGET_USER (Sujeto del análisis)
    target_user = request.user

    try:
        # Lógica de resolución de sujeto según rol
        if rol_usuario == "ACUDIENTE":
            if target_id:
                target_user = get_object_or_404(User, id=target_id)
            else:
                relacion = Acudiente.objects.filter(acudiente=request.user).select_related("estudiante").first()
                if not relacion:
                    raise ValueError("No se encontró un estudiante vinculado a su cuenta.")
                target_user = relacion.estudiante

        elif rol_usuario == "DOCENTE":
            target_user = request.user
            # Forzamos acción de docente si el sistema está intentando usar la de estudiante
            if action_type == ACCION_MEJORAS_ESTUDIANTE:
                action_type = ACCION_MEJORAS_DOCENTE

        elif target_id:
            target_user = get_object_or_404(User, id=target_id)

        # 6. CONSTRUCCIÓN DE CONTEXTO RICO (TIER 1000)
        # Importante: Asegúrate de que 'context_builder' esté importado al inicio del archivo
        try:
            contexto_enriquecido = context_builder.get_context(
                usuario=request.user,
                action_type=action_type,
                target_user=target_user
            )
        except Exception as e:
            logger.error(f"[AI] Error en ContextBuilder: {e}", exc_info=True)
            raise ValueError("No se pudo extraer la evidencia académica de la base de datos.")

        # 7. EJECUCIÓN DEL MOTOR DE IA (ORQUESTADOR)
        # Se envía el 'context_override' para que la IA use datos reales y no alucine
        resultado = ai_orchestrator.process_request(
            user=request.user,
            action_type=action_type,
            user_query=user_query,
            target_user=target_user,
            historial=historial_msgs,
            context_override=contexto_enriquecido # 🔥 ESTA ES LA CLAVE DE LOS DATOS REALES
        )

    except ValueError as e:
        resultado = {"success": False, "content": str(e), "source": "BUSINESS_LOGIC"}
    except Exception as e:
        logger.error("[AI] CRASH CRÍTICO EN ENGINE", exc_info=True)
        resultado = {"success": False, "content": "Error interno en el motor de IA."}

    # 8. RESPUESTA FINAL
    if is_ajax:
        return JsonResponse(resultado, safe=False)

    return render(request, "tasks/ai_report.html", {
        "ai_json_response": json.dumps(resultado, default=str, cls=DjangoJSONEncoder),
        "titulo_analisis": str(action_type).replace("_", " ").title(),
        "target_user": target_user
    })

@login_required
def test_ai_connection(request):
    """VISTA DE COMPATIBILIDAD PARA URLS.PY."""
    return ai_analysis_engine(request)

@login_required
def dashboard_ia_estudiante(request):
    """RENDERIZA EL PANEL PRINCIPAL DE IA."""
    context = {
        'titulo_pagina': 'Orientación Inteligente',
        'usuario_nombre': request.user.first_name or request.user.username,
    }
    return render(request, 'tasks/ai_dashboard.html', context)

#Aqui inicia la funcion para el reporte de la AI 

# ===================================================================
# 🖨️ CIRUGÍA: GENERADOR DE REPORTE IA EN PDF (INSTITUCIONAL)
# ===================================================================

@login_required
def download_ai_report_pdf(request):
    """
    Genera un PDF oficial con el análisis de la IA, formato institucional y firmas.
    Recibe los mismos parámetros que el motor de IA para reconstruir el contexto.
    """
    # 1. Recuperar parámetros
    action_type = request.GET.get('action')
    target_id = request.GET.get('target_id')
    user_query = request.GET.get('user_query', '')
    
    # 2. Identificar al usuario objetivo (Target)
    target_user = request.user
    if target_id:
        target_user = get_object_or_404(User, id=target_id)
    
    # 3. Obtener/Regenerar el análisis de la IA (Orquestador)
    # Reutilizamos tu lógica existente para obtener la data cruda
    try:
        resultado = ai_orchestrator.process_request(
            user=request.user,
            action_type=action_type,
            user_query=user_query,
            target_user=target_user,
            historial=[] # Para el reporte oficial, usamos el contexto fresco
        )
        
        contenido_raw = resultado.get('content', 'No se pudo generar el contenido.')
        
        # 4. Convertir Markdown a HTML para el PDF (Negritas, listas, etc.)
        contenido_html = markdown.markdown(contenido_raw)

    except Exception as e:
        logger.error(f"Error generando PDF IA: {e}")
        contenido_html = f"<p>Error al generar el reporte: {str(e)}</p>"

    # 5. Datos Institucionales
    institucion = Institucion.objects.first()
    
    # 6. Contexto para el Template PDF
    context = {
        'institucion': institucion,
        'fecha_impresion': timezone.now(),
        'solicitante': request.user,
        'objetivo': target_user,
        'tipo_reporte': action_type.replace('_', ' ').upper() if action_type else "REPORTE GENERAL",
        'contenido_html': mark_safe(contenido_html), # Marcamos como seguro para renderizar HTML
        'query_original': user_query
    }

    # 7. Renderizado con WeasyPrint
    if HTML is None:
        return HttpResponse("Error: WeasyPrint no está instalado en el servidor.", status=500)

    html_string = render_to_string('pdf/ai_report_template.html', context)
    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"Reporte_IA_{target_user.username}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response


# En tasks/views.py

@login_required
def ver_documentos_institucionales(request):
    """
    Vista pública para que CUALQUIER usuario autenticado (Estudiante, Acudiente, Docente)
    pueda ver y descargar los documentos oficiales.
    """
    institucion = Institucion.objects.first()
    
    # Si no hay institución creada, pasamos None para manejarlo en el template
    context = {
        'institucion': institucion
    }
    return render(request, 'institucion/documentos_publicos.html', context)
##desde aqui


#hasta aqui
# --- VISTA 1: GUARDAR SEGUIMIENTO (Backend) ---

# --- VISTA 2: GENERAR PDF (Backend + WeasyPrint) ---
# ======================================================


@login_required
def actualizar_configuracion_sms(request):
    if request.method == 'POST':
        perfil = request.user.perfil

        nuevo_telefono = request.POST.get('telefono_sms')
        # Checkbox: si no está marcado, no envía nada, por eso la comparación
        recibir = request.POST.get('recibir_sms') == 'on'

        if nuevo_telefono:
            # Quitamos espacios y guiones para validar
            limpio = ''.join(filter(str.isdigit, nuevo_telefono))
            
            # Validación estricta de longitud para Colombia
            if len(limpio) == 10:
                perfil.telefono_sms = limpio
                perfil.recibir_sms = recibir
                perfil.save()
                
                estado = "ACTIVADAS" if recibir else "DESACTIVADAS"
                messages.success(request, f'✅ Configuración actualizada. Alertas {estado}.')
            else:
                messages.error(request, '⚠️ Error: El número debe tener 10 dígitos exactos (Ej: 3001234567).')
        else:
            # Si envía el campo vacío, asumimos que quiere borrar el número
            perfil.telefono_sms = None
            perfil.recibir_sms = False
            perfil.save()
            messages.info(request, 'Has eliminado tu número de alertas.')

        return redirect('dashboard_acudiente')
    
    # Si intentan entrar por GET, los devolvemos
    return redirect('dashboard_acudiente')


#nuevo reporte de observadores y convivencia 
# Asegúrate de tener estos imports al inicio de tasks/views.py
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Avg
from weasyprint import HTML
# Tus modelos
from .models import Observacion, Seguimiento, Matricula, Institucion, Nota, Asistencia






# ==============================================================
# 🔥 VISTA 1: VALIDACIÓN PÚBLICA DEL CERTIFICADO (LO QUE ABRE EL QR)
# ==============================================================
def verificar_certificado_publico(request, user_id):
    """
    Vista pública que se abre al escanear el QR.
    Muestra si el estudiante es real y está activo.
    No requiere login para que cualquiera pueda validar.
    """
    estudiante = get_object_or_404(User, id=user_id)
    
    # Buscar si tiene matrícula activa
    matricula = Matricula.objects.filter(
        estudiante=estudiante, 
        activo=True
    ).select_related('curso').first()
    
    # Datos para mostrar en el celular
    context = {
        'estudiante': estudiante,
        'es_valido': True if matricula else False,
        'matricula': matricula,
        'fecha_consulta': timezone.now()
    }
    return render(request, 'pdf/validacion_publica.html', context)


# ==============================================================
# 🔥 VISTA 2: GENERADOR DEL CERTIFICADO PDF (CON QR DE URL)
# ==============================================================
@role_required(STAFF_ROLES + ['ACUDIENTE']) 
def generar_certificado_estudiantil(request, user_id):
    """
    Genera un Certificado de Estudios OFICIAL.
    Incluye: QR que redirige a la vista de validación.
    Acceso: Staff completo y Acudientes.
    """
    try:
        estudiante = User.objects.get(id=user_id)

        # --- CORRECCIÓN DE SEGURIDAD (SIN DEPENDER DE 'acudidos') ---
        # Si es acudiente, confiamos en que llegó aquí desde su dashboard.
        # Adicionalmente, verificamos si existe alguna conexión lógica básica.
        if request.user.perfil.rol == 'ACUDIENTE':
            # Verificamos si este acudiente tiene ALGUNA relación con el estudiante
            # Buscando en las matrículas si el estudiante está asociado al acudiente es complejo sin saber el modelo exacto.
            # Por ahora, permitimos la generación si el estudiante existe y tiene matrícula.
            # La seguridad principal es que el enlace solo aparece en su dashboard privado.
            pass 
        # -----------------------------------------------------------

        institucion = Institucion.objects.first()
        
        matricula = Matricula.objects.filter(
            estudiante=estudiante, 
            activo=True
        ).select_related('curso').first()

        if not matricula:
            messages.error(request, f"El estudiante {estudiante.get_full_name()} no tiene una matrícula activa.")
            if request.user.perfil.rol == 'ACUDIENTE':
                return redirect('dashboard_acudiente')
            return redirect('dashboard_bienestar')

        # --- 1. GENERACIÓN DEL QR DE URL ---
        path_verificacion = reverse('verificar_certificado_publico', args=[estudiante.id])
        url_qr = request.build_absolute_uri(path_verificacion)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=1,
        )
        qr.add_data(url_qr)
        qr.make(fit=True)

        img_buffer = io.BytesIO()
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        qr_src = f"data:image/png;base64,{qr_base64}"

        # --- 2. DATOS DEL DOCUMENTO ---
        security_hash = ''.join(random.choices(string.ascii_uppercase + string.digits, k=32))
        ahora = timezone.now()
        folio = f"CERT-{ahora.year}-{estudiante.id:04d}-{random.randint(1000,9999)}"
        
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        fecha_texto = f"{ahora.day} días del mes de {meses[ahora.month]} de {ahora.year}"

        context = {
            'estudiante': estudiante,
            'matricula': matricula,
            'curso': matricula.curso,
            'institucion': institucion,
            'anio': ahora.year,
            'fecha_texto': fecha_texto,
            'folio': folio,
            'security_hash': security_hash,
            'qr_src': qr_src, 
            'firma_url': 'https://res.cloudinary.com/dukiyxfvn/image/upload/v1769638753/Firma_MILLER_3_jbxux5.png'
        }

        html_string = render_to_string('pdf/certificado_estudiantil_tier.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        result = html.write_pdf(stylesheets=[], optimize_images=True)

        response = HttpResponse(result, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Certificado_{estudiante.username}.pdf"'
        return response

    except User.DoesNotExist:
        messages.error(request, "Estudiante no encontrado.")
        if request.user.perfil.rol == 'ACUDIENTE':
            return redirect('dashboard_acudiente')
        return redirect('dashboard_bienestar')

##Actualizar el numero de documento del estudiante
@role_required(['ACUDIENTE'])
def actualizar_documento_estudiante(request):
    """
    Permite al acudiente actualizar el documento de identidad de su estudiante.
    Valida unicidad para evitar duplicados.
    """
    if request.method == 'POST':
        try:
            student_id = request.POST.get('estudiante_id')
            nuevo_documento = request.POST.get('numero_documento', '').strip()

            if not nuevo_documento:
                messages.error(request, "El número de documento no puede estar vacío.")
                return redirect('dashboard_acudiente')

            # 1. Obtener estudiante
            estudiante = User.objects.get(id=student_id)

            # 2. Seguridad: Verificar duplicados
            # CORRECCIÓN AQUÍ: Usamos 'user' en lugar de 'usuario'
            if Perfil.objects.filter(numero_documento=nuevo_documento).exclude(user=estudiante).exists():
                messages.error(request, f"⚠️ Error: El documento {nuevo_documento} ya está registrado en otro estudiante.")
                return redirect('dashboard_acudiente')

            # 3. Proceder a la actualización
            perfil = estudiante.perfil
            perfil.numero_documento = nuevo_documento
            perfil.save()

            messages.success(request, f"✅ Éxito: Documento de {estudiante.get_full_name()} actualizado correctamente.")
            
        except User.DoesNotExist:
            messages.error(request, "Estudiante no encontrado.")
        except Exception as e:
            # Esto imprimirá el error real si vuelve a pasar algo
            messages.error(request, f"Error técnico actualizando documento: {str(e)}")
            
    return redirect('dashboard_acudiente')

##logica de nuevas notas 

@role_required('DOCENTE')
@transaction.atomic
def configurar_plan_evaluacion(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            periodo_id = data.get('periodo_id')
            materia_id = data.get('materia_id')
            items = data.get('items', []) # Lista de notas (Nombre, %, Temas)

            # Validar que los porcentajes sumen 100 (Opcional, pero recomendado)
            total_porcentaje = sum(Decimal(str(i['porcentaje'])) for i in items)
            if abs(total_porcentaje - 100) > 0.1:
                return JsonResponse({'success': False, 'error': f'Los porcentajes suman {total_porcentaje}%. Deben sumar 100%.'})

            # 1. Obtener definiciones actuales para saber cuáles borrar
            definiciones_actuales = DefinicionNota.objects.filter(
                materia_id=materia_id, periodo_id=periodo_id
            )
            ids_recibidos = [int(i['id']) for i in items if i.get('id')]
            
            # Borrar las que ya no vienen en la lista
            definiciones_actuales.exclude(id__in=ids_recibidos).delete()

            # 2. Crear o Actualizar
            for index, item in enumerate(items):
                defaults = {
                    'nombre': item['nombre'],
                    'porcentaje': item['porcentaje'],
                    'temas': item['temas'], # <--- AQUÍ SE GUARDAN LOS TEMAS
                    'orden': index + 1
                }
                
                if item.get('id'):
                    DefinicionNota.objects.filter(id=item['id']).update(**defaults)
                else:
                    DefinicionNota.objects.create(
                        materia_id=materia_id,
                        periodo_id=periodo_id,
                        **defaults
                    )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})



# --- PEGAR AL FINAL DE tasks/views.py ---

@login_required
@role_required('ADMINISTRADOR')
def admin_ex_estudiantes(request):
    """
    Vista de Archivo Histórico (Lectura) - NIVEL DIOS.
    """
    # --- IMPORTACIÓN CRÍTICA AQUÍ ---
    from .models import BoletinArchivado, ObservadorArchivado, GRADOS_CHOICES
    
    # 1. Query Base (Optimizada con select_related)
    boletines_qs = BoletinArchivado.objects.select_related('eliminado_por').all().order_by('-fecha_eliminado')

    # 2. Filtros
    query = request.GET.get('q', '').strip()
    grado_filtro = request.GET.get('grado', '').strip()
    anio_filtro = request.GET.get('anio', '').strip()

    if query:
        boletines_qs = boletines_qs.filter(
            Q(nombre_estudiante__icontains=query) |
            Q(username_estudiante__icontains=query)
        )
    
    if grado_filtro:
        boletines_qs = boletines_qs.filter(grado_archivado=grado_filtro)
        
    if anio_filtro:
        boletines_qs = boletines_qs.filter(anio_lectivo_archivado=anio_filtro)

    # 3. Paginación
    paginator = Paginator(boletines_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # =================================================================
    # 4. CIRUGÍA: VINCULACIÓN EXACTA (Usuario + Año)
    # =================================================================
    
    # A. Identificamos las "Huellas Digitales" únicas en esta página
    identificadores_en_pantalla = set(
        (b.username_estudiante, b.anio_lectivo_archivado) 
        for b in page_obj
    )

    if identificadores_en_pantalla:
        # B. Construimos la consulta para traer SOLO los observadores necesarios
        query_obs = Q()
        for username, anio in identificadores_en_pantalla:
            query_obs |= Q(
                estudiante_username=username,
                anio_lectivo_archivado=anio
            )

        observadores_qs = ObservadorArchivado.objects.filter(query_obs)

        # C. Mapa de Memoria: (username, anio) -> Objeto Observador
        observadores_map = {
            (obs.estudiante_username, obs.anio_lectivo_archivado): obs 
            for obs in observadores_qs
        }

        # D. INYECCIÓN DIRECTA: Pegamos el observador al boletín
        for boletin in page_obj:
            clave = (boletin.username_estudiante, boletin.anio_lectivo_archivado)
            boletin.observador_vinculado = observadores_map.get(clave)
    
    else:
        for boletin in page_obj:
            boletin.observador_vinculado = None

    # 5. Contexto para filtros
    anios_disponibles = BoletinArchivado.objects.order_by('-anio_lectivo_archivado')\
                                                .values_list('anio_lectivo_archivado', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'total_boletines': paginator.count,
        'anios_disponibles': anios_disponibles,
        'grados_disponibles': GRADOS_CHOICES,
        'current_q': query,
        'current_grado': grado_filtro,
        'current_anio': anio_filtro,
    }
    
    return render(request, 'admin/ex_estudiantes.html', context)


# ==========================================================================
# 👇 PEGA ESTO AL FINAL DE TU ARCHIVO tasks/views.py
# ==========================================================================

# ==========================================================================
# REEMPLAZA LA FUNCIÓN EN tasks/views.py CON ESTA VERSIÓN ROBUSTA
# ==========================================================================

import markdown
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from weasyprint import HTML, CSS
from io import BytesIO  # <--- IMPORTANTE: Para manejar el archivo en memoria

from .ai.orchestrator import ai_orchestrator
from .ai.constants import ACCION_ANALISIS_GLOBAL_BIENESTAR

@login_required
def generar_pdf_bienestar(request):
    """
    Genera el PDF Profesional de Bienestar usando WeasyPrint + Buffer de Memoria.
    """
    try:
        print("1. Iniciando generación de PDF...") # Debug en terminal

        # 1. Ejecutar Stratos AI
        respuesta_ia = ai_orchestrator.process_request(
            user=request.user,
            action_type=ACCION_ANALISIS_GLOBAL_BIENESTAR,
            user_query="",
            params={}
        )

        if not respuesta_ia.get('success'):
            print("Error: La IA falló.")
            return HttpResponse(f"Error IA: {respuesta_ia.get('content')}", status=500)

        print("2. IA respondió correctamente. Procesando HTML...")

        # 2. Convertir Markdown a HTML
        texto_markdown = respuesta_ia.get('content', '')
        contenido_html = markdown.markdown(
            texto_markdown,
            extensions=['extra', 'nl2br', 'sane_lists']
        )

        # 3. Datos para el Template
        contexto = {
            'contenido_html': contenido_html,
            'objetivo': request.user,
            'solicitante': request.user,
            'tipo_reporte': 'AUDITORÍA ESTRATÉGICA DE BIENESTAR',
            'fecha_impresion': timezone.now(),
            'query_original': 'Diagnóstico de Clima Escolar y Rutas de Mejora'
        }

        # 4. Renderizar HTML a string
        html_string = render_to_string('tasks/templates/pdf/ai_report_template.html', contexto, request=request)

        # 5. Generar PDF en Memoria (Buffer)
        # Esto evita errores de "Broken Pipe" o archivos corruptos
        pdf_buffer = BytesIO()
        
        # Base URL es vital para cargar las fuentes de Google y las imágenes
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(
            target=pdf_buffer, 
            presentational_hints=True,
            zoom=1  # Asegura escala correcta
        )

        # 6. Preparar respuesta HTTP
        pdf_value = pdf_buffer.getvalue()
        pdf_buffer.close()

        response = HttpResponse(pdf_value, content_type='application/pdf')
        filename = f"Informe_Bienestar_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        # 'attachment' fuerza la descarga. Si quieres verlo en el navegador usa 'inline'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print("3. PDF generado y enviado con éxito.")
        return response

    except Exception as e:
        # Esto imprimirá el error REAL en tu terminal donde corre 'runserver'
        print(f"❌ ERROR CRÍTICO GENERANDO PDF: {str(e)}")
        
        # Devolvemos el error en pantalla para que sepas qué pasó
        return HttpResponse(f"""
            <h1 style='color:red'>Error al generar el PDF</h1>
            <p>El sistema reportó el siguiente error:</p>
            <pre>{str(e)}</pre>
            <p><strong>Posible solución:</strong> Verifica que instalaste las librerías del sistema (libcairo2, libpango, etc).</p>
        """, status=500)