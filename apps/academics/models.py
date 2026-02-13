# apps/academics/models.py
from django.db import models
from django.conf import settings
from apps.tenancy.mixins import TenantAwareModel

# Opciones de Grados (Legacy compatible)
GRADOS_CHOICES = [
    ('PREKINDER', 'Pre-Kínder'),
    ('KINDER', 'Kínder'),
    ('JARDIN', 'Jardín'),
    ('TRANSICION', 'Transición'),
    ('1', 'Primero'), ('2', 'Segundo'), ('3', 'Tercero'),
    ('4', 'Cuarto'), ('5', 'Quinto'), ('6', 'Sexto'),
    ('7', 'Séptimo'), ('8', 'Octavo'), ('9', 'Noveno'),
    ('10', 'Décimo'), ('11', 'Once'),
]

class Periodo(TenantAwareModel):
    """Representa los cortes académicos (Ej: Primer Periodo, Segundo Periodo)."""
    nombre = models.CharField(max_length=50)
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.nombre}"

class Curso(TenantAwareModel):
    """Representa los grupos (Ej: 11-A, 6-B)."""
    nombre = models.CharField(max_length=100, blank=True)
    grado = models.CharField(max_length=20, choices=GRADOS_CHOICES)
    seccion = models.CharField(max_length=10)
    anio_escolar = models.CharField(max_length=20)
    capacidad_maxima = models.IntegerField(default=40)
    
    # 🛡️ FIX related_name
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='academics_cursos_dirigidos' 
    )
    activo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.nombre:
            self.nombre = f"{self.get_grado_display()} {self.seccion}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.anio_escolar})"

class Materia(TenantAwareModel):
    """Representa las asignaturas vinculadas a un curso."""
    nombre = models.CharField(max_length=100)
    # 🩹 FIX MIGRACIÓN: Permitir null temporalmente
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE, 
        related_name='materias',
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return f"{self.nombre}"

class AsignacionMateria(TenantAwareModel):
    """Vincula un Docente con una Materia y Curso (Carga Académica)."""
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='academics_asignaciones'
    )
    # 🩹 FIX MIGRACIÓN
    materia = models.ForeignKey(
        Materia, 
        on_delete=models.CASCADE, 
        related_name='asignaciones',
        null=True, 
        blank=True
    )
    # 🩹 FIX MIGRACIÓN
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE,
        null=True, 
        blank=True
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.docente.username} -> {self.materia.nombre if self.materia else 'S/M'}"

class Matricula(TenantAwareModel):
    """Vínculo entre estudiante y curso por año lectivo."""
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='academics_matriculas'
    )
    # 🩹 FIX MIGRACIÓN
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE, 
        related_name='matriculados',
        null=True, 
        blank=True
    )
    anio_escolar = models.CharField(max_length=20)
    fecha_inicio = models.DateField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    puede_generar_boletin = models.BooleanField(default=True)

class DefinicionNota(TenantAwareModel):
    """Define los porcentajes de la materia (Ej: 30% Quiz, 70% Examen)."""
    # 🩹 FIX MIGRACIÓN
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, null=True, blank=True)
    # 🩹 FIX MIGRACIÓN
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    orden = models.IntegerField(default=1)
    temas = models.TextField(blank=True)

class Nota(TenantAwareModel):
    """Nota Definitiva consolidada."""
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='academics_notas_estudiante'
    )
    # 🩹 FIX MIGRACIÓN
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, null=True, blank=True)
    # 🩹 FIX MIGRACIÓN
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, null=True, blank=True)
    valor = models.DecimalField(max_digits=3, decimal_places=2)
    numero_nota = models.IntegerField(default=5) 
    descripcion = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='academics_notas_registradas'
    )

class NotaDetallada(TenantAwareModel):
    """Calificaciones de los cortes individuales definidos en DefinicionNota."""
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='academics_detalles_notas'
    )
    # 🩹 FIX MIGRACIÓN
    definicion = models.ForeignKey(DefinicionNota, on_delete=models.CASCADE, null=True, blank=True)
    valor = models.DecimalField(max_digits=3, decimal_places=2)
    fecha_registro = models.DateTimeField(auto_now_add=True)

class BoletinArchivado(TenantAwareModel):
    """Historial de boletines cuando un estudiante es retirado."""
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='academics_boletines_historial'
    )
    nombre_estudiante = models.CharField(max_length=255)
    username_estudiante = models.CharField(max_length=150)
    grado_archivado = models.CharField(max_length=50)
    seccion_archivada = models.CharField(max_length=10)
    anio_lectivo_archivado = models.CharField(max_length=20)
    fecha_eliminado = models.DateTimeField(auto_now_add=True)
    archivo_pdf = models.FileField(upload_to='boletines_archivados/')