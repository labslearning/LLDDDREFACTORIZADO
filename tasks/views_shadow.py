# tasks/views_shadow.py

import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.contrib.auth import get_user_model

# Importación explícita de modelos para evitar referencias circulares
from .models import (
    Nota, NotaDetallada, Observacion, Asistencia, 
    ActaInstitucional, Seguimiento, AIUsageLog, HistorialAcademico
)

User = get_user_model()

# ==========================================
# 📊 CONFIGURACIÓN DE BUSINESS INTELLIGENCE
# ==========================================
VALOR_PENSIÓN_MENSUAL = 450000  # COP
MESES_PERDIDA_PROMEDIO = 6      # Tiempo promedio que tarda en llenarse un cupo
COSTO_LITIGIO_BASE = 5000000    # Costo estimado de una demanda/tutela

# ==========================================
# 🤖 ECONOMÍA DE APIS (MICRO-COSTOS)
# ==========================================
# Precios basados en el estándar de DeepSeek/OpenAI (ajustar según proveedor)
COSTO_INPUT_1M = 0.14   # USD por 1M tokens entrada
COSTO_OUTPUT_1M = 0.28  # USD por 1M tokens salida

def is_staff_or_superuser(user):
    """Verifica privilegios administrativos de alto nivel."""
    return user.is_active and (user.is_staff or user.is_superuser)

@login_required
@user_passes_test(is_staff_or_superuser)
def shadow_tenant_dashboard(request):
    """
    🛡️ COMMAND CENTER: TORRE DE CONTROL DE RIESGO
    Visualización estratégica de riesgos académicos, financieros y operativos.
    """
    # ---------------------------------------------------------
    # 1. MOTOR DE RIESGO (DETECCIÓN TEMPRANA)
    # ---------------------------------------------------------
    umbral_academico = 3.2
    
    # Detección en sistema de notas antiguo
    ids_legacy = set(
        Nota.objects.values('estudiante')
        .annotate(promedio=Avg('valor'))
        .filter(promedio__lt=umbral_academico)
        .values_list('estudiante', flat=True)
    )
    
    # Detección en sistema de notas moderno (Rúbricas)
    ids_modern = set(
        NotaDetallada.objects.values('estudiante')
        .annotate(promedio=Avg('valor'))
        .filter(promedio__lt=umbral_academico)
        .values_list('estudiante', flat=True)
    )
    ids_academico = ids_legacy | ids_modern
    
    # Riesgo Legal: Tipos de falta graves
    ids_legal = set(
        Observacion.objects.filter(tipo__in=['CONVIVENCIA', '2', '3'])
        .values_list('estudiante', flat=True)
    )
    
    # Riesgo Ausentismo: Más de 5 fallas injustificadas
    ids_ausentismo = set(
        Asistencia.objects.filter(estado='FALLA')
        .values('estudiante')
        .annotate(total_fallas=Count('id'))
        .filter(total_fallas__gte=5)
        .values_list('estudiante', flat=True)
    )

    # ---------------------------------------------------------
    # 2. FILTRO DE GESTIÓN (NETEO DE RIESGO)
    # ---------------------------------------------------------
    # Si hubo seguimiento en los últimos 15 días, el riesgo está "Mitigado"
    fecha_limite = timezone.now() - timedelta(days=15)
    ids_atendidos = set(
        Seguimiento.objects.filter(fecha__gte=fecha_limite)
        .values_list('estudiante', flat=True)
    )
    
    total_riesgo_ids = ids_academico | ids_legal | ids_ausentismo
    riesgo_neto_ids = total_riesgo_ids - ids_atendidos
    
    # ---------------------------------------------------------
    # 3. IMPACTO FINANCIERO (FORECASTING)
    # ---------------------------------------------------------
    count_riesgo_neto = len(riesgo_neto_ids)
    
    # Dinero en riesgo por posible deserción
    kpi_dinero = count_riesgo_neto * VALOR_PENSIÓN_MENSUAL * MESES_PERDIDA_PROMEDIO
    
    # Riesgo legal latente (casos legales sin atender)
    casos_legales_abiertos = len(ids_legal - ids_atendidos)
    kpi_legal = (casos_legales_abiertos * 0.20) * COSTO_LITIGIO_BASE # Asumiendo 20% probabilidad de escalamiento

    # Tasa de Riesgo Global
    total_alumnos = User.objects.filter(perfil__rol='ESTUDIANTE').count() or 1
    tasa_riesgo = round((count_riesgo_neto / total_alumnos) * 100, 1)

    # ---------------------------------------------------------
    # 4. AUDITORÍA DE COSTOS IA (CONTROL FINANCIERO)
    # ---------------------------------------------------------
    logs_mes = AIUsageLog.objects.filter(fecha__month=timezone.now().month)
    
    # Agregación segura manejando posibles nulos
    metricas_ia = logs_mes.aggregate(
        total_in=Sum('tokens_entrada'),
        total_out=Sum('tokens_salida')
    )
    
    tokens_in = metricas_ia['total_in'] or 0
    tokens_out = metricas_ia['total_out'] or 0
    
    costo_mes_ia = (
        (tokens_in / 1_000_000) * COSTO_INPUT_1M +
        (tokens_out / 1_000_000) * COSTO_OUTPUT_1M
    )

    # ---------------------------------------------------------
    # 5. CONTEXTO DE OPERACIÓN
    # ---------------------------------------------------------
    ultimos_casos = ActaInstitucional.objects.select_related('implicado__perfil').order_by('-fecha')[:8]

    context = {
        "kpis": {
            "dinero": kpi_dinero,
            "legal": kpi_legal,
            "total_riesgo": count_riesgo_neto,
            "riesgo_mitigado": len(total_riesgo_ids) - count_riesgo_neto,
            "tasa_riesgo": tasa_riesgo,
            "costo_ia_mes": round(costo_mes_ia, 4),
            "tokens_totales": tokens_in + tokens_out
        },
        "conteos": {
            "academico": len(ids_academico),
            "legal": len(ids_legal),
            "ausentismo": len(ids_ausentismo)
        },
        "ultimos_casos": ultimos_casos,
        "config": {
            "pension": VALOR_PENSIÓN_MENSUAL, 
            "meses": MESES_PERDIDA_PROMEDIO
        },
        "fecha_corte": timezone.now()
    }
    return render(request, 'admin/shadow_dashboard.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def shadow_case_detail(request, acta_id):
    """
    📂 DOSSIER FORENSE 360° - NIVEL TÉCNICO PROFUNDO (MAX LEVEL)
    Investigación que revela la "Caja Negra" de la IA: Prompts, Respuestas crudas y Micro-economía.
    """
    acta = get_object_or_404(ActaInstitucional, id=acta_id)
    estudiante = acta.implicado

    # ---------------------------------------------------------
    # 1. FUSIÓN DE DATOS HISTÓRICOS (DATA FUSION)
    # ---------------------------------------------------------
    seguimientos = Seguimiento.objects.filter(estudiante=estudiante).select_related('profesional').order_by('-fecha')
    otras_actas = ActaInstitucional.objects.filter(implicado=estudiante).exclude(id=acta.id).order_by('-fecha')
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')

    # ---------------------------------------------------------
    # 2. CALIFICACIÓN DE PERFIL (SCORING)
    # ---------------------------------------------------------
    notas_legacy = Nota.objects.filter(estudiante=estudiante)
    notas_new = NotaDetallada.objects.filter(estudiante=estudiante)
    
    # Cálculo robusto de promedio (Manejo de nulos)
    avg_legacy = notas_legacy.aggregate(Avg('valor'))['valor__avg'] or 0
    avg_new = notas_new.aggregate(Avg('valor'))['valor__avg'] or 0
    promedio = avg_new if avg_new > 0 else avg_legacy
    
    # Conteo de indicadores negativos
    perdidas = notas_legacy.filter(valor__lt=3.5).count() + notas_new.filter(valor__lt=3.5).count()
    graves = observaciones.filter(tipo__in=['CONVIVENCIA', '2', '3']).count()
    fallas = Asistencia.objects.filter(estudiante=estudiante, estado='FALLA').count()

    # ---------------------------------------------------------
    # 3. SISTEMA EXPERTO DE RECOMENDACIÓN
    # ---------------------------------------------------------
    if perdidas >= 3 or graves >= 1 or fallas >= 8:
        nivel, color, accion = "CRÍTICO", "danger", "⚠️ ACTIVAR RUTA DE PERMANENCIA (RIESGO DESERCIÓN INMINENTE)."
    elif perdidas >= 1 or fallas >= 3:
        nivel, color, accion = "ALERTA", "warning", "Se requiere compromiso académico y citación inmediata a acudientes."
    else:
        nivel, color, accion = "BAJO", "success", "Continuar monitoreo preventivo regular."

    # ---------------------------------------------------------
    # 4. ANÁLISIS FORENSE DE IA (CAJA NEGRA DESBLOQUEADA)
    # ---------------------------------------------------------
    ai_logs = AIUsageLog.objects.filter(usuario=request.user).order_by('-fecha')[:5]

    audit_data = []
    total_gasto_caso = 0.0
    total_tokens_caso = 0
    
    for log in ai_logs:
        # A. Extracción de Métricas Crudas
        t_in = log.tokens_entrada or 0
        t_out = log.tokens_salida or 0
        modelo = log.modelo_utilizado or "modelo-desconocido"
        
        # B. Micro-Costing (Cálculo Financiero de Alta Precisión)
        cost_in = (t_in / 1_000_000) * COSTO_INPUT_1M
        cost_out = (t_out / 1_000_000) * COSTO_OUTPUT_1M
        cost_log = cost_in + cost_out
        
        total_gasto_caso += cost_log
        total_tokens_caso += (t_in + t_out)
        
        # C. Decodificación de la "Caja Negra" (Prompts y Respuestas)
        meta_raw = log.metadata_tecnica
        prompt_structure = [] # Lista para almacenar mensajes [System, User, Assistant]
        response_text = "N/A"

        try:
            # 1. Normalizar Metadata a Diccionario
            if isinstance(meta_raw, str):
                # Si viene como string JSON, lo parseamos
                try:
                    meta_data = json.loads(meta_raw)
                except json.JSONDecodeError:
                    meta_data = {"error": "JSON Inválido", "raw_content": meta_raw}
            else:
                # Si ya es dict o None
                meta_data = meta_raw or {}

            # 2. Extraer Estructura de Chat (System vs User)
            if 'messages' in meta_data and isinstance(meta_data['messages'], list):
                # Formato estándar de Chat Completion (OpenAI/DeepSeek)
                prompt_structure = meta_data['messages'] 
            elif 'prompt' in meta_data:
                # Formato legacy o simple
                prompt_structure = [{'role': 'user', 'content': meta_data['prompt']}]
            else:
                # Fallback: Usar la acción como prompt
                prompt_structure = [{'role': 'system/action', 'content': str(log.accion)}]

            # 3. Extraer Respuesta
            response_text = meta_data.get('response', meta_data.get('full_response', 'Respuesta no registrada en metadata'))

        except Exception as e:
            prompt_structure = [{'role': 'error', 'content': f"Fallo crítico al leer metadata: {str(e)}"}]

        # D. Construcción del Objeto Forense
        audit_data.append({
            'id': log.id,
            'timestamp': log.fecha,
            'modelo': modelo,
            'status': '✅ 200 OK' if log.exitoso else '❌ 500 ERROR',
            'tokens': {
                'in': t_in,
                'out': t_out,
                'total': t_in + t_out
            },
            'financial': {
                'cost_in': f"{cost_in:.7f}",   # Formato string para preservar decimales en HTML
                'cost_out': f"{cost_out:.7f}",
                'total_usd': f"{cost_log:.7f}"
            },
            'black_box': {
                'prompts': prompt_structure, # Pasamos la lista completa para iterar en template
                'response': response_text
            }
        })

    # ---------------------------------------------------------
    # 5. CONSTRUCCIÓN DEL CONTEXTO FINAL
    # ---------------------------------------------------------
    context = {
        "acta": acta,
        "estudiante": estudiante,
        "dossier": {
            "seguimientos": seguimientos,
            "otras_actas": otras_actas,
            "observaciones_recent": observaciones[:5],
            "total_observaciones": observaciones.count()
        },
        "metrics": {
            "promedio": round(promedio, 2),
            "perdidas": perdidas,
            "graves": graves,
            "fallas": fallas
        },
        "estado": {
            "nivel": nivel, 
            "color": color, 
            "accion": accion
        },
        # DATA FORENSE EXPUESTA PARA EL TEMPLATE "MATRIX"
        "ai_forensics": {
            "logs": audit_data,
            "total_gasto_usd": f"{total_gasto_caso:.6f}", # String formateado
            "total_tokens": total_tokens_caso
        }
    }
    return render(request, 'admin/shadow_case_detail.html', context)