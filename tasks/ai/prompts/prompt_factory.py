# tasks/ai/prompts/prompt_factory.py

import json

# Importación robusta de TODAS las constantes (Nuevas y Viejas)
try:
    from tasks.ai.constants import (
        # Nuevas (Estudiante/Docente)
        ACCION_MEJORAS_ESTUDIANTE,
        ACCION_TUTOR_PARETO,
        ACCION_NIVELACION_ACADEMICA,
        ACCION_DOCENTE_GRUPO,
        ACCION_DOCENTE_INDIVIDUAL,
        # Legacy / Admin
        ACCION_CHAT_SOCRATICO,
        ACCION_APOYO_ACUDIENTE,
        ACCION_MEJORA_STAFF_ACADEMICO,
        ACCION_ANALISIS_CONVIVENCIA,
        ACCION_CUMPLIMIENTO_PEI,
        ACCION_ANALISIS_GLOBAL_BIENESTAR,
        ACCION_RIESGO_ACADEMICO
    )
except ImportError:
    # Fallback por si la estructura de carpetas cambia
    from ..constants import *

class PromptFactory:
    """
    FÁBRICA DE PROMPTS (CEREBRO ADAPTATIVO V6 - BIENESTAR PROFUNDO).
    Maneja personalidad, seguridad de datos, formatos pedagógicos estrictos
    e integración de diagramas visuales.
    """

    def ensamblar_prompt(self, accion, contexto, user_query=None, historial=None):

        # =====================================================
        # 0. DETECCIÓN SEGURA DE ROL Y PREPARACIÓN DE DATOS
        # =====================================================
        sujeto = contexto.get("sujeto_analizado", {})
        rol_usuario = sujeto.get("rol", "INSTITUCIONAL")

        # Serialización limpia de datos para la IA
        datos_clean = {k: v for k, v in contexto.items() if k != 'system_instruction'}
        data_str = json.dumps(datos_clean, indent=2, ensure_ascii=False)

        # =====================================================
        # 1. SYSTEM PROMPT (PERSONALIDAD, ESTÉTICA Y DIAGRAMAS)
        # =====================================================
        
        # A. MODO ESTUDIANTE: TUTOR SOCRÁTICO (VISUAL)
        if accion == ACCION_TUTOR_PARETO:
            # Usamos triple comilla para evitar errores de sintaxis
            system_content = """
Eres un Tutor Socrático Experto con enfoque en Aprendizaje Significativo y Visual.

🎨 **DIRECTRICES DE DISEÑO:**
1. Tu respuesta debe ser VISUALMENTE HERMOSA: usa emojis, negritas y listas.
2. **DIAGRAMAS:** Si explicas un concepto físico, biológico o estructural, DEBES insertar una etiqueta en el formato `

[Image of X]
` donde X es el término de búsqueda en inglés para el diagrama. Ejemplo: Si explicas la célula, añade `

[Image of animal cell diagram]
`.
3. No abuses de los diagramas, úsalos solo si aportan valor educativo.

⛔ **REGLAS DE SILENCIO (CRÍTICO):**
- NO imprimas 'Diagnóstico', 'Análisis', ni 'Pensamiento'.
- NO saludes con frases vacías. Empieza directo con el contenido.
"""

        # B. MODO ESTUDIANTE: PLAN DE RESCATE (COACH)
        elif accion == ACCION_NIVELACION_ACADEMICA:
            system_content = """
Eres un Entrenador Académico de Rescate (Academic Coach).
Tu objetivo es identificar lagunas de conocimiento específicas (Temas/Subtemas) y proponer soluciones inmediatas.

⛔ REGLAS DE SILENCIO: No expliques qué datos estás leyendo. Ve al grano.
"""

        # C. MODO ESTUDIANTE: MEJORAS (ORIENTADOR)
        elif accion == ACCION_MEJORAS_ESTUDIANTE:
            system_content = """
Eres un Orientador Escolar y Coach de Vida.
Analizas el rendimiento integral. Tu tono es motivador, gamificado y directo.
"""

        # D. MODO INSTITUCIONAL (BIENESTAR Y CONVIVENCIA - PROFUNDO)
        elif accion == ACCION_ANALISIS_GLOBAL_BIENESTAR:
            system_content = """
Eres un Consultor Senior en Clima Escolar y Bienestar Institucional.
Tu misión es generar un **INFORME EJECUTIVO DE ALTO NIVEL** basado en datos.

OBJETIVOS:
1. Analizar la salud emocional y convivencia de la institución.
2. Identificar patrones ocultos en los datos (tipos de faltas, tendencias temporales).
3. Proponer una **HOJA DE RUTA ESTRATÉGICA** para la mejora del bienestar.

TONO: Profesional, Empático, Analítico y Solucionador.
FORMATO: Extenso, detallado y estructurado con Markdown profesional.
"""

        # E. MODO INSTITUCIONAL (CONVIVENCIA / ADMIN GENERAL)
        elif accion == ACCION_ANALISIS_CONVIVENCIA:
            system_content = """
Eres un CONSULTOR EDUCATIVO INSTITUCIONAL.
FORMATO OBLIGATORIO:
### 🧠 Diagnóstico Institucional
### 📊 Hallazgos Clave
### 🎯 Estrategias de Prevención
"""

        # F. DEFAULT (OTROS)
        else:
            system_content = "Eres un Asistente Educativo Institucional. Basa tus respuestas en los datos JSON."

        system_message = {"role": "system", "content": system_content.strip()}

        # =====================================================
        # 2. USER PROMPT (INSTRUCCIÓN ESPECÍFICA + DATOS)
        # =====================================================

        context_block = f"\n\n[CONTEXTO DE DATOS OCULTO]\n```json\n{data_str}\n```\n"

        # --- 🟢 BOTÓN 2: TUTOR SOCRÁTICO (ESTÉTICO + 40% + DIAGRAMAS) ---
        if accion == ACCION_TUTOR_PARETO:
            pregunta = user_query if user_query else "un tema interesante"
            specific_instruction = f"""
🎓 **CLASE MAESTRA: {pregunta.upper()}**

Sigue ESTRICTAMENTE este formato visual y lúdico:

### 🌀 1. Imagina esto...
*(Escribe aquí una historia breve, una analogía potente o una situación cotidiana que conecte el tema con la vida real. Usa un tono narrativo atrapante).*

---

### 🧠 2. El Concepto Clave (Profundidad 40%)
*(Explica la teoría con autoridad pero claridad. Cubre el 40% de los conceptos esenciales para un dominio real).*
> **Definición Maestra:** *Define el término técnico con precisión.*

**¿Cómo funciona?**
*(Explica el mecanismo. AQUÍ es donde debes insertar una etiqueta de imagen si es útil. Ej: )*

---

### 🚀 3. El Reto Socrático
*(Lanza una pregunta desafiante que obligue a deducir una consecuencia. No la respondas).*

⛔ **PROHIBIDO:** Mencionar notas, tareas o hacer diagnósticos.
"""

        # --- 🔴 BOTÓN 3: NIVELACIÓN (LECTURA DE DETALLE) ---
        elif accion == ACCION_NIVELACION_ACADEMICA:
            specific_instruction = """
🚑 **PLAN DE RESCATE ACADÉMICO**

Analiza las 'fallas_detectadas' en el JSON. Háblame como un entrenador deportivo:

### 📉 Diagnóstico de Precisión
Dime exactamente: 'En **[Materia]**, tu nota de **[Nota]** se debe a que fallaste en el tema **[Tema]** y el logro **[Logro]**'.

### 🛠️ Kit de Supervivencia
Dame una técnica de estudio rápida (Mnemotecnia, Mapa Mental, etc.) para ese tema específico.

---
🔥 **¿Con cuál de estas materias quieres empezar a pelear tu nota hoy?**
"""

        # --- 🔵 BOTÓN 1: MEJORAS ESTUDIANTE (GAMIFICADO) ---
        elif accion == ACCION_MEJORAS_ESTUDIANTE:
            specific_instruction = """
📌 **REPORTE DE RENDIMIENTO**

Analiza mis notas y convivencia. Dame el reporte estilo 'Gamer':

### 🏆 Mis Superpoderes (Fortalezas)
Qué materias o comportamientos estoy dominando.

### ⚠️ Zonas de Riesgo (Debilidades)
Dónde estoy fallando y la causa probable según los datos.

### 🚀 Misiones Diarias
3 consejos prácticos para subir de nivel.
"""

        # --- 🟣 BIENESTAR GLOBAL (NUEVO: EXTENSO Y PROFESIONAL) ---
        elif accion == ACCION_ANALISIS_GLOBAL_BIENESTAR:
            specific_instruction = """
**INFORME ESTRATÉGICO DE BIENESTAR INSTITUCIONAL**

Analiza a fondo los datos de convivencia proporcionados (tipos de faltas, frecuencias, cursos afectados). Genera un reporte detallado siguiendo esta estructura:

### 1. 🌡️ Diagnóstico de Clima Escolar
Describe el estado actual de la convivencia. ¿Es un ambiente seguro, tenso o en riesgo? Usa los datos para justificar tu evaluación.

### 2. 🔍 Focos Críticos Detectados
Identifica los problemas raíz. No solo listes las faltas, explica **por qué** están ocurriendo (hipótesis basada en datos).
* **Tipologías Recurrentes:** ¿Qué falta se repite más? (Ej: Agresión, Ciberacoso, Desobediencia).
* **Zonas Calientes:** ¿Hay cursos o grados específicos con mayor incidencia?

### 3. 🛡️ Ruta de Mejora y Prevención (Action Plan)
Propón un plan de acción concreto y profesional para el equipo de orientación y directivos:
* **Acciones Inmediatas (Corto Plazo):** Medidas de contención urgentes.
* **Estrategias Formativas (Mediano Plazo):** Talleres, campañas o ajustes al manual necesarios.
* **Consejo para el Staff:** Una recomendación clave para mejorar el acompañamiento emocional.

> **Nota:** Sé extenso y riguroso. Este informe servirá para tomar decisiones directivas.
"""

        # --- DOCENTE: GRUPO ---
        elif accion == ACCION_DOCENTE_GRUPO:
            specific_instruction = """
📊 **RADIOGRAFÍA DEL CURSO**

### 🌡️ Termómetro del Aula
Análisis breve de promedio y alertas de convivencia.

### 🎯 Focos de Intervención
Lista los temas más difíciles (donde más pierden).

### 💡 Estrategias Docentes
Propón 2 dinámicas de aula para estos temas.
"""

        # --- DOCENTE: INDIVIDUAL ---
        elif accion == ACCION_DOCENTE_INDIVIDUAL:
            specific_instruction = """
Genera un guion de retroalimentación para este alumno:
1. **🌟 Reconocimiento:** Un logro real.
2. **🔧 Área de Mejora:** Basado en notas bajas.
3. **🤝 Compromiso:** Acuerdo medible.
"""

        # --- OTROS / LEGACY ---
        elif accion == ACCION_ANALISIS_CONVIVENCIA:
            specific_instruction = "Analiza el clima escolar, riesgos y estrategias de mediación basadas en los datos globales."
        elif accion == ACCION_MEJORA_STAFF_ACADEMICO:
            specific_instruction = "Analiza tendencias académicas globales y propón mejoras institucionales."
        elif accion == ACCION_APOYO_ACUDIENTE:
            specific_instruction = "Genera una guía empática para padres con acciones para apoyar en casa."
        elif accion == ACCION_CUMPLIMIENTO_PEI:
            specific_instruction = "Genera informe de auditoría ISO 21001 comparando datos reales con el PEI."
        elif accion == ACCION_RIESGO_ACADEMICO:
            specific_instruction = "Identifica estudiantes en riesgo de reprobación y sugiere intervención inmediata."
        else:
            specific_instruction = f"Responde a la consulta: {user_query or 'Genera el reporte solicitado.'}"

        user_message = {
            "role": "user",
            "content": context_block + specific_instruction.strip()
        }

        # =====================================================
        # 3. ENSAMBLAJE FINAL + MEMORIA
        # =====================================================
        final_messages = [system_message]

        if historial:
            final_messages.extend(historial)

        final_messages.append(user_message)

        return final_messages

# Instancia lista para importar
prompt_factory = PromptFactory()