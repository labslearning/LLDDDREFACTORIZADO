# tasks/services/reports.py
import logging
from datetime import date
from decimal import Decimal
from tasks.models import (
    Matricula, Nota, LogroPeriodo, ComentarioDocente, Convivencia, 
    Institucion, AsignacionMateria, Periodo, Acudiente,
    GRADOS_CHOICES, Materia
)

logger = logging.getLogger(__name__)

def get_student_report_context(matricula_id: int) -> dict:
    """
    Recopila datos para el boletín académico individual.
    """
    try:
        matricula = Matricula.objects.select_related('estudiante', 'curso').get(id=matricula_id)
    except Matricula.DoesNotExist:
        logger.error(f"No se encontró matrícula con el id: {matricula_id}")
        return None

    estudiante = matricula.estudiante
    curso = matricula.curso

    acudiente_link = Acudiente.objects.filter(estudiante=estudiante).select_related('acudiente').first()
    acudiente = acudiente_link.acudiente if acudiente_link else None

    institucion = Institucion.objects.first()
    if not institucion:
        institucion = Institucion(nombre="[Configurar Institución en Admin]")

    periodos = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
    
    # Lógica de asignaciones por año escolar
    anio_prefix = curso.anio_escolar.split('-')[0] if curso.anio_escolar else ""
    asignaciones = AsignacionMateria.objects.filter(
        curso=curso,
        activo=True,
        periodo_academico__startswith=anio_prefix
    ).select_related('materia', 'docente')

    if not asignaciones.exists():
        materias_del_curso = list(Materia.objects.filter(curso=curso))
        asignaciones = []
        for mat in materias_del_curso:
            docente_asignado = AsignacionMateria.objects.filter(materia=mat).select_related('docente').last()
            asignaciones.append(AsignacionMateria(materia=mat, docente=docente_asignado.docente if docente_asignado else None))

    materias_ids = [a.materia.id for a in asignaciones]
    notas_qs = Nota.objects.filter(estudiante=estudiante, materia_id__in=materias_ids, periodo__in=periodos)
    logros_qs = LogroPeriodo.objects.filter(curso=curso, materia_id__in=materias_ids, periodo__in=periodos)
    comentarios_qs = ComentarioDocente.objects.filter(estudiante=estudiante, materia_id__in=materias_ids, periodo__in=periodos).select_related('periodo')
    convivencia_qs = Convivencia.objects.filter(estudiante=estudiante, curso=curso, periodo__in=periodos)

    materias_data = []

    for asignacion in asignaciones:
        materia_obj = asignacion.materia 
        materia_info = {
            'nombre': materia_obj.nombre,
            'docente': asignacion.docente.get_full_name() or asignacion.docente.username if asignacion.docente else "Docente no asignado",
            'periodos_data': [],
            'promedio_final_materia': Decimal('0.0')
        }

        promedios_periodo_existentes = []

        for periodo in periodos:
            # Filtrado en memoria
            notas_periodo = [n for n in notas_qs if n.materia_id == materia_obj.id and n.periodo_id == periodo.id]
            logros_periodo = [l.descripcion for l in logros_qs if l.materia_id == materia_obj.id and l.periodo_id == periodo.id]
            comentarios_periodo = [c.comentario for c in comentarios_qs if c.materia_id == materia_obj.id and c.periodo_id == periodo.id]

            nota_promedio_obj = next((n for n in notas_periodo if n.numero_nota == 5), None)
            promedio_periodo_actual = nota_promedio_obj.valor if nota_promedio_obj else None

            if promedio_periodo_actual is not None or logros_periodo or comentarios_periodo:
                if promedio_periodo_actual is not None:
                    promedios_periodo_existentes.append(promedio_periodo_actual)

                materia_info['periodos_data'].append({
                    'nombre_periodo': periodo.nombre,
                    'promedio_periodo': promedio_periodo_actual,
                    'logros': logros_periodo,
                    'comentarios': comentarios_periodo,
                })

        if promedios_periodo_existentes:
            materia_info['promedio_final_materia'] = (sum(promedios_periodo_existentes) / len(promedios_periodo_existentes)).quantize(Decimal('0.01'))

        if materia_info['periodos_data']:
            materias_data.append(materia_info)

    return {
        'institucion': institucion,
        'estudiante': estudiante,
        'acudiente': acudiente,
        'curso': curso,
        'matricula': matricula,
        'materias_data': materias_data,
        'convivencia_data': list(convivencia_qs.values('periodo__nombre', 'valor', 'comentario')),
        'fecha_emision': date.today(),
        'periodos': periodos,
        'GRADOS_CHOICES': dict(GRADOS_CHOICES)
    }

