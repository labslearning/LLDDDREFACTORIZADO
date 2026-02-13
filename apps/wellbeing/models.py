# apps/wellbeing/models.py
from django.db import models
from django.conf import settings
from apps.tenancy.mixins import TenantAwareModel
from apps.academics.models import Curso, Materia, Periodo

# ==========================================================
# 📋 ASISTENCIA Y CONVIVENCIA
# ==========================================================

class Asistencia(TenantAwareModel):
    ESTADOS = [
        ('ASISTIO', 'Asistió'),
        ('FALLA', 'Falla Injustificada'),
        ('EXCUSA', 'Falla Justificada'),
        ('TARDE', 'Llegada Tarde'),
    ]
    # 🛡️ FIX related_name: bienestar_asistencias
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wellbeing_asistencias'
    )
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ASISTIO')
    # 🛡️ FIX related_name: bienestar_asistencias_tomadas
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_asistencias_tomadas'
    )

    def __str__(self):
        return f"{self.estudiante.username} - {self.materia.nombre} ({self.fecha})"

class Convivencia(TenantAwareModel):
    # 🛡️ FIX related_name: wellbeing_convivencias
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wellbeing_convivencias'
    )
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE)
    valor = models.DecimalField(max_digits=3, decimal_places=2)
    comentario = models.TextField(blank=True)
    # 🛡️ FIX related_name: wellbeing_convivencias_registradas
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_convivencias_registradas'
    )

# ==========================================================
# 📝 OBSERVADOR DISCIPLINARIO Y SEGUIMIENTOS
# ==========================================================

class Observacion(TenantAwareModel):
    TIPOS = [
        ('CONVIVENCIA', 'Convivencia'),
        ('ACADEMICA', 'Académica'),
        ('PSICOLOGICA', 'Psicológica'),
    ]
    # 🛡️ FIX related_name: wellbeing_observaciones
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wellbeing_observaciones'
    )
    # 🛡️ FIX related_name: wellbeing_observaciones_autor
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_observaciones_autor'
    )
    periodo = models.ForeignKey(Periodo, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='CONVIVENCIA')
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def es_editable(self):
        from django.utils import timezone
        import datetime
        return (timezone.now() - self.fecha_creacion) < datetime.timedelta(hours=24)

class Seguimiento(TenantAwareModel):
    # 🛡️ FIX related_name: wellbeing_seguimientos
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wellbeing_seguimientos'
    )
    # 🛡️ FIX related_name: wellbeing_seguimientos_profesional
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_seguimientos_profesional'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=100)
    descripcion = models.TextField()
    observaciones_adicionales = models.TextField(blank=True)

# ==========================================================
# 📜 ACTAS E INSTITUCIONAL
# ==========================================================

class ActaInstitucional(TenantAwareModel):
    TIPOS = [
        ('COMITE', 'Comité de Convivencia'),
        ('CONSEJO', 'Consejo Académico'),
        ('SITUACION_ESPECIAL', 'Situación Especial'),
    ]
    consecutivo = models.IntegerField()
    fecha = models.DateField()
    hora_fin = models.TimeField()
    titulo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=TIPOS)
    # 🛡️ FIX related_name: wellbeing_actas_creadas
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_actas_creadas'
    )
    # 🛡️ FIX related_name: wellbeing_actas_implicado
    implicado = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='wellbeing_actas_implicado'
    )
    # 🛡️ FIX related_name: wellbeing_actas_participantes
    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='wellbeing_actas_participantes'
    )
    orden_dia = models.TextField()
    contenido = models.TextField()
    compromisos = models.TextField()
    asistentes_externos = models.TextField(blank=True)

class Institucion(TenantAwareModel):
    nombre = models.CharField(max_length=255)
    archivo_pei = models.FileField(upload_to='institucion/docs/', null=True, blank=True)
    archivo_manual_convivencia = models.FileField(upload_to='institucion/docs/', null=True, blank=True)

class ObservadorArchivado(TenantAwareModel):
    estudiante_nombre = models.CharField(max_length=255)
    estudiante_username = models.CharField(max_length=150)
    anio_lectivo_archivado = models.CharField(max_length=20)
    archivo_pdf = models.FileField(upload_to='archivados/observadores/')
    # 🛡️ FIX related_name: wellbeing_obs_eliminados
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='wellbeing_obs_eliminados'
    )
    fecha_archivado = models.DateTimeField(auto_now_add=True)