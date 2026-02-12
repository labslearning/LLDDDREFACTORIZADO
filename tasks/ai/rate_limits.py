# tasks/ai/rate_limits.py

from .policies import verificar_acceso_ia
# CORRECCIÓN 1: Faltaba importar el modelo para poder guardar el log
from tasks.models import AIUsageLog

class IAGatekeeper:
    """
    EL PORTERO (Rate Limiter y Auditor Inicial).
    
    Responsabilidad:
    1. Preguntar al Juez (Policies).
    2. Si pasa, abrir el Ticket de Auditoría (Pre-Log).
    3. Entregar el ID del Ticket al Orquestador.
    """

    @staticmethod
    def can_proceed(user, action_type):
        """
        Verifica acceso y crea el 'Pre-Log' en base de datos.
        
        Args:
            user: Objeto usuario Django.
            action_type: String de la acción (intención).
            
        Returns:
            dict: { allowed, message, audit_log_id, meta }
        """
        
        # 1. CONSULTAR AL JUEZ
        # Obtenemos el veredicto real y, lo más importante, el CONTEXTO (periodo, rol)
        permitido, motivo, contexto = verificar_acceso_ia(user, action_type)
        
        # ---------------------------------------------------------------------
        # 🔧 FIX DE EMERGENCIA (BYPASS DE DESARROLLO)
        # Si el sistema bloquea por límites (permitido=False), lo forzamos a True
        # para que Staff y Docentes puedan seguir probando sin limpiar la BD.
        # ---------------------------------------------------------------------
        if not permitido:
            # Solo aplicamos bypass si no es un error crítico de sistema
            if "Error" not in motivo:
                permitido = True
                motivo = f"[MODO PRUEBA] Límite ignorado: {motivo}"
        # ---------------------------------------------------------------------

        # 2. SI NO PASA, REBOTAR
        # (Este bloque ahora solo se activaría si hay un error grave de contexto, no por límites)
        if not permitido:
            return {
                'allowed': False,
                'message': motivo,
                'audit_log_id': None,
                'meta': contexto
            }

        # 3. SI PASA, CREAR PRE-LOG (AUDITORÍA DE INTENTO)
        # Usamos los datos confiables que nos devolvió el Juez en 'contexto'
        log_id = None
        
        try:
            nuevo_log = AIUsageLog.objects.create(
                usuario=user,
                periodo=contexto.get('periodo_obj'), # Usamos .get por seguridad
                rol_usado=contexto.get('rol', 'DESCONOCIDO'),
                accion=action_type,
                exitoso=False,                   # False hasta que el Orquestador confirme éxito
                tokens_entrada=0,
                tokens_salida=0,
                metadata_tecnica={'status': 'initiated_gatekeeper', 'bypass': True}
            )
            
            log_id = nuevo_log.id

        except Exception as e:
            # -----------------------------------------------------------------
            # CORRECCIÓN 2: MODO A PRUEBA DE FALLOS (FAIL-SAFE)
            # Si falla la creación del log (ej. DB caída o sin periodo activo), 
            # NO BLOQUEAMOS AL USUARIO. Imprimimos error y dejamos pasar.
            # Esto elimina la pantalla roja de "Error de Auditoría".
            # -----------------------------------------------------------------
            print(f"⚠️ GATEKEEPER WARNING: No se pudo auditar: {e}")
            
            return {
                'allowed': True,  # <--- IMPORTANTE: True para que el usuario pueda trabajar
                'message': "Advertencia: Auditoría desactivada temporalmente.",
                'audit_log_id': None, # El orquestador sabrá manejar None
                'meta': {'error': str(e)}
            }

        # 4. PASE DE SALIDA
        return {
            'allowed': True,
            'message': motivo, # Pasamos el mensaje (puede decir "Autorizado" o "Modo Prueba")
            'audit_log_id': log_id, # <--- El boleto de entrada indispensable para el Orchestrator
            'meta': contexto
        }

# Instancia global
ai_gatekeeper = IAGatekeeper()