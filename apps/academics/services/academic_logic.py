# apps/academics/services/academic_logic.py
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.conf import settings
from apps.tenancy.utils import get_current_tenant

# Importamos GRADOS_CHOICES del archivo central de modelos de esta app
from ..models import GRADOS_CHOICES

logger = logging.getLogger(__name__)

# --- CONSTANTES INDUSTRIALES ---
PESOS_NOTAS = {
    1: Decimal('0.20'), 
    2: Decimal('0.30'), 
    3: Decimal('0.30'), 
    4: Decimal('0.20')
}
ESCALA_MIN = Decimal('1.0') # Ajustado a escala estándar (1-5)
ESCALA_MAX = Decimal('5.0')
NOTA_APROBACION = Decimal('3.5')
CAPACIDAD_POR_DEFECTO = getattr(settings, 'CAPACIDAD_CURSOS_DEFAULT', 40)

# --- NORMALIZACIÓN DE GRADOS ---
_GRADOS_VALIDOS = set(dict(GRADOS_CHOICES).keys())
_NOMBRE_A_CLAVE = {v.upper(): k for k, v in GRADOS_CHOICES}

def normalizar_grado(g):
    if not g: return None
    g_str = str(g).strip().upper()
    if g_str in _GRADOS_VALIDOS:
        return g_str
    return _NOMBRE_A_CLAVE.get(g_str)

# --- AYUDANTES DE TIEMPO ---

def obtener_anio_escolar_actual():
    """Calcula el ciclo escolar basado en la fecha actual."""
    hoy = timezone.now().date()
    y = hoy.year
    return f"{y}-{y + 1}" if hoy.month >= 7 else f"{y - 1}-{y}"

# --- FUNCIONES REQUERIDAS POR VIEWS.PY (CON GUION BAJO) ---

def _secciones_disponibles(anio_escolar=None):
    """Retorna las secciones únicas (A, B, C...) registradas en el colegio."""
    from ..models import Curso # Import local para evitar importación circular
    tenant = get_current_tenant()
    qs = Curso.objects.filter(tenant=tenant, activo=True)
    if anio_escolar:
        qs = qs.filter(anio_escolar=anio_escolar)
    return sorted(list(set(qs.exclude(seccion__isnull=True).exclude(seccion__exact='').values_list('seccion', flat=True))))

def _capacidad_curso(curso):
    """Devuelve la capacidad máxima de un curso o la default."""
    return getattr(curso, 'capacidad_maxima', CAPACIDAD_POR_DEFECTO) or CAPACIDAD_POR_DEFECTO

def _curso_esta_completo(curso):
    """Verifica si el curso alcanzó el límite de alumnos matriculados."""
    from ..models import Matricula # Import local
    ocupacion = Matricula.objects.filter(curso=curso, activo=True).count()
    return ocupacion >= _capacidad_curso(curso)

def calcular_siguiente_seccion(grado, anio_escolar, tenant):
    """Calcula la siguiente letra disponible para una nueva sección."""
    from ..models import Curso
    secciones = Curso.objects.filter(
        grado=grado, anio_escolar=anio_escolar, tenant=tenant
    ).values_list('seccion', flat=True)
    
    existing = set(secciones)
    for i in range(ord('A'), ord('Z') + 1):
        letra = chr(i)
        if letra not in existing:
            return letra
    return f"X{len(existing) + 1}"

@transaction.atomic
def obtener_o_crear_curso_con_cupo(grado, anio_escolar):
    """Lógica de asignación automática de cupos."""
    from ..models import Curso
    tenant = get_current_tenant()
    grado_norm = normalizar_grado(grado)
    
    if not grado_norm:
        return None

    # 1. Buscar cursos existentes con espacio
    cursos = Curso.objects.filter(
        grado=grado_norm, anio_escolar=anio_escolar, tenant=tenant
    ).order_by('seccion')

    for c in cursos:
        if not _curso_esta_completo(c):
            return c

    # 2. Si no hay cupo, crear nueva sección automática
    nueva_seccion = calcular_siguiente_seccion(grado_norm, anio_escolar, tenant)
    nombre_curso = f"{dict(GRADOS_CHOICES).get(grado_norm, grado_norm)} {nueva_seccion}"
    
    try:
        return Curso.objects.create(
            nombre=nombre_curso,
            grado=grado_norm,
            seccion=nueva_seccion,
            anio_escolar=anio_escolar,
            tenant=tenant,
            activo=True
        )
    except IntegrityError:
        return Curso.objects.get(grado=grado_norm, seccion=nueva_seccion, tenant=tenant)

# --- ESTRUCTURA EDUCATIVA ---

def obtener_grados_por_nivel():
    return {
        'preescolar': ['PREKINDER', 'KINDER', 'JARDIN', 'TRANSICION'],
        'primaria': ['1', '2', '3', '4', '5'],
        'bachillerato': ['6', '7', '8', '9', '10', '11']
    }

def obtener_nivel_por_grado(grado_id):
    niveles = obtener_grados_por_nivel()
    for nivel, grados in niveles.items():
        if str(grado_id).upper() in grados:
            return nivel
    return 'otros'