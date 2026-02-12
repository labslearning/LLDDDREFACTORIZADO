# tasks/ai/policies.py

from tasks.models import PeriodoAcademico, AIUsageLog
from .constants import (
    ROL_ESTUDIANTE, ROL_PROFESOR, ROL_ACUDIENTE, ROL_STAFF, ROL_ADMIN
)

def verificar_acceso_ia(usuario, accion_intencion):  # <--- CAMBIO DE NOMBRE (CRÍTICO)
    """
    EL JUEZ: Decide si un usuario tiene permiso para usar la IA en este momento.
    
    Retorna una tupla: (permitido: bool, motivo: str, contexto: dict)
    """
    
    # --------------------------------------------------------------------------
    # 1. VERIFICAR GOBERNANZA GLOBAL (El Periodo)
    # --------------------------------------------------------------------------
    periodo_activo = PeriodoAcademico.obtener_periodo_activo()
    
    # Obtener el rol del usuario de forma segura
    try:
        perfil = getattr(usuario, 'perfil', None)
        rol_usuario = perfil.rol if perfil else None
        
        # Si es superuser sin perfil, lo tratamos como ADMIN
        if not rol_usuario and usuario.is_superuser:
            rol_usuario = ROL_ADMIN
            
    except Exception:
        rol_usuario = None

    # REGLA DE ORO: Si es ADMIN, pasa siempre (incluso sin periodo activo para pruebas)
    if rol_usuario == ROL_ADMIN:
        return True, "Acceso administrativo concedido.", {
            "periodo_obj": periodo_activo, # Puede ser None y el Log lo aguanta si es null=True
            "rol": ROL_ADMIN,
            "limite": "Infinito"
        }

    # Para mortales (No Admins), el periodo es obligatorio
    if not periodo_activo:
        return False, "No hay un periodo académico activo para el uso de IA.", {}

    if not periodo_activo.esta_vigente:
        return False, f"El periodo '{periodo_activo.nombre}' ha finalizado o no ha iniciado.", {}

    if not rol_usuario:
        return False, "Usuario sin perfil académico asignado.", {}

    # --------------------------------------------------------------------------
    # 4. DEFINIR LÍMITES SEGÚN LA LEY (Base de Datos)
    # --------------------------------------------------------------------------
    limite_permitido = 0
    
    if rol_usuario == ROL_ESTUDIANTE:
        limite_permitido = periodo_activo.limite_intentos_estudiante
    elif rol_usuario == ROL_PROFESOR:
        limite_permitido = periodo_activo.limite_intentos_profesor
    elif rol_usuario == ROL_ACUDIENTE:
        limite_permitido = periodo_activo.limite_intentos_acudiente
    elif rol_usuario == ROL_STAFF:
        limite_permitido = periodo_activo.limite_intentos_staff
    else:
        # Roles no contemplados (seguridad por defecto)
        limite_permitido = 0 

    # --------------------------------------------------------------------------
    # 5. JUICIO: CONTAR ANTECEDENTES
    # --------------------------------------------------------------------------
    # Contamos cuántas veces ha usado la IA exitosamente en este periodo
    consumo_actual = AIUsageLog.objects.filter(
        usuario=usuario,
        periodo=periodo_activo,
        exitoso=True  # Solo descontamos intentos si la IA respondió bien (Pedagogía justa)
    ).count()

    # --------------------------------------------------------------------------
    # 7. VEREDICTO FINAL
    # --------------------------------------------------------------------------
    intentos_restantes = limite_permitido - consumo_actual
    
    if intentos_restantes > 0:
        return True, "Acceso autorizado.", {
            "periodo_obj": periodo_activo, # <--- CAMBIO CLAVE: rate_limits espera 'periodo_obj'
            "rol": rol_usuario,
            "intentos_restantes": intentos_restantes,
            "limite_total": limite_permitido
        }
    else:
        # UX Pedagógica: El mensaje explica por qué
        return False, (
            f"Has alcanzado tu límite de asistencias por IA para el periodo {periodo_activo.nombre}. "
            "Te invitamos a reflexionar sobre las orientaciones ya recibidas."
        ), {
            "periodo_obj": periodo_activo,
            "intentos_restantes": 0
        }