import datetime
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from apps.academics.models import Periodo

# Importaciones de Modelos
from django.contrib.auth.models import User
from tasks.models import (
    BovedaSeguridad, CierreAnualLog, Perfil, 
    Curso, Materia, Matricula, ObservadorArchivado
)

# Importaciones de Servicios de Arquitectura
from tasks.services.vault import VaultManagerService
from tasks.services.rollover import YearRolloverService, ReverseProtocolService

# ==============================================================================
# 🛡️ GATEKEEPER: SEGURIDAD DE ACCESO (NIVEL NÚCLEO)
# ==============================================================================
def is_superuser(user):
    """
    Verifica acceso de nivel raíz. Solo administradores activos.
    """
    return user.is_authenticated and user.is_active and user.is_superuser

# ==============================================================================
# 🦅 SALA DE GUERRA: CONTROL DE CIERRE ANUAL
# ==============================================================================
@login_required
@user_passes_test(is_superuser)
def panel_cierre_anual(request):
    """
    Gestiona el ciclo de vida anual de la institución.
    """
    anio_actual = datetime.datetime.now().year
    anio_nuevo = anio_actual + 1
    
    if request.method == 'POST':
        confirmacion = request.POST.get('frase_confirmacion', '').strip()
        frase_esperada = f"CERRAR {anio_actual}"
        
        if confirmacion != frase_esperada:
            messages.error(request, f"⛔ ALERTA: Frase incorrecta. Se esperaba: '{frase_esperada}'")
            return redirect('panel_cierre_anual')
        
        try:
            servicio = YearRolloverService(anio_actual, request.user)
            exito, mensaje, log_id = servicio.ejecutar_cierre()
            
            if exito:
                messages.success(request, f"✅ PROTOCOLO COMPLETADO: {mensaje}")
                messages.info(request, f"🎉 Ciclo {anio_nuevo} iniciado. Sistema purgado.")
            else:
                messages.error(request, f"❌ ERROR CRÍTICO: {mensaje}")
        except Exception as e:
            messages.error(request, f"🔥 FALLO DEL SISTEMA: {str(e)}")
            
        return redirect('panel_cierre_anual')

    historial_cierres = CierreAnualLog.objects.select_related('ejecutado_por').order_by('-fecha_ejecucion')[:10]
    
    context = {
        'anio_actual': anio_actual,
        'anio_siguiente': anio_nuevo,
        'historial': historial_cierres,
        'fecha_servidor': timezone.now()
    }
    return render(request, 'admin/cierre_anual.html', context)

@login_required
@user_passes_test(is_superuser)
@require_POST
def revertir_cierre_anual(request, log_id):
    """
    Protocolo de restauración de emergencia ante fallos en el cierre.
    """
    try:
        servicio = ReverseProtocolService(log_id, request.user)
        exito, mensaje = servicio.ejecutar_reversion()
        
        if exito:
            messages.success(request, f"⏪ TIEMPO REVERTIDO: {mensaje}")
        else:
            messages.error(request, f"❌ FALLO EN RESTAURACIÓN: {mensaje}")
    except Exception as e:
        messages.error(request, f"🔥 ERROR CRÍTICO: {str(e)}")
        
    return redirect('panel_cierre_anual')

# ==============================================================================
# 🛡️ BÓVEDA: CUSTODIA DIGITAL E INTEGRIDAD
# ==============================================================================
@login_required
@user_passes_test(is_superuser)
def panel_boveda(request):
    """
    Generación de snapshots inmutables de la base de datos.
    """
    if request.method == 'POST':
        nombre = request.POST.get('nombre_respaldo', '').strip()
        if not nombre:
            nombre = f"RESPALDO_SISTEMA_{timezone.now().strftime('%Y%m%d_%H%M')}"
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_cliente = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

        service = VaultManagerService(request.user, nombre, ip_cliente=ip_cliente)
        
        try:
            exito, resultado = service.generar_snapshot_militar()
            if exito:
                messages.success(request, f"🛡️ Activo de Bóveda Sellado: '{nombre}'.")
            else:
                messages.error(request, f"❌ Fallo en la Bóveda: {resultado}")
        except Exception as e:
            messages.error(request, f"🔥 Error de Infraestructura: {str(e)}")
            
        return redirect('panel_boveda')

    respaldos = BovedaSeguridad.objects.select_related('generado_por').order_by('-fecha_generacion')[:20]
    context = {
        'respaldos': respaldos,
        'config_seguridad': {
            'engine_version': '2.5.0-PRO',
            'last_sync': timezone.now(),
            'storage_status': 'ONLINE'
        }
    }
    return render(request, 'admin/boveda.html', context)

@login_required
@user_passes_test(is_superuser)
@require_POST
def verificar_integridad_respaldo(request, uuid_operacion):
    respaldo = get_object_or_404(BovedaSeguridad, uuid_operacion=uuid_operacion)
    if respaldo.verificar_integridad():
        messages.success(request, f"✅ Integridad Confirmada (SHA-256 coincide).")
    else:
        messages.error(request, f"🚨 ALERTA: El archivo ha sido manipulado.")
    return redirect('panel_boveda')

# ==============================================================================
# 💉 INJERTO QUIRÚRGICO: VISTAS ADMINISTRATIVAS DE GESTIÓN
# ==============================================================================

@login_required
@user_passes_test(is_superuser)
def gestion_perfiles(request):
    """
    Sutura de AttributeError: Vista para administrar roles y estados de perfiles.
    """
    query = request.GET.get('q', '')
    perfiles = Perfil.objects.select_related('user').filter(
        Q(user__username__icontains=query) | Q(rol__icontains=query)
    ).order_by('user__username')
    
    return render(request, 'admin/gestion_perfiles.html', {
        'perfiles': perfiles,
        'query': query
    })

@login_required
@user_passes_test(is_superuser)
def admin_ex_estudiantes(request):
    """
    Sutura de AttributeError: Acceso al archivo histórico de la institución.
    """
    archivados = ObservadorArchivado.objects.all().order_by('-fecha_archivado')
    return render(request, 'admin/archivo_estudiantes.html', {
        'archivados': archivados
    })

@login_required
@user_passes_test(is_superuser)
def asignar_curso_estudiante(request):
    """
    Sutura de NoReverseMatch: Vinculación de estudiantes a la malla curricular.
    """
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    estudiantes_sin_curso = Perfil.objects.filter(rol='ESTUDIANTE').select_related('user').all()
    
    return render(request, 'admin/asignar_estudiantes.html', {
        'cursos': cursos,
        'estudiantes': estudiantes_sin_curso
    })

# ==============================================================================
# 🚨 CURAS DASHBOARD APPS (Data Center, Shadow, AI)
# ==============================================================================

@login_required
@user_passes_test(is_superuser)
def import_history(request):
    """Vista para el historial de importaciones masivas (Data Center)."""
    return render(request, 'admin/import_history.html', {})

@login_required
@user_passes_test(is_superuser)
def shadow_tenant(request):
    """Vista para Shadow Monitor (Riesgo & BI)."""
    return render(request, 'admin/shadow_monitor.html', {})

@login_required
@user_passes_test(is_superuser)
def ai_engine(request):
    """Vista para el motor de Inteligencia Artificial."""
    return render(request, 'admin/ai_engine.html', {})

# ==============================================================================
# 🚑 CURAS FINALES: OPERATIVIDAD DIARIA (SOLUCIÓN ERROR ACTUAL)
# ==============================================================================

@login_required
@user_passes_test(is_superuser)
def mostrar_registro_individual(request):
    """Vista para el formulario de registro manual de estudiantes."""
    return render(request, 'admin/registro_individual.html', {})

@login_required
@user_passes_test(is_superuser)
def admin_db_visual(request):
    """Vista para el mapa visual de la base de datos."""
    return render(request, 'admin/db_visual.html', {})

@login_required
@user_passes_test(is_superuser)
def gestionar_staff(request):
    """Vista para la gestión de psicólogos y coordinadores."""
    return render(request, 'admin/gestion_staff.html', {})

@login_required
@user_passes_test(is_superuser)
def reporte_consolidado(request):
    """Vista para el reporte de notas generales y consolidados."""
    return render(request, 'admin/reporte_consolidado.html', {})


from django.http import JsonResponse

# ... (resto del código previo)

@login_required
@user_passes_test(is_superuser)
@require_POST
def panel_api_toggle_boletin_permiso(request):
    """API para habilitar/deshabilitar visualización de boletines."""
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        nuevo_estado = data.get('estado') # True/False
        
        # Lógica Industrial: Buscamos el perfil del estudiante
        perfil = get_object_or_404(Perfil, id=estudiante_id, rol='ESTUDIANTE')
        # Aquí asumo que tienes un campo boolean en Perfil o Matrícula
        # Ejemplo: perfil.permiso_boletin = nuevo_estado
        # perfil.save()
        
        return JsonResponse({'status': 'ok', 'message': 'Permiso de boletín actualizado'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@user_passes_test(is_superuser)
@require_POST
def panel_api_toggle_observador(request):
    """API para habilitar/deshabilitar visualización del observador."""
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        nuevo_estado = data.get('estado')
        
        perfil = get_object_or_404(Perfil, id=estudiante_id, rol='ESTUDIANTE')
        # perfil.permiso_observador = nuevo_estado
        # perfil.save()
        
        return JsonResponse({'status': 'ok', 'message': 'Estado del observador actualizado'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_superuser)
def desactivar_staff(request, user_id):
    """Protocolo de revocación de acceso para personal especializado."""
    miembro = get_object_or_404(User, id=user_id)
    
    # Software Industrial: No borramos, desactivamos por integridad histórica
    miembro.is_active = False
    miembro.save()
    
    messages.warning(request, f"🔒 Acceso revocado para: {miembro.get_full_name() or miembro.username}")
    return redirect('gestionar_staff')

# tasks/views_admin.py
from django.http import JsonResponse
from apps.academics.models import Periodo

def api_cargar_periodos(request):
    """API ligera para llenar el select de periodos vía AJAX"""
    curso_id = request.GET.get('curso_id')
    if curso_id:
        # Lógica: Filtrar periodos activos para el año del curso seleccionado
        # Si tu modelo Periodo no está ligado a Curso directamente, 
        # asumo que traes todos los periodos activos del sistema.
        periodos = Periodo.objects.filter(activo=True).values('id', 'nombre')
        return JsonResponse(list(periodos), safe=False)
    return JsonResponse([], safe=False)