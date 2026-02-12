# tasks/ai/prompts.py
import json

# Importación robusta: Intenta cargar todo, maneja fallos de legacy si ocurren
try:
    from .constants import (
        ACCION_MEJORAS_ESTUDIANTE,
        ACCION_TUTOR_PARETO,
        ACCION_NIVELACION_ACADEMICA,
        ACCION_DOCENTE_GRUPO,
        ACCION_DOCENTE_INDIVIDUAL,
        # Legacy
        ACCION_APOYO_ACUDIENTE,
        ACCION_MEJORA_STAFF_ACADEMICO,
        ACCION_ANALISIS_CONVIVENCIA,
        ACCION_CUMPLIMIENTO_PEI,
        ACCION_ANALISIS_GLOBAL_BIENESTAR,
        ACCION_RIESGO_ACADEMICO
    )
except ImportError:
    # Fallback de seguridad por si alguna constante falta
    from .constants import *

class PromptFactory:
    """
    FÁBRICA DE INSTRUCCIONES INSTITUCIONAL (EDITION: IA DE APRENDIZAJE PRO).
    Define la personalidad, el tono pedagógico y las reglas estrictas de salida.
    """

    def crear_mensaje_sistema(self, contexto):
        """Define la identidad inmutable y las reglas de formato."""
        system_instruction = contexto.get('system_instruction', "Eres un asistente educativo de alto nivel.")
        
        return (
            f"{system_instruction}\n"
            f"DIRECTRIZ SUPREMA: Tu respuesta es EXCLUSIVAMENTE para el ESTUDIANTE o DOCENTE. "
            f"⛔ PROHIBIDO IMPRIMIR EL ANÁLISIS INTERNO: No muestres bloques de 'Diagnóstico', 'Análisis de Datos', 'Modo identificado' o metadatos internos. "
            f"Ve DIRECTO al contenido educativo o respuesta útil.\n"
            f"FORMATO: Usa Markdown profesional (Negritas, Títulos, Listas).\n"
        )

    def ensamblar_prompt(self, accion, contexto, user_query=None):
        """Construye la cadena de mensajes optimizada para DeepSeek/LLM."""
        
        # 1. Identidad y Reglas del Juego
        system_content = self.crear_mensaje_sistema(contexto)
        
        # 2. Inyección de Datos (Context Injection)
        # Limpiamos el contexto para no confundir a la IA con instrucciones duplicadas
        datos_para_ia = {k: v for k, v in contexto.items() if k != 'system_instruction'}
        datos_json = json.dumps(datos_para_ia, ensure_ascii=False, indent=2)
        
        context_block = (
            f"\n\n[DATOS DISPONIBLES - CONTEXTO OCULTO]\n"
            f"```json\n{datos_json}\n```\n"
            f"Usa estos datos para personalizar, pero NO menciones explícitamente que estás leyendo un JSON."
        )

        messages = [
            {"role": "system", "content": system_content + context_block}
        ]

        # 3. SELECCIÓN DE GUIONES DE ALTO NIVEL (PROMPTS)
        
        # --- ESTUDIANTE: ANÁLISIS INTEGRAL (Botón 1) ---
        if accion == ACCION_MEJORAS_ESTUDIANTE:
            user_content = self._prompt_mejoras_estudiante()

        # --- ESTUDIANTE: TUTOR PARETO (Botón 2 - CORREGIDO) ---
        elif accion == ACCION_TUTOR_PARETO:
            user_content = self._prompt_tutor_pareto(user_query)

        # --- ESTUDIANTE: NIVELACIÓN / RESCATE (Botón 3 - DETALLADO) ---
        elif accion == ACCION_NIVELACION_ACADEMICA:
            user_content = self._prompt_nivelacion_academica()

        # --- DOCENTE: ANÁLISIS DE GRUPO ---
        elif accion == ACCION_DOCENTE_GRUPO:
            user_content = self._prompt_docente_grupo()
            
        # --- DOCENTE: MENTORÍA INDIVIDUAL ---
        elif accion == ACCION_DOCENTE_INDIVIDUAL:
             user_content = self._prompt_docente_individual()

        # --- ROLES ADMINISTRATIVOS / LEGACY ---
        elif accion == ACCION_APOYO_ACUDIENTE:
            user_content = self._prompt_apoyo_acudiente()
        elif accion == ACCION_MEJORA_STAFF_ACADEMICO:
            user_content = self._prompt_staff_academico()
        elif accion == ACCION_ANALISIS_CONVIVENCIA:
            user_content = self._prompt_convivencia()
        elif accion == ACCION_CUMPLIMIENTO_PEI:
            user_content = self._prompt_auditoria_admin()
        elif accion == ACCION_ANALISIS_GLOBAL_BIENESTAR:
            user_content = self._prompt_bienestar_global()
        elif accion == ACCION_RIESGO_ACADEMICO:
            user_content = self._prompt_riesgo_academico()
            
        else:
            user_content = f"CONSULTA: {user_query or 'Analiza la información.'}"

        messages.append({"role": "user", "content": user_content})
        return messages

    # ==================================================================
    # 🧠 GUIONES PEDAGÓGICOS PERSONALIZADOS
    # ==================================================================

    def _prompt_mejoras_estudiante(self):
        return (
            "📌 TAREA: Actúa como mi Orientador Personal.\n"
            "1. Analiza mis notas ('boletin_actual') y observaciones ('historial_disciplinario').\n"
            "2. Cruza esta información con el Manual de Convivencia.\n"
            "3. Dime DIRECTAMENTE: ¿Qué estoy haciendo bien y dónde estoy fallando?\n"
            "4. Dame 3 consejos prácticos (Conductuales y Académicos)."
        )

    def _prompt_tutor_pareto(self, query):
        """
        Estructura forzada: Imaginación -> Teoría -> Pregunta.
        """
        pregunta = query if query else "un tema interesante"
        return (
            f"🎓 TEMA A ENSEÑAR: '{pregunta}'\n\n"
            "⚠️ REGLAS OBLIGATORIAS DE RESPUESTA (NO HAGAS DIAGNÓSTICOS PREVIOS):\n"
            "Debes responder ÚNICAMENTE siguiendo estos 3 pasos, sin saludos ni introducciones técnicas:\n\n"
            "**1. 🌀 IMAGINA ESTO (Analogía/Historia):**\n"
            "Empieza conectando el tema con una situación de la vida real, una metáfora visual o una historia breve que sirva de gancho. (Ej: 'Imagina que vas en un auto...').\n\n"
            "**2. 🧠 EL CONCEPTO CLAVE (Teoría Sólida):**\n"
            "Explica el fundamento teórico con rigor y profundidad. Define los términos técnicos y explica el 'por qué' de las cosas (Usa el Principio de Pareto: el 20% esencial que explica el 80% del funcionamiento).\n\n"
            "**3. ❓ PREGUNTA SOCRÁTICA:**\n"
            "Finaliza con UNA sola pregunta reflexiva que obligue a aplicar lo aprendido (no esperes respuesta, solo déjala planteada).\n\n"
            "🚫 PROHIBIDO: No menciones mis notas, ni digas 'Diagnóstico', 'Análisis' o 'Aquí tienes tu respuesta'. Ve directo al grano."
        )

    def _prompt_nivelacion_academica(self):
        """
        Instrucción detallada para leer Temas, Subtemas y Logros de notas bajas.
        """
        return (
            "🚑 **PLAN DE RESCATE ACADÉMICO PERSONALIZADO**\n\n"
            "Tu misión es realizar una autopsia académica de mis notas bajas para salvar el periodo.\n"
            "1. **ANÁLISIS DE DETALLE**: Revisa las 'fallas_detectadas' en el JSON. No mires solo el nombre de la materia; busca en la descripción el **TEMA, SUBTEMA y LOGRO** específico donde fallé.\n"
            "2. **DIAGNÓSTICO PRECISO**: Dime exactamente qué no estoy entendiendo. (Ej: 'En Matemáticas, tu nota de 2.5 indica que fallaste específicamente en el subtema de Factorización').\n"
            "3. **MICRO-ESTRATEGIA**: Para ese tema específico, dame una técnica de estudio concreta o recurso rápido.\n"
            "🔥 **OBLIGATORIO**: Debes terminar tu respuesta con esta frase exacta:\n"
            "**'¿Con cuál de estas materias quieres iniciar tu recuperación hoy?'**"
        )

    def _prompt_docente_grupo(self):
        return (
            "📊 CONSULTORÍA PEDAGÓGICA:\n"
            "Analiza estadísticas y temas críticos del curso.\n"
            "1. Diagnóstico breve.\n"
            "2. 2 Estrategias didácticas concretas.\n"
            "3. Sugerencia de clima de aula."
        )

    def _prompt_docente_individual(self):
         return (
             "👨‍🏫 MENTORÍA INDIVIDUAL:\n"
             "Analiza las notas del alumno.\n"
             "Genera guion de feedback: Logro -> Área de Mejora -> Compromiso."
         )

    # --- GUIONES LEGACY / ADMINISTRATIVOS (MANTENIDOS) ---

    def _prompt_apoyo_acudiente(self):
        return (
            "Dirígete al padre de familia con empatía. Traduce el JSON técnico a lenguaje humano.\n"
            "Crea una 'Guía de Apoyo Familiar':\n"
            "1. Resumen de Logros (Lo positivo).\n"
            "2. Semáforo de Alerta (Dónde necesita ayuda).\n"
            "3. Consejos para Casa: 3 acciones simples."
        )

    def _prompt_staff_academico(self):
        return (
            "Analista Académico: Revisa tendencias globales.\n"
            "¿Existe un problema sistémico en alguna materia o grado?\n"
            "Propón una estrategia de nivelación institucional alineada con el PEI."
        )

    def _prompt_convivencia(self):
        return (
            "Analista de Convivencia: Revisa anotaciones y tipologías.\n"
            "1. Clasifica el clima escolar.\n"
            "2. Identifica patrones (agresión, bullying, liderazgo).\n"
            "3. Sugiere intervención basada en Justicia Restaurativa."
        )

    def _prompt_auditoria_admin(self):
        return (
            "**INFORME EJECUTIVO DE AUDITORÍA (ISO 21001)**\n"
            "Analiza los KPIs institucionales.\n"
            "1. ¿Estamos cumpliendo la visión de excelencia?\n"
            "2. Alertas de Deserción o Riesgo.\n"
            "3. Acciones Estratégicas para Rectoría."
        )
    
    def _prompt_bienestar_global(self):
        return (
            "**RADIOGRAFÍA DE BIENESTAR**\n"
            "Analiza los datos globales de convivencia.\n"
            "Identifica focos rojos y propón campañas de prevención."
        )

    def _prompt_riesgo_academico(self):
        return (
            "**MAPA DE RIESGO ACADÉMICO**\n"
            "Identifica estudiantes con pérdida crítica de materias.\n"
            "Sugiere intervenciones inmediatas para evitar la reprobación del año."
        )

# Instancia global lista para usar
prompt_factory = PromptFactory()