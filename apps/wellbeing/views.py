# apps/wellbeing/views.py
import json
import logging
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.template.loader import render_to_string
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

# 🩸 CONEXIÓN CON EL LEGACY (Modelos y Utilidades)
from tasks.models import (
    User, Perfil, Matricula, Institucion, Periodo, Nota, Asistencia,
    Observacion, Seguimiento, ActaInstitucional, ObservadorArchivado, BoletinArchivado,
    Curso, Materia # Necesarios para dashboards y reportes
)
from tasks.decorators import role_required

# 🟢 IMPORTACIÓN CORRECTA DE FORMULARIOS (Desde su propia app)
from .forms import ObservacionForm, ActaInstitucionalForm, SeguimientoForm

# Los de perfil, si se usan aquí, se traen de la app social
from apps.social.forms import UserEditForm, EditarPerfilForm

# Librería de PDF (Manejo de error si no está instalada)
try:
    from weasyprint import HTML
except ImportError:
    HTML = None

logger = logging.getLogger(__name__)

# Roles permitidos para el módulo de bienestar
STAFF_ROLES = ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO', 'ADMINISTRADOR']

# ==========================================================
# ❤️ PANEL PRINCIPAL (DASHBOARD BIENESTAR)
# ==========================================================

@role_required(STAFF_ROLES)
def dashboard_bienestar(request):
    """
    VISTA MAESTRA DE INTELIGENCIA INSTITUCIONAL - STRATOS (VERSIÓN CIRUGÍA DE PRECISIÓN)
    """
    # 0. GESTIÓN DOCUMENTAL (PEI Y MANUAL)
    if request.method == 'POST':
        if 'pei_file' in request.FILES:
            if request.user.perfil.rol in ['COORD_ACADEMICO', 'ADMINISTRADOR']:
                institucion, _ = Institucion.objects.get_or_create(id=1)
                archivo = request.FILES['pei_file']
                if archivo.name.lower().endswith('.pdf'):
                    institucion.archivo_pei = archivo
                    institucion.save()
                    messages.success(request, "✅ PEI actualizado correctamente.")
                else:
                    messages.error(request, "❌ Error: El archivo debe ser PDF.")
        elif 'manual_file' in request.FILES:
            if request.user.perfil.rol in ['COORD_CONVIVENCIA', 'ADMINISTRADOR']:
                institucion, _ = Institucion.objects.get_or_create(id=1)
                archivo = request.FILES['manual_file']
                if archivo.name.lower().endswith('.pdf'):
                    institucion.archivo_manual_convivencia = archivo
                    institucion.save()
                    messages.success(request, "✅ Manual de Convivencia actualizado.")
                else:
                    messages.error(request, "❌ Error: El archivo debe ser PDF.")
        return redirect('dashboard_bienestar')

    # 1. MOTOR DE BÚSQUEDA (ESTUDIANTES)
    query = request.GET.get('q')
    estudiantes_busqueda = []
    if query:
        estudiantes_busqueda = User.objects.filter(
            Q(perfil__rol='ESTUDIANTE') &
            (Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        ).select_related('perfil').distinct()[:25]

    # 2. RADAR DE RIESGO ACADÉMICO
    matriculas_activas = Matricula.objects.filter(activo=True).select_related('estudiante', 'curso')
    riesgo_academico_total = []
    total_materias_perdidas_institucional = 0

    for mat in matriculas_activas:
        est = mat.estudiante
        notas_reprobadas = Nota.objects.filter(
            estudiante=est,
            numero_nota=5,    # Nota definitiva
            valor__lt=3.0,    # Reprobado
            materia__curso=mat.curso
        ).exclude(
            Q(materia__nombre__icontains="Convivencia") | 
            Q(materia__nombre__icontains="Comportamiento")
        ).select_related('materia')

        conteo_perdidas = notas_reprobadas.count()
        
        if conteo_perdidas > 0:
            total_materias_perdidas_institucional += conteo_perdidas
            materias_nombres = [n.materia.nombre for n in notas_reprobadas]
            prom_reprobacion = notas_reprobadas.aggregate(avg=Avg('valor'))['avg'] or 0

            riesgo_academico_total.append({
                'estudiante': est,
                'curso': mat.curso,
                'materias_perdidas': conteo_perdidas,
                'materias_nombres': materias_nombres,
                'promedio_riesgo': round(float(prom_reprobacion), 2)
            })

    riesgo_academico_total.sort(key=lambda x: (-x['materias_perdidas'], x['promedio_riesgo']))

    # 3. ANALÍTICA DE GESTIÓN POR CURSOS
    cursos_activos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    periodos_header = []
    if cursos_activos.exists():
        periodos_header = Periodo.objects.filter(curso=cursos_activos.first(), activo=True).order_by('id')

    total_estudiantes_colegio = matriculas_activas.count()
    suma_promedios_acad = 0.0
    suma_promedios_conv = 0.0
    cursos_con_datos_acad = 0
    cursos_con_datos_conv = 0

    chart_labels = []      
    chart_data_acad = []   
    chart_data_conv = []   
    vista_cursos = []
    
    for curso in cursos_activos:
        mats_curso = matriculas_activas.filter(curso=curso)
        num_alumnos = mats_curso.count()

        val_acad = Nota.objects.filter(
            materia__curso=curso,
            numero_nota=5 
        ).exclude(materia__nombre__icontains="Convivencia").aggregate(avg=Avg('valor'))['avg']
        
        prom_acad_curso = float(val_acad) if val_acad is not None else 0.0

        val_conv = Nota.objects.filter(
            materia__curso=curso,
            materia__nombre__icontains="Convivencia",
            numero_nota=5 
        ).aggregate(avg=Avg('valor'))['avg']

        prom_conv_curso = float(val_conv) if val_conv is not None else 0.0

        if num_alumnos > 0:
            chart_labels.append(f"{curso.nombre}")
            chart_data_acad.append(round(prom_acad_curso, 2))
            chart_data_conv.append(round(prom_conv_curso, 2) if prom_conv_curso > 0 else 0)
            
            if prom_acad_curso > 0:
                suma_promedios_acad += prom_acad_curso
                cursos_con_datos_acad += 1
            if prom_conv_curso > 0:
                suma_promedios_conv += prom_conv_curso
                cursos_con_datos_conv += 1

        # Detalle estudiantes
        periodos_del_curso = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
        lista_estudiantes_curso = []
        ranking_academico_curso = []
        
        for m in mats_curso:
            estudiante = m.estudiante
            notas_conv_periodo = {}
            for p in periodos_del_curso:
                nota_real_obj = Nota.objects.filter(
                    estudiante=estudiante, 
                    periodo=p, 
                    materia__curso=curso,
                    materia__nombre__icontains="Convivencia",
                    numero_nota=5 
                ).first()
                
                if nota_real_obj:
                    notas_conv_periodo[p.id] = nota_real_obj.valor
                else:
                    notas_conv_periodo[p.id] = "-"
            
            lista_estudiantes_curso.append({
                'obj': estudiante,
                'notas': notas_conv_periodo
            })

            p_ind = Nota.objects.filter(
                estudiante=estudiante, 
                materia__curso=curso,
                numero_nota=5
            ).exclude(materia__nombre__icontains="Convivencia").aggregate(p=Avg('valor'))['p']
            
            ranking_academico_curso.append({
                'nombre': estudiante.get_full_name() or estudiante.username,
                'promedio': round(float(p_ind or 0), 2)
            })

        ranking_academico_curso.sort(key=lambda x: x['promedio'], reverse=True)

        if lista_estudiantes_curso:
            vista_cursos.append({
                'curso': curso,
                'estudiantes': lista_estudiantes_curso,
                'stats': {
                    'acad': round(prom_acad_curso, 2), 
                    'conv': round(prom_conv_curso, 2), 
                    'alumnos': num_alumnos
                },
                'top_10_academico': ranking_academico_curso[:10]
            })

    # 4. KPIs GLOBALES
    prom_global_acad = round(suma_promedios_acad / cursos_con_datos_acad, 2) if cursos_con_datos_acad > 0 else 0
    prom_global_conv = round(suma_promedios_conv / cursos_con_datos_conv, 2) if cursos_con_datos_conv > 0 else 0

    stats_asistencia = {
        'asistio': Asistencia.objects.filter(estado='ASISTIO').count(),
        'falla': Asistencia.objects.filter(estado='FALLA').count(),
        'excusa': Asistencia.objects.filter(estado='EXCUSA').count(),
        'tarde': Asistencia.objects.filter(estado='TARDE').count(),
    }
    
    top_fallas = Asistencia.objects.filter(estado='FALLA')\
        .values('estudiante__id', 'estudiante__first_name', 'estudiante__last_name', 'curso__nombre')\
        .annotate(total=Count('id'))\
        .order_by('-total')[:5]

    alertas_convivencia = Nota.objects.filter(
        materia__nombre__icontains="Convivencia",
        materia__curso__activo=True,
        numero_nota=5, 
        valor__lt=3.5  
    ).values(
        'estudiante__id', 'estudiante__first_name', 'estudiante__last_name', 'materia__curso__nombre'
    ).annotate(
        promedio=Avg('valor')
    ).order_by('promedio')[:5]
    
    institucion = Institucion.objects.first()

    # 5. HISTORIAL OBSERVACIONES
    all_observaciones = Observacion.objects.all()
    kpi_obs = {
        'total': all_observaciones.count(),
        'convivencia': all_observaciones.filter(tipo='CONVIVENCIA').count(),
        'academica': all_observaciones.filter(Q(tipo='ACADEMICO') | Q(tipo='ACADEMICA')).count(),
        'psicologia': all_observaciones.filter(Q(tipo='PSICOLOGIA') | Q(tipo='PSICOLOGICA')).count()
    }

    historial_seguimientos = Seguimiento.objects.select_related('estudiante', 'profesional').all().order_by('-fecha')[:100]
    
    base_observaciones = Observacion.objects.select_related('estudiante', 'autor').all().order_by('-fecha_creacion')
    if query:
        base_observaciones = base_observaciones.filter(
            Q(estudiante__username__icontains=query) |
            Q(estudiante__first_name__icontains=query) |
            Q(estudiante__last_name__icontains=query) |
            Q(descripcion__icontains=query)
        )
    observaciones = base_observaciones[:50]

    context = {
        'estudiantes': estudiantes_busqueda, 
        'query': query,
        'vista_cursos': vista_cursos,
        'periodos': periodos_header,
        'institucion': institucion,
        'top_riesgo_academico': riesgo_academico_total, 
        'kpi': {
            **kpi_obs,
            'total_alumnos': total_estudiantes_colegio,
            'prom_global_acad': prom_global_acad,
            'prom_global_conv': prom_global_conv,
            'total_cursos': cursos_activos.count(),
            'total_materias_perdidas': total_materias_perdidas_institucional 
        },
        'chart_data': {
            'labels': json.dumps(chart_labels),
            'acad': json.dumps(chart_data_acad),
            'conv': json.dumps(chart_data_conv)
        },
        'stats_asistencia': json.dumps(list(stats_asistencia.values())),
        'top_fallas': top_fallas,
        'alertas_convivencia': alertas_convivencia,
        'historial_seguimientos': historial_seguimientos,
        'observaciones': observaciones,
    }

    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/dashboard_bienestar.html', context)


# ==========================================================
# 📋 HISTORIAL DE ASISTENCIA (COORDINACIÓN)
# ==========================================================

@role_required(STAFF_ROLES)
def historial_asistencia(request):
    curso_id = request.GET.get('curso')
    estado = request.GET.get('estado')
    
    asistencias = Asistencia.objects.select_related('estudiante', 'curso', 'materia', 'registrado_por').all().order_by('-fecha')

    if curso_id:
        asistencias = asistencias.filter(curso_id=curso_id)
    if estado:
        asistencias = asistencias.filter(estado=estado)
    
    paginator = Paginator(asistencias, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/historial_asistencia.html', {
        'page_obj': page_obj,
        'cursos': cursos,
        'current_curso': int(curso_id) if curso_id else '',
        'current_estado': estado,
        'total_registros': asistencias.count()
    })

# ==========================================================
# 📊 HISTORIAL GLOBAL OBSERVACIONES (INTELIGENCIA)
# ==========================================================

@role_required(['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO'])
def historial_global_observaciones(request):
    # Reutilizamos lógica simplificada para no duplicar demasiado código
    observaciones = Observacion.objects.select_related('estudiante', 'autor').all().order_by('-fecha_creacion')
    query = request.GET.get('q')
    if query:
        observaciones = observaciones.filter(
            Q(estudiante__first_name__icontains=query) |
            Q(estudiante__last_name__icontains=query) |
            Q(estudiante__username__icontains=query) |
            Q(descripcion__icontains=query)
        )
    
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/historial_global_observaciones.html', {
        'observaciones': observaciones,
        'query': query,
        'institucion': Institucion.objects.first(),
    })


# ==========================================================
# 📝 OBSERVADOR DISCIPLINARIO Y SEGUIMIENTOS
# ==========================================================

@role_required(STAFF_ROLES)
def ver_observador(request, estudiante_id):
    estudiante = get_object_or_404(User, id=estudiante_id)
    if not hasattr(estudiante, 'perfil') or estudiante.perfil.rol != 'ESTUDIANTE':
        messages.error(request, "El usuario seleccionado no es un estudiante.")
        return redirect('dashboard_bienestar')

    observaciones = Observacion.objects.filter(estudiante=estudiante).select_related('autor', 'periodo').order_by('-fecha_creacion')
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/ver_observador.html', {
        'estudiante': estudiante,
        'observaciones': observaciones
    })

@role_required(STAFF_ROLES)
def crear_observacion(request, estudiante_id):
    estudiante = get_object_or_404(User, id=estudiante_id)
    if request.method == 'POST':
        form = ObservacionForm(request.POST, user=request.user, estudiante=estudiante)
        if form.is_valid():
            observacion = form.save(commit=False)
            observacion.estudiante = estudiante
            observacion.autor = request.user
            observacion.save()
            messages.success(request, "Observación registrada correctamente.")
            return redirect('ver_observador', estudiante_id=estudiante.id)
    else:
        form = ObservacionForm(user=request.user, estudiante=estudiante)
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/form_observacion.html', {'form': form, 'estudiante': estudiante, 'titulo': 'Nueva Observación'})

@role_required(STAFF_ROLES)
def editar_observacion(request, observacion_id):
    observacion = get_object_or_404(Observacion, id=observacion_id)
    es_admin = request.user.perfil.rol == 'ADMINISTRADOR'
    es_autor = observacion.autor == request.user

    if not es_admin and not es_autor:
        messages.error(request, "No tienes permiso para editar esta observación.")
        return redirect('ver_observador', estudiante_id=observacion.estudiante.id)

    if not observacion.es_editable and not es_admin:
        messages.error(request, "El tiempo de edición (24h) ha expirado.")
        return redirect('ver_observador', estudiante_id=observacion.estudiante.id)

    if request.method == 'POST':
        form = ObservacionForm(request.POST, instance=observacion, user=request.user, estudiante=observacion.estudiante)
        if form.is_valid():
            form.save()
            messages.success(request, "Observación actualizada.")
            return redirect('ver_observador', estudiante_id=observacion.estudiante.id)
    else:
        form = ObservacionForm(instance=observacion, user=request.user, estudiante=observacion.estudiante)
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/form_observacion.html', {'form': form, 'estudiante': observacion.estudiante, 'titulo': 'Editar Observación'})

@role_required(STAFF_ROLES)
def guardar_seguimiento(request):
    try:
        estudiante_id = request.POST.get('estudiante_id')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion')
        observaciones_adicionales = request.POST.get('observaciones_adicionales', '')

        if not all([estudiante_id, tipo, descripcion]):
            return JsonResponse({'success': False, 'error': 'Faltan datos obligatorios'}, status=400)

        estudiante = get_object_or_404(User, id=estudiante_id)
        nuevo_seguimiento = Seguimiento.objects.create(
            estudiante=estudiante,
            tipo=tipo,
            descripcion=descripcion,
            observaciones_adicionales=observaciones_adicionales,
            profesional=request.user, 
        )
        return JsonResponse({'success': True, 'id': nuevo_seguimiento.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==========================================================
# 👥 GESTIÓN DE STAFF
# ==========================================================

@role_required('ADMINISTRADOR')
def gestionar_staff(request):
    staff_roles = [
        ('PSICOLOGO', 'Psicólogo'),
        ('COORD_CONVIVENCIA', 'Coord. Convivencia'),
        ('COORD_ACADEMICO', 'Coord. Académico')
    ]
    institucion = Institucion.objects.first()
    if not institucion:
        institucion = Institucion.objects.create(nombre="Institución Educativa")

    if request.method == 'POST':
        if 'pei_file' in request.FILES:
             pass
        elif 'username' in request.POST:
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            rol = request.POST.get('rol')
            try:
                with transaction.atomic():
                    if rol not in [r[0] for r in staff_roles]: raise ValueError("Rol inválido")
                    user = User.objects.create_user(
                        username=username, first_name=first_name, last_name=last_name,
                        email=email, password=settings.DEFAULT_TEMP_PASSWORD
                    )
                    Perfil.objects.create(user=user, rol=rol, requiere_cambio_clave=True)
                    messages.success(request, f"Usuario {username} creado.")
            except Exception as e:
                messages.error(request, f"Error: {e}")
        return redirect('gestionar_staff')

    staff_users = User.objects.filter(perfil__rol__in=[r[0] for r in staff_roles], is_active=True).select_related('perfil')
    
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing' (Asumiendo que moviste este archivo o usas la estructura modular)
    return render(request, 'wellbeing/gestionar_staff.html', {'staff_users': staff_users, 'roles': staff_roles, 'institucion': institucion})

@role_required('ADMINISTRADOR')
def desactivar_staff(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario.is_superuser or usuario == request.user:
        messages.error(request, "No puedes desactivar a este usuario.")
        return redirect('gestionar_staff')
    usuario.is_active = False
    usuario.save()
    messages.success(request, "Usuario desactivado.")
    return redirect('gestionar_staff')

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def toggle_observador_permiso(request):
    try:
        data = json.loads(request.body)
        matricula = Matricula.objects.filter(estudiante_id=data.get('estudiante_id'), activo=True).first()
        if not matricula: return JsonResponse({'status': 'error', 'message': 'Matrícula no encontrada'}, status=404)
        
        matricula.puede_ver_observador = bool(data.get('estado'))
        matricula.save(update_fields=['puede_ver_observador'])
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================================
# 📜 ACTAS INSTITUCIONALES
# ==========================================================

@login_required
def historial_actas(request):
    if request.user.perfil.rol in ['ADMINISTRADOR', 'DIRECTOR_CURSO', 'PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
        actas = ActaInstitucional.objects.all()
    else:
        actas = ActaInstitucional.objects.filter(Q(creador=request.user) | Q(participantes=request.user)).distinct()
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/historial_actas.html', {'actas': actas})

@login_required
def crear_acta(request):
    if request.method == 'POST':
        form = ActaInstitucionalForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                acta = form.save(commit=False)
                acta.creador = request.user
                acta.save()
                form.save_m2m()
                messages.success(request, f"Acta #{acta.consecutivo} generada.")
                return redirect('historial_actas')
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Formulario inválido.")
    else:
        form = ActaInstitucionalForm(initial={'fecha': timezone.now()})
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing'
    return render(request, 'wellbeing/crear_acta.html', {'form': form})

# ==========================================================
# 🖨️ REPORTES PDF (WEASYPRINT)
# ==========================================================

@login_required
def generar_observador_pdf(request, estudiante_id):
    es_staff = request.user.perfil.rol in STAFF_ROLES
    es_acudiente = request.user.perfil.rol == 'ACUDIENTE'
    estudiante = get_object_or_404(User, id=estudiante_id)
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).first()

    if es_acudiente:
        pass
    elif not es_staff:
        return redirect('home')

    observaciones = Observacion.objects.filter(estudiante=estudiante).select_related('autor__perfil', 'periodo').order_by('periodo__id', 'fecha_creacion')
    institucion = Institucion.objects.first()

    if HTML is None: return HttpResponse("Error: WeasyPrint no instalado.", status=500)

    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing/pdf/'
    html_string = render_to_string('wellbeing/pdf/observador_template.html', {
        'estudiante': estudiante, 'observaciones': observaciones,
        'institucion': institucion, 'curso': matricula.curso if matricula else None,
        'fecha_impresion': date.today()
    })
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="observador_{estudiante.username}.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(response)
    return response

@login_required
def generar_seguimiento_pdf(request, seguimiento_id):
    seguimiento = get_object_or_404(Seguimiento.objects.select_related('estudiante', 'profesional'), id=seguimiento_id)
    institucion = Institucion.objects.first() 
    context = {
        'seguimiento': seguimiento, 'estudiante': seguimiento.estudiante,
        'profesional': seguimiento.profesional, 'institucion': institucion, 'request': request,
    }
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing/pdf/'
    html_string = render_to_string('wellbeing/pdf/seguimiento_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Seguimiento_{seguimiento.estudiante.username}.pdf"'
    return response

@login_required
def generar_acta_pdf(request, acta_id):
    acta = get_object_or_404(ActaInstitucional, id=acta_id)
    institucion = Institucion.objects.first()
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing/pdf/'
    html_string = render_to_string('wellbeing/pdf/acta_institucional_weasy.html', {'acta': acta, 'institucion': institucion, 'request': request})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Acta_{acta.consecutivo}.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response

@role_required(['ADMINISTRADOR', 'COORD_CONVIVENCIA', 'PSICOLOGO', 'COORD_ACADEMICO', 'DIRECTOR_CURSO'])
def generar_reporte_integral_bienestar(request, estudiante_id):
    estudiante = get_object_or_404(User, id=estudiante_id)
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).first()
    institucion = Institucion.objects.first()
    
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')
    seguimientos = Seguimiento.objects.filter(estudiante=estudiante).order_by('-fecha')
    promedio_global = Nota.objects.filter(estudiante=estudiante).aggregate(Avg('valor'))['valor__avg'] or 0.0
    total_fallas = Asistencia.objects.filter(estudiante=estudiante, estado='FALLA').count()

    resumen = {
        'total_obs': observaciones.count(),
        'total_seg': seguimientos.count(),
        'obs_convivencia': observaciones.filter(tipo='CONVIVENCIA').count(),
        'promedio_actual': round(promedio_global, 2),
        'total_fallas': total_fallas
    }
    concepto_ia = f"El estudiante registra {resumen['total_obs']} observaciones y {resumen['total_seg']} seguimientos."

    context = {
        'estudiante': estudiante, 'curso': matricula.curso if matricula else None,
        'institucion': institucion, 'observaciones': observaciones, 'seguimientos': seguimientos,
        'resumen': resumen, 'concepto_ia': concepto_ia, 'fecha_impresion': timezone.now(),
        'generado_por': request.user.get_full_name(), 'request': request
    }
    
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing/pdf/'
    html_string = render_to_string('wellbeing/pdf/reporte_integral_template.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Expediente_{estudiante.username}.pdf"'
    return response

@role_required(['ADMINISTRADOR', 'COORD_CONVIVENCIA', 'PSICOLOGO', 'COORD_ACADEMICO', 'DIRECTOR_CURSO'])
def generar_acta_historial_integral(request, estudiante_id):
    estudiante = get_object_or_404(User, id=estudiante_id)
    institucion = Institucion.objects.first()
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')[:10]
    
    acta_virtual = {
        'consecutivo': 'AUTO-GEN', 'fecha': timezone.now(), 'hora_fin': timezone.now(),
        'titulo': f"CONSOLIDADO INTEGRAL: {estudiante.get_full_name().upper()}",
        'get_tipo_display': 'SEGUIMIENTO DISCIPLINARIO', 'tipo': 'SITUACION_ESPECIAL',
        'creador': request.user, 'implicado': estudiante, 'participantes': [request.user],
        'orden_dia': "1. Revisión antecedentes.\n2. Análisis.\n3. Expediente.",
        'contenido': f"Documento oficial del estudiante ID {estudiante.username}.",
        'compromisos': "Documento informativo.", 'asistentes_externos': "N/A"
    }

    context = {'acta': acta_virtual, 'institucion': institucion, 'observaciones_adjuntas': observaciones}
    # 🏥 CORRECCIÓN DE RUTA: Apunta a 'wellbeing/pdf/'
    html_string = render_to_string('wellbeing/pdf/acta_institucional_weasy.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Acta_Oficial_{estudiante.username}.pdf"'
    return response


from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def documentos_institucionales(request):
    # Aquí puedes pasar una lista de archivos o PDFs si los tienes
    return render(request, 'wellbeing/documentos.html')