# tasks/services/institutional.py
from django.db.models import Avg, Count
from tasks.models import (
    Nota, Observacion, Convivencia, Asistencia, Institucion
)

class InteligenciaInstitucionalService:
    """
    FUENTE DE VERDAD ÚNICA (Single Source of Truth).
    Centraliza el cálculo de KPIs para Dashboard e IA.
    """

    @staticmethod
    def get_radiografia_completa():
        """Retorna el objeto JSON limpio con métricas institucionales."""
        institucion = Institucion.objects.first()
        nombre_colegio = institucion.nombre if institucion else "Institución Educativa"
        
        # Promedio global calculado solo sobre cursos activos
        promedio_global = Nota.objects.filter(materia__curso__activo=True).aggregate(Avg('valor'))['valor__avg'] or 0.0

        return {
            "institucion_info": {
                "nombre": nombre_colegio,
                "promedio_global_gpa": round(float(promedio_global), 2),
            },
            "riesgo_academico": InteligenciaInstitucionalService._calcular_riesgo_academico(),
            "alertas_convivencia": InteligenciaInstitucionalService._calcular_alertas_convivencia(),
            "radar_observaciones": InteligenciaInstitucionalService._obtener_radar_observaciones(),
            "top_ausentismo": InteligenciaInstitucionalService._calcular_top_ausentismo()
        }

    @staticmethod
    def _calcular_riesgo_academico():
        """
        Estudiantes con Nota < 3.0 en múltiples materias.
        CORRECCIÓN: Cuenta materias únicas (distinct) y filtra por periodo activo.
        """
        reprobados_qs = Nota.objects.filter(
            valor__lt=3.0, 
            materia__curso__activo=True,
            periodo__activo=True  # 🔥 Solo notas del periodo actual
        ).values(
            'estudiante__id', 
            'estudiante__first_name', 
            'estudiante__last_name', 
            'materia__curso__nombre'
        ).annotate(
            # 🔥 CORRECCIÓN MATEMÁTICA: Cuenta materias distintas, no cantidad de notas
            materias_perdidas=Count('materia', distinct=True) 
        ).filter(materias_perdidas__gte=1).order_by('-materias_perdidas')[:15]

        lista_riesgo = []
        for rep in reprobados_qs:
            # Subconsulta para obtener nombres de materias (también filtrada y distinct)
            materias_names = Nota.objects.filter(
                estudiante_id=rep['estudiante__id'], 
                valor__lt=3.0,
                periodo__activo=True
            ).values_list('materia__nombre', flat=True).distinct()
            
            cantidad = rep['materias_perdidas']
            # Pre-cálculo para ayudar a la IA con el Manual
            gravedad = "CRITICO_FIRMA_COMPROMISO" if cantidad >= 3 else "ALERTA_ACADEMICA"

            lista_riesgo.append({
                "estudiante": f"{rep['estudiante__first_name']} {rep['estudiante__last_name']}",
                "curso": rep['materia__curso__nombre'],
                "cantidad_materias_perdidas": cantidad,
                "nivel_riesgo_manual": gravedad, # 👈 Pista para la IA
                "asignaturas_criticas": list(materias_names)
            })
        
        return {
            "descripcion": "Estudiantes con mayor número de asignaturas reprobadas actualmente (Periodo Activo).",
            "casos_criticos": lista_riesgo
        }

    @staticmethod
    def _calcular_alertas_convivencia():
        """Estudiantes con Nota Convivencia < 3.5."""
        baja_convivencia_qs = Convivencia.objects.filter(
            valor__lt=3.5, 
            periodo__activo=True
        ).select_related('estudiante', 'curso').order_by('valor')[:10]

        return {
            "descripcion": "Estudiantes con calificación de conducta baja (Inferior a 3.5).",
            "casos": [{
                "estudiante": e.estudiante.get_full_name(),
                "curso": e.curso.nombre,
                "nota_convivencia": float(e.valor),
                "observacion_docente": e.comentario or "Sin comentario"
            } for e in baja_convivencia_qs]
        }

    @staticmethod
    def _obtener_radar_observaciones():
        """Últimas incidencias graves/disciplinarias."""
        ultimas_obs = Observacion.objects.exclude(
            tipo__in=['ACADEMICO', 'FELICITACION']
        ).select_related('estudiante', 'autor').order_by('-fecha_creacion')[:8]

        return {
            "descripcion": "Últimos reportes disciplinarios en tiempo real.",
            "eventos": [{
                "tipo": obs.tipo,
                "estudiante": obs.estudiante.get_full_name(),
                "descripcion": obs.descripcion[:100] + "...", 
                "fecha": str(obs.fecha_creacion.date())
            } for obs in ultimas_obs]
        }

    @staticmethod
    def _calcular_top_ausentismo():
        """Top estudiantes con más fallas."""
        # Filtramos por curso activo para no contar fallas de años anteriores
        top_ausentismo = list(Asistencia.objects.filter(
                estado='FALLA',
                curso__activo=True 
            )
            .values('estudiante__first_name', 'estudiante__last_name', 'curso__nombre')
            .annotate(conteo=Count('id'))
            .order_by('-conteo')[:5])
            
        return {
            "descripcion": "Estudiantes con mayor acumulación de fallas.",
            "lista": top_ausentismo
        }