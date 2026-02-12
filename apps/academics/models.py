from django.db import models

# Create your models here.
from django.db import models

class Periodo(models.Model):
    """Representa los cortes académicos (Ej: Primer Periodo, Segundo Periodo)."""
    nombre = models.CharField(max_length=50) # Ej: Periodo 1
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.nombre

class Materia(models.Model):
    """Representa las asignaturas (Ej: Matemáticas, Lenguaje)."""
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.nombre

class Curso(models.Model):
    """Representa los grupos (Ej: 11-A, 6-B)."""
    GRADOS = [
        ('6', 'Sexto'), ('7', 'Séptimo'), ('8', 'Octavo'),
        ('9', 'Noveno'), ('10', 'Décimo'), ('11', 'Undécimo'),
    ]
    grado = models.CharField(max_length=2, choices=GRADOS)
    seccion = models.CharField(max_length=10) # Ej: A, B, 1, 2
    anio_escolar = models.CharField(max_length=10) # Ej: 2025-2026
    activo = models.BooleanField(default=True)

    @property
    def nombre(self):
        return f"{self.get_grado_display()} {self.seccion}"

    def __str__(self):
        return f"{self.nombre} ({self.anio_escolar})"