# tasks/ai_views.py

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

# IMPORTANTE: Importamos el Orquestador REAL y la constante para el chat por defecto
from .ai.orchestrator import ai_orchestrator 
from .ai.constants import ACCION_TUTOR_PARETO

# Configuramos un logger profesional
logger = logging.getLogger(__name__)
User = get_user_model()

# ==============================================================================
# 🔌 VISTA / API ENDPOINT (CEREBRO REAL + CHAT CONTINUO)
# ==============================================================================

@csrf_exempt
@login_required
def api_ai_agent(request):
    """
    Endpoint inteligente: Maneja acciones directas (Botones) y Conversación Continua.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'content': 'Método no permitido.'}, status=405)

    try:
        data = json.loads(request.body)
        
        # 1. Recuperamos datos básicos
        action_type = data.get('action_type')
        user_query = data.get('query', '')
        params = data.get('params', {})
        
        # 2. Recuperamos el historial (Memoria de chat)
        # Esto permite que la IA recuerde la "Pregunta Socrática" anterior
        historial = data.get('historial', []) 

        # 3. LÓGICA DE CONTINUIDAD (EL ARREGLO CLAVE)
        # Si el usuario solo escribe texto (responde a la pregunta) sin hundir un botón,
        # asumimos que está hablando con el Tutor Pareto.
        if not action_type and user_query:
            action_type = ACCION_TUTOR_PARETO

        # Si después de esto sigue sin haber acción, entonces sí es un error
        if not action_type:
            return JsonResponse({'success': False, 'content': 'Falta el tipo de acción o mensaje.'}, status=400)

        # 4. Validación de permisos para profesores/admin (Ver datos de otros)
        target_user_id = params.get('target_user_id')
        if target_user_id:
            # Solo docentes o staff pueden consultar datos de otros
            es_profesor = request.user.groups.filter(name='Docentes').exists()
            es_admin = request.user.is_staff
            
            if not (es_profesor or es_admin):
                 return JsonResponse({'success': False, 'content': '⛔ Acceso denegado.'}, status=403)
            
            try:
                # Reemplazamos el ID por el objeto usuario real para el orquestador
                params['target_user'] = User.objects.get(id=target_user_id)
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'content': 'Usuario no encontrado.'}, status=404)

        # 5. EJECUCIÓN (ORQUESTADOR)
        # Llamamos al cerebro con todos los datos, incluido el historial
        response_data = ai_orchestrator.process_request(
            user=request.user,
            action_type=action_type,
            user_query=user_query,
            historial=historial, # Pasamos la memoria al cerebro
            **params
        )
        
        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'content': 'Error: JSON inválido.'}, status=400)
        
    except Exception as e:
        logger.error(f"🔥 Error Crítico en AI View: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'content': 'Error interno del sistema de IA.'}, status=500)