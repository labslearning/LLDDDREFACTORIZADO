# apps/academics/views.py
import json
import csv
import io
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.files.base import ContentFile

# ---------------------------------------------------------
# 🏗️ IMPORTACIONES DE CAPA DE DOMINIO Y TENANCY
# ---------------------------------------------------------
from apps.tenancy.utils import get_current_tenant
from tasks.decorators import role_required
from tasks.utils import generar_username_unico, notificar_acudientes

# Modelos Locales (Academics)
from .models import (
    Curso, Materia, AsignacionMateria, Matricula, 
    Periodo, Nota, NotaDetallada, DefinicionNota, 
    BoletinArchivado, GRADOS_CHOICES
)
# Modelos Externos (Tasks/Globales)
from tasks.models import Perfil, Acudiente

# Formularios
from .forms import (
    BulkCSVForm, DocenteCreationForm, AsignacionMateriaForm, 
    MatriculaForm
)

# Servicios
from .services.academic_logic import (
    obtener_grados_por_nivel, obtener_anio_escolar_actual, 
    normalizar_grado, obtener_o_crear_curso_con_cupo,
    _curso_esta_completo, _capacidad_curso, _secciones_disponibles
)

# Configuración
logger = logging.getLogger(__name__)
DEFAULT_TEMP_PASSWORD = getattr(settings, 'DEFAULT_TEMP_PASSWORD', '123456')
PESOS_NOTAS_DEFAULT = {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20} # Fallback

# ==========================================================
# 📊 DASHBOARD ACADÉMICO (CON MOTOR DE PREDICCIÓN)
# ==========================================================
@role_required('ADMINISTRADOR')
def dashboard_academico(request):
    """
    Tablero de Inteligencia Académica con MOTOR DE PREDICCIÓN.
    Recuperado del Legacy y adaptado a Multi-Tenant.
    """
    tenant = get_current_tenant()
    
    # 1. KPIs GLOBALES
    estudiantes_activos = Perfil.objects.filter(tenant=tenant, rol='ESTUDIANTE', user__is_active=True).count()
    docentes_activos = Perfil.objects.filter(tenant=tenant, rol='DOCENTE', user__is_active=True).count()
    
    # 2. MOTOR DE RIESGO
    notas_reprobadas = Nota.objects.filter(
        tenant=tenant,
        numero_nota=5, 
        valor__lt=3.0,
        materia__curso__activo=True
    ).select_related('estudiante', 'materia', 'materia__curso')

    riesgo_map = {}
    for nota in notas_reprobadas:
        est_id = nota.estudiante.id
        if est_id not in riesgo_map:
            riesgo_map[est_id] = {
                'estudiante': nota.estudiante,
                'curso': nota.materia.curso.nombre,
                'total_perdidas': 0,
                'materias': []
            }
        
        riesgo_map[est_id]['total_perdidas'] += 1
        riesgo_map[est_id]['materias'].append({
            'nombre': nota.materia.nombre,
            'nota_actual': float(nota.valor),
            'periodo': nota.periodo.nombre
        })

    # Top 10 Estudiantes en Riesgo
    lista_riesgo = sorted(riesgo_map.values(), key=lambda x: x['total_perdidas'], reverse=True)[:10]

    # 3. ESTADÍSTICAS DE RENDIMIENTO
    all_notas = Nota.objects.filter(tenant=tenant, numero_nota=5, materia__curso__activo=True)
    promedio_global = all_notas.aggregate(Avg('valor'))['valor__avg'] or 0.0

    context = {
        'kpi': {
            'total_estudiantes': estudiantes_activos,
            'total_docentes': docentes_activos,
            'promedio_global': round(promedio_global, 2),
            'reprobadas_count': notas_reprobadas.count()
        },
        'lista_riesgo': lista_riesgo,
        'niveles': obtener_grados_por_nivel(),
        'cursos': Curso.objects.filter(tenant=tenant, activo=True).order_by('grado', 'seccion')
    }
    return render(request, 'academics/dashboard_academico.html', context)

@role_required('ADMINISTRADOR')
def gestion_academica(request):
    """Acceso rápido a las herramientas de gestión académica."""
    context = {
        'grados': GRADOS_CHOICES,
        'anio_escolar': obtener_anio_escolar_actual(),
        'secciones': _secciones_disponibles()
    }
    return render(request, 'academics/gestion_academica.html', context)

# ==========================================================
# 🏫 GESTIÓN DE PERSONAL (DOCENTES) Y PERIODOS
# ==========================================================
@role_required('ADMINISTRADOR')
@transaction.atomic
def registrar_docente(request):
    tenant = get_current_tenant()
    if request.method == 'POST':
        form = DocenteCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                if not user.username:
                    user.username = generar_username_unico(user.first_name, user.last_name)
                user.set_password(DEFAULT_TEMP_PASSWORD)
                user.save()

                Perfil.objects.create(
                    user=user, tenant=tenant, rol='DOCENTE',
                    telefono_sms=form.cleaned_data.get('telefono', ''),
                    numero_documento=form.cleaned_data.get('numero_documento', ''),
                    requiere_cambio_clave=True
                )
                messages.success(request, f"Docente {user.username} creado correctamente.")
                return redirect('academics:gestion_staff')
            except Exception as e:
                messages.error(request, f"Error: {e}")
    else:
        form = DocenteCreationForm()
    return render(request, 'academics/registro_docente.html', {'form': form})

@role_required('ADMINISTRADOR')
def gestion_staff(request):
    tenant = get_current_tenant()
    docentes = Perfil.objects.filter(rol='DOCENTE', tenant=tenant).select_related('user')
    return render(request, 'academics/gestion_staff.html', {'docentes': docentes})

@role_required('ADMINISTRADOR')
def gestionar_periodos(request):
    """Gestión de periodos académicos por colegio."""
    tenant = get_current_tenant()
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        with transaction.atomic():
            Periodo.objects.filter(tenant=tenant).update(activo=False)
            Periodo.objects.create(
                nombre=nombre, 
                activo=True, 
                tenant=tenant,
                fecha_inicio=timezone.now().date()
            )
        messages.success(request, f"Periodo '{nombre}' activado exitosamente.")
        return redirect('academics:gestionar_periodos')
    
    periodos = Periodo.objects.filter(tenant=tenant).order_by('-fecha_inicio')
    return render(request, 'academics/periodos.html', {'periodos': periodos})

# ==========================================================
# 🏫 GESTIÓN DE CURSOS Y ASIGNACIONES
# ==========================================================
@role_required('ADMINISTRADOR')
def gestionar_cursos(request):
    """Crea y visualiza los cursos por nivel educativo."""
    tenant = get_current_tenant()
    if request.method == 'POST' and 'crear_curso' in request.POST:
        grado = request.POST.get('grado')
        seccion = request.POST.get('seccion', '').upper()
        anio = request.POST.get('anio_escolar') or obtener_anio_escolar_actual()
        try:
            Curso.objects.create(grado=grado, seccion=seccion, anio_escolar=anio, tenant=tenant)
            messages.success(request, f"Curso creado exitosamente.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('academics:gestionar_cursos')

    context = {
        'grados': GRADOS_CHOICES,
        'cursos_por_nivel': {
            'primaria': Curso.objects.filter(tenant=tenant, grado__in=['1','2','3','4','5']),
            'bachillerato': Curso.objects.filter(tenant=tenant, grado__in=['6','7','8','9','10','11']),
        }
    }
    return render(request, 'academics/gestionar_cursos.html', context)

@role_required('ADMINISTRADOR')
def asignar_materia_docente(request):
    """Vincula docentes a materias y cursos."""
    tenant = get_current_tenant()
    if request.method == 'POST' and 'asignar_docente' in request.POST:
        form = AsignacionMateriaForm(request.POST)
        if form.is_valid():
            asig = form.save(commit=False)
            asig.tenant = tenant
            asig.save()
            messages.success(request, "Asignación realizada.")
            return redirect('academics:asignar_materia_docente')
    
    context = {
        'form': AsignacionMateriaForm(),
        'asignaciones': AsignacionMateria.objects.filter(tenant=tenant).select_related('docente', 'materia', 'curso')
    }
    return render(request, 'academics/asignar_materia_docente.html', context)

# ==========================================================
# 🎓 REGISTRO MASIVO Y MATRÍCULAS
# ==========================================================
@role_required('ADMINISTRADOR')
def asignar_curso_estudiante(request):
    """Matricula individual de estudiantes."""
    tenant = get_current_tenant()
    if request.method == 'POST':
        form = MatriculaForm(request.POST)
        if form.is_valid():
            mat = form.save(commit=False)
            mat.tenant = tenant
            mat.save()
            messages.success(request, "Estudiante matriculado.")
            return redirect('academics:asignar_curso_estudiante')
    return render(request, 'academics/asignar_curso_estudiante.html', {'form': MatriculaForm()})

@role_required('ADMINISTRADOR')
def registrar_alumnos_masivo_form(request):
    if request.method == 'GET':
        form = BulkCSVForm()
        return render(request, 'academics/registrar_alumnos.html', {'form': form})
    return redirect('academics:gestion_academica')

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def registrar_alumnos_masivo(request):
    """Procesa el CSV con lógica Tenant-Aware y Transaccional."""
    tenant = get_current_tenant()
    form = BulkCSVForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Formulario inválido.")
        return redirect('academics:registrar_alumnos_masivo_form')

    archivo_csv = form.cleaned_data['archivo_csv']
    anio_escolar = form.cleaned_data['anio_escolar'] or obtener_anio_escolar_actual()
    creados_est, matriculados = 0, 0
    errores = []

    try:
        decoded_file = archivo_csv.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded_file))
        reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames or []]
        
        for i, row in enumerate(reader, start=2):
            try:
                with transaction.atomic():
                    email = (row.get('email') or "").strip().lower()
                    first = (row.get('first_name') or "").strip().title()
                    last = (row.get('last_name') or "").strip().title()
                    grado_raw = (row.get('grado') or "").strip()
                    doc_id = (row.get('documento') or "").strip()

                    if not all([first, last, grado_raw]):
                        raise ValueError("Faltan nombre, apellido o grado.")

                    username = generar_username_unico(first, last)
                    user, created = User.objects.get_or_create(
                        email=email if email else None,
                        defaults={'username': username, 'first_name': first, 'last_name': last}
                    )
                    
                    if created:
                        user.set_password(DEFAULT_TEMP_PASSWORD)
                        user.save()
                        creados_est += 1

                    Perfil.objects.update_or_create(
                        user=user,
                        defaults={
                            'tenant': tenant, 'rol': 'ESTUDIANTE',
                            'numero_documento': doc_id, 'requiere_cambio_clave': True
                        }
                    )

                    curso = obtener_o_crear_curso_con_cupo(grado_raw, anio_escolar)
                    if curso:
                        Matricula.objects.filter(
                            estudiante=user, anio_escolar=anio_escolar, tenant=tenant, activo=True
                        ).update(activo=False)

                        Matricula.objects.create(
                            estudiante=user, curso=curso, anio_escolar=anio_escolar,
                            tenant=tenant, activo=True
                        )
                        matriculados += 1
                    else:
                        errores.append(f"Fila {i}: Grado '{grado_raw}' no válido.")
            except Exception as e:
                errores.append(f"Fila {i}: {str(e)}")

        messages.success(request, f"Proceso finalizado. Creados: {creados_est}. Matriculados: {matriculados}.")
    except Exception as e:
        messages.error(request, f"Error crítico al procesar archivo: {e}")

    return redirect('academics:gestion_academica')

@role_required('ADMINISTRADOR')
@require_POST
@transaction.atomic
def admin_eliminar_estudiante(request):
    """Retiro de estudiante con generación de historial."""
    est_id = request.POST.get('estudiante_id')
    estudiante = get_object_or_404(User, id=est_id)
    tenant = get_current_tenant()

    estudiante.is_active = False
    estudiante.save()
    Matricula.objects.filter(estudiante=estudiante, tenant=tenant).update(activo=False)

    messages.success(request, f"Estudiante {estudiante.username} retirado y archivado.")
    return redirect('academics:gestion_academica')

# ==========================================================
# 📝 EVALUACIÓN DOCENTE Y REPORTES
# ==========================================================
@role_required('DOCENTE')
def subir_notas(request):
    tenant = get_current_tenant()
    docente = request.user
    asignaciones = AsignacionMateria.objects.filter(
        docente=docente, activo=True, tenant=tenant
    ).select_related('materia', 'curso')
    periodo_activo = Periodo.objects.filter(tenant=tenant, activo=True).first()

    return render(request, 'academics/subir_notas.html', {
        'asignaciones': asignaciones,
        'periodo': periodo_activo
    })

@role_required(['ADMINISTRADOR', 'COORD_ACADEMICO'])
def reporte_consolidado(request):
    """Sábana de notas consolidada."""
    tenant = get_current_tenant()
    curso_id = request.GET.get('curso_id')
    periodo_id = request.GET.get('periodo_id')
    
    context = {
        'cursos': Curso.objects.filter(tenant=tenant, activo=True).order_by('grado', 'seccion'),
        'periodos': Periodo.objects.filter(tenant=tenant).order_by('id'),
        'datos_reporte': [],
        'materias': []
    }

    if curso_id and periodo_id:
        curso = get_object_or_404(Curso, id=curso_id, tenant=tenant)
        periodo = get_object_or_404(Periodo, id=periodo_id, tenant=tenant)
        materias = Materia.objects.filter(curso=curso, tenant=tenant).order_by('nombre')
        context['materias'] = materias

        matriculas = Matricula.objects.filter(curso=curso, activo=True, tenant=tenant).select_related('estudiante')
        
        reporte = []
        for m in matriculas:
            notas_est = []
            prom_acum = 0
            materias_perdidas = 0
            
            for mat in materias:
                nota = Nota.objects.filter(
                    estudiante=m.estudiante, materia=mat, periodo=periodo, numero_nota=5
                ).first()
                val = float(nota.valor) if nota else 0.0
                
                if 0 < val < 3.0: materias_perdidas += 1
                prom_acum += val
                notas_est.append({'valor': val})

            promedio = prom_acum / len(materias) if materias else 0
            reporte.append({
                'estudiante': m.estudiante,
                'notas': notas_est,
                'promedio': round(promedio, 2),
                'perdidas': materias_perdidas
            })
        
        context['datos_reporte'] = reporte
        context['curso_seleccionado'] = curso
        context['periodo_seleccionado'] = periodo

    return render(request, 'academics/reporte_consolidado.html', context)

# ==========================================================
# ⚡ ENDPOINTS DE API (JSON / AJAX)
# ==========================================================

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def api_crear_curso(request):
    tenant = get_current_tenant()
    try:
        data = json.loads(request.body)
        grado = data.get('grado')
        seccion = data.get('seccion', '').upper()
        anio_escolar = data.get('anio_escolar') or obtener_anio_escolar_actual()
        capacidad = int(data.get('capacidad_maxima', 40))
        
        if grado not in dict(GRADOS_CHOICES):
            return JsonResponse({'error': 'Grado no válido'}, status=400)

        curso, created = Curso.objects.update_or_create(
            grado=grado, seccion=seccion, anio_escolar=anio_escolar, tenant=tenant,
            defaults={
                'nombre': f"{dict(GRADOS_CHOICES)[grado]} {seccion}",
                'capacidad_maxima': capacidad, 'activo': True
            }
        )
        return JsonResponse({'success': True, 'message': f'Curso {curso.nombre} gestionado.', 'curso_id': curso.id}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def api_asignar_director(request):
    tenant = get_current_tenant()
    try:
        data = json.loads(request.body)
        curso = get_object_or_404(Curso, id=data.get('curso_id'), tenant=tenant)
        docente_id = data.get('docente_id')

        with transaction.atomic():
            if docente_id:
                docente = get_object_or_404(User, id=docente_id, perfil__tenant=tenant)
                if curso.director:
                    perfil_viejo = curso.director.perfil
                    perfil_viejo.es_director = False
                    perfil_viejo.save()

                curso.director = docente
                perfil_nuevo = docente.perfil
                perfil_nuevo.es_director = True
                perfil_nuevo.save()
            else:
                curso.director = None
            curso.save()
            return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@csrf_protect
def api_tomar_asistencia(request):
    # Lógica de asistencia delegada a módulo Wellbeing o implementada aquí
    return JsonResponse({'success': True, 'message': 'Endpoint activo'})

@role_required('ADMINISTRADOR')
def api_get_students_by_course(request, curso_id):
    tenant = get_current_tenant()
    try:
        mats = Matricula.objects.filter(
            curso_id=curso_id, activo=True, tenant=tenant
        ).select_related('estudiante').order_by('estudiante__last_name')
        data = [{'id': m.estudiante.id, 'name': m.estudiante.get_full_name() or m.estudiante.username} for m in mats]
        return JsonResponse({'success': True, 'students': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def cargar_periodos_por_curso(request):
    tenant = get_current_tenant()
    curso_id = request.GET.get('curso_id')
    if not curso_id: return JsonResponse([], safe=False)
    periodos = Periodo.objects.filter(curso_id=curso_id, tenant=tenant, activo=True).values('id', 'nombre').order_by('id')
    return JsonResponse(list(periodos), safe=False)

@role_required('DOCENTE')
@require_POST
@csrf_protect
def configurar_plan_evaluacion(request):
    try:
        data = json.loads(request.body)
        materia_id = data.get('materia_id')
        periodo_id = data.get('periodo_id')
        items = data.get('items', [])
        tenant = get_current_tenant()

        with transaction.atomic():
            DefinicionNota.objects.filter(materia_id=materia_id, periodo_id=periodo_id, tenant=tenant).delete()
            for index, item in enumerate(items):
                DefinicionNota.objects.create(
                    tenant=tenant, materia_id=materia_id, periodo_id=periodo_id,
                    nombre=item['nombre'], porcentaje=Decimal(str(item['porcentaje'])), orden=index + 1
                )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)