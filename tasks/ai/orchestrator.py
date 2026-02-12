# tasks/ai/orchestrator.py

import logging
import json
from django.utils import timezone
from tasks.models import AIUsageLog

# --- IMPORTACIONES DEL SISTEMA ---
from .rate_limits import ai_gatekeeper
from .context_builder import context_builder

# 🔴 CORRECCIÓN CRÍTICA: Importamos la instancia específica para evitar AttributeError
from .prompts.prompt_factory import prompt_factory

from .cache import ai_cache
from .deepseek_client import deepseek_client
from .constants import ACCION_ANALISIS_CONVIVENCIA, MODEL_NAME

logger = logging.getLogger(__name__)

class AIOrchestrator:
    """
    EL DIRECTOR DE ORQUESTA (Producción - Fase 12 + Context Injection).
    
    Responsabilidad:
    Coordinar el flujo entre seguridad, datos, caché y la API de IA.
    Soporta inyección de contexto manual (override) para vistas avanzadas.
    """

    def process_request(self, user, action_type, user_query=None, **kwargs):
        """
        Punto único de entrada para todas las solicitudes de IA.
        Acepta 'context_override' en kwargs para saltar la construcción automática.
        """
        # ---------------------------------------------------------
        # 1. GATEKEEPER — PERMISOS + TICKET
        # ---------------------------------------------------------
        # El Gatekeeper abre un registro en AIUsageLog con estado pendiente
        gate = ai_gatekeeper.can_proceed(user, action_type)
        log_id = gate.get("audit_log_id")

        if not gate.get("allowed"):
            return {
                "success": False,
                "content": gate.get("message"),
                "source": "POLICY",
                "meta": gate.get("meta", {})
            }

        try:
            # ---------------------------------------------------------
            # 2. SELECCIÓN DE SUJETO (TARGET USER) Y MEMORIA
            # ---------------------------------------------------------
            # Extraemos el objetivo del análisis. Si no viene, es el mismo usuario.
            target_user = kwargs.pop('target_user', user)
            
            # [NUEVO] Extraemos el historial de chat si viene en los parámetros
            historial_chat = kwargs.pop('historial', None)
            
            # [NUEVO] Extraemos override de contexto (Viene desde views.py)
            context_override = kwargs.pop('context_override', None)

            # ---------------------------------------------------------
            # 3. CONTEXT BUILDER (Extracción de datos SQL)
            # ---------------------------------------------------------
            if context_override:
                # Si la vista ya hizo el trabajo pesado (Tier 1000), usamos eso.
                contexto_json = context_override
            else:
                # Si no, dejamos que el builder construya el contexto estándar
                contexto_json = context_builder.get_context(
                    usuario=user,
                    action_type=action_type,
                    target_user=target_user,
                    **kwargs
                )
            
            if "error" in contexto_json:
                self._cerrar_ticket(
                    log_id=log_id,
                    exitoso=False,
                    error=contexto_json.get("error")
                )
                return {
                    "success": False, 
                    "content": f"Error de datos: {contexto_json.get('error')}", 
                    "source": "DATA_ERROR"
                }

            # INYECTAR LA PREGUNTA EN EL CONTEXTO
            # Si el usuario hace una pregunta específica, la añadimos al contexto
            if user_query:
                contexto_json['user_query_actual'] = user_query

            # ---------------------------------------------------------
            # 4. CACHE SEMÁNTICO (CONTROLADO)
            # ---------------------------------------------------------
            # Generamos la huella digital del contexto
            current_hash = ai_cache.calculate_hash(contexto_json)

            # 🔴 POLÍTICA "SIEMPRE FRESCO": Ignoramos caché de lectura para asegurar datos en tiempo real
            cache_result = None 

            if cache_result:
                self._cerrar_ticket(
                    log_id=log_id,
                    exitoso=True,
                    response_content=cache_result.get("content"),
                    context_hash=current_hash,
                    tokens_in=0,
                    tokens_out=0,
                    metadata_extra={
                        "source": "CACHE", 
                        "ahorro": True,
                        "cache_ref_date": str(cache_result.get("fecha"))
                    }
                )
                return {
                    "success": True,
                    "content": cache_result.get("content"),
                    "source": "CACHE",
                    "meta": {
                        "ahorro": True,
                        "context_hash": current_hash
                    }
                }

            # ---------------------------------------------------------
            # 5. PROMPT FACTORY (Construcción del lenguaje)
            # ---------------------------------------------------------
            # Ensamblamos el prompt final con el contexto (sea inyectado o construido)
            messages = prompt_factory.ensamblar_prompt(
                accion=action_type,
                contexto=contexto_json,
                user_query=user_query,
                historial=historial_chat # <--- CONEXIÓN DE MEMORIA APLICADA
            )

            # Configuración dinámica de la IA
            ai_config = {
                "temperature": 0.7, # Default
                "max_tokens": 2000 # Aumentado para soportar reportes largos
            }
            
            if action_type == ACCION_ANALISIS_CONVIVENCIA:
                ai_config["temperature"] = 0.2 # Más determinista
            
            # Sobrescribir si vienen parámetros específicos en kwargs
            if "temperature" in kwargs:
                ai_config["temperature"] = float(kwargs.pop("temperature"))

            # ---------------------------------------------------------
            # 6. CLIENTE IA (DeepSeek API Call)
            # ---------------------------------------------------------
            api_result = deepseek_client.get_completion(
                messages_list=messages,
                config=ai_config
            )

            usage = api_result.get("usage", {})

            # ---------------------------------------------------------
            # 7. CIERRE DE TICKET (Auditoría final)
            # ---------------------------------------------------------
            self._cerrar_ticket(
                log_id=log_id,
                exitoso=api_result.get("success", False),
                response_content=api_result.get("content"),
                error=api_result.get("error"),
                context_hash=current_hash, 
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                metadata_extra={
                    "request_id": api_result.get("request_id"),
                    "source": "API",
                    "target_user_id": target_user.id if hasattr(target_user, 'id') else None,
                    "model": MODEL_NAME
                }
            )

            if not api_result.get("success"):
                return {
                    "success": False,
                    "content": "Servicio de IA temporalmente no disponible.",
                    "source": "API_ERROR",
                    "debug": api_result.get("error")
                }

            return {
                "success": True,
                "content": api_result.get("content"),
                "source": "IA",
                "meta": usage
            }

        except Exception as e:
            logger.error("CRASH ORCHESTRATOR", exc_info=True)
            self._cerrar_ticket(
                log_id=log_id,
                exitoso=False,
                error=f"Error Crítico: {str(e)}"
            )
            return {
                "success": False,
                "content": "Error interno en el motor de IA institucional.",
                "source": "INTERNAL_ERROR"
            }

    def _cerrar_ticket(self, log_id, exitoso, response_content=None, error=None, 
                       context_hash=None, tokens_in=0, tokens_out=0, metadata_extra=None):
        """
        Actualiza el registro AIUsageLog para finalizar la auditoría técnica.
        """
        if not log_id:
            return

        try:
            log = AIUsageLog.objects.get(id=log_id)
            log.exitoso = exitoso
            log.tokens_entrada = tokens_in
            log.tokens_salida = tokens_out
            log.error_mensaje = error

            meta = log.metadata_tecnica or {}
            if context_hash: meta["context_hash"] = context_hash
            if response_content: meta["response_content"] = response_content
            if metadata_extra: meta.update(metadata_extra)

            log.metadata_tecnica = meta
            log.save(update_fields=[
                "exitoso", "tokens_entrada", "tokens_salida", 
                "error_mensaje", "metadata_tecnica"
            ])
        except AIUsageLog.DoesNotExist:
            logger.error(f"Ticket {log_id} no encontrado.")
        except Exception as e:
            logger.error(f"Error cerrando auditoría {log_id}: {e}")

# Instancia global
ai_orchestrator = AIOrchestrator()