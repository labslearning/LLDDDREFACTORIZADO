# tasks/ai/constants.py
# ==============================================================================
# VOCABULARIO OFICIAL DE IA - PROYECTO EDUCATIVO INSTITUCIONAL (PEI)
# ==============================================================================
# Este archivo define TODOS los términos permitidos para el uso de IA.
# Integra las funciones administrativas (Legacy) con las nuevas pedagógicas.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. ROLES INSTITUCIONALES
# ------------------------------------------------------------------------------
ROL_PROFESOR = 'DOCENTE'
ROL_ESTUDIANTE = 'ESTUDIANTE'
ROL_ACUDIENTE = 'ACUDIENTE'
ROL_STAFF = 'STAFF'              # Psicología, Coordinación, Orientación
ROL_ADMIN = 'ADMINISTRADOR'

ROLES_IA_PERMITIDOS = [
    ROL_PROFESOR,
    ROL_ESTUDIANTE,
    ROL_ACUDIENTE,
    ROL_STAFF,
    ROL_ADMIN,
]

# ------------------------------------------------------------------------------
# 2. ACCIONES (INTENTS) DE LA IA
# ------------------------------------------------------------------------------

# --- A. Perfil Estudiante (NUEVOS BOTONES + LEGACY) ---
# Actualizamos 'mejoras_estudiante' a 'est_mejoras' para coincidir con tu nuevo Frontend
ACCION_MEJORAS_ESTUDIANTE = 'est_mejoras'       # Botón 1: Análisis Integral
ACCION_TUTOR_PARETO = 'est_pareto'              # Botón 2: Tutor 80/20 (NUEVO)
ACCION_NIVELACION_ACADEMICA = 'est_nivelacion'  # Botón 3: Plan de Rescate (NUEVO)
ACCION_CHAT_SOCRATICO = 'chat_socratico'        # Mantenido por compatibilidad histórica

# --- B. Perfil Docente (NUEVOS BOTONES + LEGACY) ---
ACCION_DOCENTE_GRUPO = 'doc_grupo'              # Análisis Macro del Salón (NUEVO)
ACCION_DOCENTE_INDIVIDUAL = 'doc_individual'    # Mentoría Alumno Específico (NUEVO)
ACCION_MEJORAS_DOCENTE = 'mejoras_docente'      # Legacy
ACCION_ORIENTACION_CURSO = 'orientacion_curso'  # Legacy

# --- C. Perfil Acudiente ---
ACCION_APOYO_ACUDIENTE = 'apoyo_acudiente'

# --- D. Perfil Staff / Institucional (Globales) ---
ACCION_MEJORA_STAFF_ACADEMICO = 'staff_academico'
ACCION_ANALISIS_CONVIVENCIA = 'analisis_convivencia'
ACCION_CUMPLIMIENTO_PEI = 'cumplimiento_pei'
ACCION_ANALISIS_GLOBAL_BIENESTAR = 'analisis_global_bienestar'
ACCION_RIESGO_ACADEMICO = 'riesgo_academico_global'

# === LISTA MAESTRA DE SEGURIDAD (TODO PERMITIDO) ===
ACCIONES_IA_PERMITIDAS = [
    # Estudiante
    ACCION_MEJORAS_ESTUDIANTE,
    ACCION_TUTOR_PARETO,            # <--- Importante para evitar NameError
    ACCION_NIVELACION_ACADEMICA,    # <--- Importante para evitar NameError
    ACCION_CHAT_SOCRATICO,
    
    # Docente
    ACCION_DOCENTE_GRUPO,
    ACCION_DOCENTE_INDIVIDUAL,
    ACCION_MEJORAS_DOCENTE,
    ACCION_ORIENTACION_CURSO,
    
    # Acudiente
    ACCION_APOYO_ACUDIENTE,
    
    # Administrativo / Staff
    ACCION_MEJORA_STAFF_ACADEMICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI,
    ACCION_ANALISIS_GLOBAL_BIENESTAR,
    ACCION_RIESGO_ACADEMICO
]

# ------------------------------------------------------------------------------
# 3. OPCIONES PARA FRONTEND (Visualización en Dashboards)
# ------------------------------------------------------------------------------
OPCIONES_ACCIONES_IA = (
    # Estudiante
    (ACCION_MEJORAS_ESTUDIANTE, 'Plan de Mejora Individual'),
    (ACCION_TUTOR_PARETO, 'Tutoría Pareto 80/20'),
    (ACCION_NIVELACION_ACADEMICA, 'Plan de Rescate Académico'),
    (ACCION_CHAT_SOCRATICO, 'Chat Socrático (Clásico)'),
    
    # Docente
    (ACCION_DOCENTE_GRUPO, 'Análisis Grupal'),
    (ACCION_DOCENTE_INDIVIDUAL, 'Mentoría Individual'),
    (ACCION_MEJORAS_DOCENTE, 'Estrategias por Curso'),
    
    # Administrativos
    (ACCION_APOYO_ACUDIENTE, 'Guía de Apoyo en Casa'),
    (ACCION_MEJORA_STAFF_ACADEMICO, 'Reporte Académico Global'),
    (ACCION_ANALISIS_CONVIVENCIA, 'Reporte de Convivencia'),
    (ACCION_CUMPLIMIENTO_PEI, 'Auditoría PEI'),
    (ACCION_ANALISIS_GLOBAL_BIENESTAR, 'Radiografía de Bienestar'),
    (ACCION_RIESGO_ACADEMICO, 'Mapa de Riesgo'),
)

# ------------------------------------------------------------------------------
# 4. TIPOS DE DOCUMENTOS GENERADOS
# ------------------------------------------------------------------------------
DOC_REPORTE_PEDAGOGICO = 'reporte_pedagogico'
DOC_ORIENTACION_ESTUDIANTE = 'orientacion_estudiante'
DOC_ORIENTACION_ACUDIENTE = 'orientacion_acudiente'
DOC_REPORTE_CONVIVENCIA = 'reporte_convivencia'
DOC_REPORTE_INSTITUCIONAL = 'reporte_institucional'
DOC_AUDITORIA_PEI = 'reporte_auditoria_pei'

DOCUMENTOS_IA_PERMITIDOS = [
    DOC_REPORTE_PEDAGOGICO,
    DOC_ORIENTACION_ESTUDIANTE,
    DOC_ORIENTACION_ACUDIENTE,
    DOC_REPORTE_CONVIVENCIA,
    DOC_REPORTE_INSTITUCIONAL,
    DOC_AUDITORIA_PEI,
]

# ------------------------------------------------------------------------------
# 5. CONFIGURACIÓN TÉCNICA
# ------------------------------------------------------------------------------
MODEL_NAME = 'deepseek-chat' 
MAX_TOKENS = 2500           # Aumentado para soportar explicaciones largas
MAX_TOKENS_PER_REQUEST = 4000 # Límite duro de la API
TEMPERATURE = 0.7           # Balance entre creatividad y precisión