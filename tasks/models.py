
import uuid
import hashlib
import os
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

from django.db import models
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Max    #importacion necesaria para el acta institucional 
import os
from django.core.validators import MinValueValidator, MaxValueValidator



import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder



from datetime import timedelta
from datetime import date
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from django.contrib.auth import get_user_model
User = get_user_model()


from .ai.constants import (
    # 1. Configuración General y Roles
    ROLES_IA_PERMITIDOS,
    ACCIONES_IA_PERMITIDAS,
    MODEL_NAME,

    # 2. Tipos de Documentos Oficiales (Fase 6)
    DOC_REPORTE_PEDAGOGICO,
    DOC_ORIENTACION_ESTUDIANTE,
    DOC_ORIENTACION_ACUDIENTE,
    DOC_REPORTE_CONVIVENCIA,
    DOC_REPORTE_INSTITUCIONAL,
    DOCUMENTOS_IA_PERMITIDOS  # Útil si necesitas validar listas
)

# ===================================================================
# CONSTANTES Y OPCIONES
# ===================================================================

GRADOS_CHOICES = (
    ('PREKINDER', 'Prekinder'),
    ('KINDER', 'Kinder'),
    ('JARDIN', 'Jardín'),
    ('TRANSICION', 'Transición'),
    ('1', 'Primer grado'),
    ('2', 'Segundo grado'),
    ('3', 'Tercer grado'),
    ('4', 'Cuarto grado'),
    ('5', 'Quinto grado'),
    ('6', 'Sexto grado'),
    ('7', 'Séptimo grado'),
    ('8', 'Octavo grado'),
    ('9', 'Noveno grado'),
    ('10', 'Décimo grado'),
    ('11', 'Undécimo grado'),
)

ROLES_CHOICES = (
    ('ESTUDIANTE', 'Estudiante'),
    ('DOCENTE', 'Docente'),
    ('ADMINISTRADOR', 'Administrador'),
    ('DIRECTOR_CURSO', 'Director de Curso'),
    ('ACUDIENTE', 'Acudiente'),
    ('PSICOLOGO', 'Psicólogo'),
    ('COORD_CONVIVENCIA', 'Coord. Convivencia'),
    ('COORD_ACADEMICO', 'Coord. Académico'),
)

# ===================================================================
# PERFILES Y USUARIOS
# ===================================================================

class Perfil(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    rol = models.CharField(max_length=20, choices=ROLES_CHOICES, default='ESTUDIANTE')
    
    # --- FLAGS ADMINISTRATIVOS ---
    es_director = models.BooleanField(default=False)
    requiere_cambio_clave = models.BooleanField(default=False)
    # 🔥🔥🔥 AGREGA ESTE CAMPO AQUÍ 🔥🔥🔥
    numero_documento = models.CharField(
        max_length=30, 
        blank=True, 
        null=True, 
        verbose_name="Documento de Identidad",
        db_index=True, # Importante para búsquedas rápidas
        help_text="Cédula, TI, Pasaporte, etc."
    )
    # --- IDENTIDAD VISUAL Y SOCIAL ---
    foto_perfil = models.ImageField(upload_to='perfiles/avatars/', blank=True, null=True, verbose_name="Foto de Perfil")
    foto_portada = models.ImageField(upload_to='perfiles/covers/', blank=True, null=True, verbose_name="Foto de Portada")
    biografia = models.TextField(max_length=500, blank=True, verbose_name="Sobre mí")
    
    # --- NUEVOS CAMPOS: INTERESES Y GUSTOS ---
    hobbies = models.TextField(blank=True, null=True, verbose_name="Mis Hobbies")
    gustos_musicales = models.CharField(max_length=255, blank=True, null=True, verbose_name="Música favorita")
    libros_favoritos = models.TextField(blank=True, null=True, verbose_name="Libros que me gustan")
    materia_favorita = models.CharField(max_length=100, blank=True, null=True, verbose_name="Materia favorita")
    metas_anio = models.TextField(blank=True, null=True, verbose_name="Metas del año lectivo")
    
    # --- GAMIFICACIÓN Y ESTADO ---
    puntos_reputacion = models.IntegerField(default=0, verbose_name="Reputación Académica")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Última vez visto")
    
    # --- PRIVACIDAD ---
    perfil_publico = models.BooleanField(default=True, help_text="Si es falso, solo profesores y compañeros de curso pueden verlo.")

    # ==========================================
    # 📱 SISTEMA DE ALERTAS SMS (NUEVO)
    # ==========================================
    telefono_sms = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Celular para Alertas",
        help_text="Número para notificaciones urgentes (+57...)"
    )
    recibir_sms = models.BooleanField(
        default=True,
        verbose_name="Activar Notificaciones SMS",
        help_text="Si se desactiva, no llegarán alertas al celular."
    )
    ultimo_sms_enviado = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Control de spam para no enviar mensajes repetidos el mismo día."
    )

    def __str__(self):
        return f"Perfil de {self.user.username}"

    def __str__(self):
        return f'{self.user.username} ({self.get_rol_display()})'

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
        
    @property
    def esta_en_linea(self):
        """Retorna True si el usuario tuvo actividad en los últimos 5 minutos."""
        if self.last_seen:
            now = timezone.now()
            return now - self.last_seen < timezone.timedelta(minutes=5)
        return False


class SocialGroup(models.Model):
    """
    Espacios sociales temáticos (Clubs, Grupos de Estudio, Deportes).
    """
    PRIVACIDAD_CHOICES = (
        ('PUBLICO', 'Público (Cualquiera puede unirse)'),
        ('PRIVADO', 'Privado (Requiere aprobación)'),
    )

    # 1. NOMBRE: Quitamos el default para que guarde el nombre real
    name = models.CharField(max_length=100, verbose_name="Nombre del Grupo")
    
    # Slug para URLs amigables
    slug = models.SlugField(unique=True, blank=True, null=True)
    
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Imagen de portada
    image = models.ImageField(upload_to='groups/covers/', blank=True, null=True, verbose_name="Imagen de Portada")
    
    # 2. CREADOR: Quitamos default=1 para asignar el usuario real en la vista
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_groups', 
        verbose_name="Creador",
        null=True, 
        blank=True
    )
    
    # 3. MIEMBROS: Relación limpia para permitir .add() y .remove()
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='social_groups', 
        verbose_name="Miembros",
        blank=True
    )
    
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='admin_groups', 
        blank=True, 
        verbose_name="Administradores"
    )

    # Configuración
    tipo_privacidad = models.CharField(max_length=10, choices=PRIVACIDAD_CHOICES, default='PUBLICO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Grupo Social"
        verbose_name_plural = "Grupos Sociales"
        ordering = ['-created_at']

    def __str__(self):
        return self.name
        
    def save(self, *args, **kwargs):
        # Generar slug automáticamente basado en el nombre real
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while SocialGroup.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_member_count(self):
        return self.members.count()

    def es_miembro(self, user):
        """Devuelve True si el usuario es miembro del grupo"""
        return self.members.filter(id=user.id).exists()

    @property
    def is_public(self):
        return self.tipo_privacidad == 'PUBLICO'

class GroupMember(models.Model):
    """
    Tabla intermedia para miembros de grupo con roles.
    """
    ROL_CHOICES = (
        ('ADMIN', 'Administrador'),
        ('MODERATOR', 'Moderador'),
        ('MEMBER', 'Miembro'),
    )

    grupo = models.ForeignKey(SocialGroup, on_delete=models.CASCADE)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='MEMBER')
    unido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('grupo', 'usuario')
        verbose_name = "Miembro de Grupo"
        verbose_name_plural = "Miembros de Grupo"

    def __str__(self):
        return f"{self.usuario.username} en {self.grupo.name} ({self.get_rol_display()})"


class Acudiente(models.Model):
    acudiente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='estudiantes_a_cargo',
        limit_choices_to={'perfil__rol': 'ACUDIENTE'},
        verbose_name='Usuario Acudiente'
    )
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='acudientes_asignados',
        limit_choices_to={'perfil__rol': 'ESTUDIANTE'},
        verbose_name='Usuario Estudiante'
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        verbose_name = 'Vínculo Acudiente-Estudiante'
        verbose_name_plural = 'Vínculos Acudiente-Estudiante'
        unique_together = ('acudiente', 'estudiante')

    def __str__(self):
        acudiente_nombre = self.acudiente.get_full_name() or self.acudiente.username
        estudiante_nombre = self.estudiante.get_full_name() or self.estudiante.username
        return f"Acudiente: {acudiente_nombre} -> Estudiante: {estudiante_nombre}"

# ===================================================================
# INSTITUCIONAL Y ACADÉMICO BÁSICO
# ===================================================================

# === MODELO INSTITUCIONAL ===
class Institucion(models.Model):
    # 1. Información Básica
    nombre = models.CharField(max_length=150)
    logo = models.ImageField(upload_to="logos_institucionales/", null=True, blank=True)
    lema = models.CharField(max_length=200, blank=True, null=True)
    anio_lectivo = models.CharField(max_length=10, default="2025")

    # 2. Información de Contacto y Legal
    direccion = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    nit = models.CharField(max_length=50, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    resolucion = models.CharField(max_length=200, blank=True, null=True)
    
    # 3. Centro de Documentación (PDFs)
    # Nota: He unificado la ruta de subida a 'institucion/documentos/' para mantener el orden.
    
    archivo_pei = models.FileField(
        upload_to='institucion/documentos/', 
        null=True, 
        blank=True, 
        verbose_name="Documento PEI (PDF)",
        help_text="Carga aquí el Proyecto Educativo Institucional en formato PDF."
    )

    archivo_manual_convivencia = models.FileField(
        upload_to='institucion/documentos/', 
        null=True, 
        blank=True, 
        verbose_name="Manual de Convivencia"
    )

    archivo_proyectos = models.FileField(
        upload_to='institucion/documentos/', 
        null=True, 
        blank=True, 
        verbose_name="Proyectos Transversales"
    )

    archivo_malla_curricular = models.FileField(
        upload_to='institucion/documentos/', 
        null=True, 
        blank=True, 
        verbose_name="Malla Curricular"
    )

    archivo_calendario = models.FileField(
        upload_to='institucion/documentos/', 
        null=True, 
        blank=True, 
        verbose_name="Calendario Académico"
    )

    # 4. Configuración del Modelo
    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Información Institucional"

    # 5. Métodos
    def __str__(self):
        return getattr(self, 'nombre', f"Institución sin nombre (ID: {self.pk or 'Nueva'})")

        class Meta:
            verbose_name = "Institución"
            verbose_name_plural = "Información Institucional"

        def __str__(self):
            return getattr(self, 'nombre', f"Institución sin nombre (ID: {self.pk or 'Nueva'})")
        
class Curso(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos_dirigidos',
        verbose_name='Director de Curso',
        limit_choices_to={'perfil__rol__in': ['DOCENTE']}
    )
    capacidad_maxima = models.IntegerField(default=40, verbose_name='Capacidad Máxima')
    anio_escolar = models.CharField(max_length=9, default='2025-2026', verbose_name='Año Escolar')
    seccion = models.CharField(max_length=100, default='A', verbose_name='Sección')
    grado = models.CharField(max_length=20, choices=GRADOS_CHOICES, default='6', verbose_name='Grado')
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        unique_together = ['grado', 'seccion', 'anio_escolar']
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['grado', 'seccion']

    def __str__(self):
        return f"{self.get_grado_display()} {self.seccion} - {self.anio_escolar}"

    def esta_completo(self):
        return self.matriculados.filter(activo=True).count() >= self.capacidad_maxima


class Materia(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='materias', verbose_name='Curso')

    class Meta:
        unique_together = ('nombre', 'curso')
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return f'{self.nombre} ({self.curso.nombre})'


class Periodo(models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='periodos', verbose_name='Curso')
    fecha_inicio = models.DateField(default=timezone.now, verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(default=timezone.now, verbose_name='Fecha de Fin')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        unique_together = ('nombre', 'curso')
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'

    def __str__(self):
        return f'{self.nombre} ({self.curso.nombre})'


class Matricula(models.Model):
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='matriculas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='matriculados')
    anio_escolar = models.CharField(max_length=9, default='2025-2026', verbose_name='Año Escolar')
    fecha_matricula = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Matrícula')
    activo = models.BooleanField(default=True)

    puede_generar_boletin = models.BooleanField(
        default=True,
        verbose_name="Acudiente puede generar boletín",
        help_text="Si está desactivado, el acudiente no podrá generar boletín desde su panel."
    )
    puede_ver_observador = models.BooleanField(
        default=True,
        verbose_name="Acudiente puede ver Observador",
        help_text="Si está desactivado, el acudiente no podrá descargar el observador."
    )

    class Meta:
        unique_together = ['estudiante', 'anio_escolar']
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'

    def __str__(self):
        return f"{self.estudiante.username} - {self.curso.nombre} ({self.anio_escolar})"


class AsignacionMateria(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='asignaciones')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='asignaciones_materias')
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='materias_asignadas')
    periodo_academico = models.CharField(max_length=20, default='2025-1', verbose_name='Periodo Académico')
    activo = models.BooleanField(default=True)
  
    class Meta:
        unique_together = ['materia', 'curso', 'docente']
        verbose_name = 'Asignación de Materia'
        verbose_name_plural = 'Asignaciones de Materias'

    def __str__(self):
        return f"{self.docente.username} -> {self.materia.nombre} en {self.curso.nombre}"

# ===================================================================
# GESTIÓN ACADÉMICA (NOTAS, LOGROS, ACTIVIDADES)
# ===================================================================

class Nota(models.Model):
    valor = models.DecimalField(max_digits=4, decimal_places=2, verbose_name='Valor')
    descripcion = models.CharField(max_length=100, blank=True, verbose_name='Descripción')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notas')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='notas', verbose_name='Materia')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='notas', verbose_name='Periodo')
    numero_nota = models.IntegerField(default=1, verbose_name='Número de Nota')
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notas_registradas'
    )

    class Meta:
        unique_together = ['estudiante', 'materia', 'periodo', 'numero_nota']
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    def __str__(self):
        return f'Nota {self.numero_nota} de {self.estudiante.username} en {self.materia.nombre} ({self.valor})'


class LogroPeriodo(models.Model):
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logros_registrados', verbose_name='Docente')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='logros_periodo', verbose_name='Curso')
    materia = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='logros_materia', verbose_name='Materia')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='logros', verbose_name='Periodo')
    descripcion = models.TextField(verbose_name='Descripción del Logro')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        verbose_name = "Logro del Periodo"
        verbose_name_plural = "Logros de los Periodos"
        unique_together = ('curso', 'periodo', 'docente', 'materia')
        ordering = ['periodo', '-fecha_creacion']

    def __str__(self):
        return f"Logro de {self.docente.username} para {self.curso.nombre} en {self.periodo.nombre}"


class ActividadSemanal(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='actividades')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='actividades_semanales')
    titulo = models.CharField(max_length=200, default='Actividad de la Semana', verbose_name='Título')
    descripcion = models.TextField(verbose_name='Descripción')
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(null=True, blank=True, verbose_name='Fecha de Finalización')
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Docente')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def __str__(self):
        return f'{self.titulo} - {self.materia.nombre} ({self.curso.nombre})'

    class Meta:
        verbose_name = "Actividad Semanal"
        verbose_name_plural = "Actividades Semanales"
        ordering = ['-fecha_creacion']


class ComentarioDocente(models.Model):
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_escritos')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_recibidos')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='comentarios')
    comentario = models.TextField(verbose_name='Comentario')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = 'Comentario del Docente'
        verbose_name_plural = 'Comentarios de los Docentes'
        unique_together = ('docente', 'estudiante', 'materia', 'periodo')
        ordering = ['-fecha_creacion']

    def __str__(self):
        if self.periodo:
            return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} ({self.periodo.nombre})"
        return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} (Sin periodo)"

# ===================================================================
# BIENESTAR Y CONVIVENCIA (OBSERVADOR, CONVIVENCIA, ASISTENCIA)
# ===================================================================

class Convivencia(models.Model):
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='convivencias')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='convivencias_curso')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='convivencias_periodo')
    valor = models.DecimalField(max_digits=3, decimal_places=2, help_text="Valor de la nota de 0.0 a 5.0")
    comentario = models.TextField(blank=True, null=True, help_text="Comentario opcional del director de curso")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='convivencias_registradas')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('estudiante', 'curso', 'periodo')
        verbose_name = "Nota de Convivencia"
        verbose_name_plural = "Notas de Convivencia"
        ordering = ['-periodo', 'estudiante']

    def __str__(self):
        return f"Convivencia de {self.estudiante.username} en {self.curso.nombre} ({self.periodo.nombre})"


class Observacion(models.Model):
    TIPO_CHOICES = (
        ('CONVIVENCIA', 'Situación de Convivencia'),
        ('ACADEMICA', 'Compromiso Académico'),
        ('PSICOLOGIA', 'Orientación Psicológica'),
        ('FELICITACION', 'Felicitación / Reconocimiento'),
    )

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='observaciones')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='observaciones_creadas')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='observaciones')

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(verbose_name="Descripción de la situación")
    compromisos_estudiante = models.TextField(blank=True, verbose_name="Compromisos del Estudiante")
    compromisos_familia = models.TextField(blank=True, verbose_name="Compromisos de la Familia/Acudiente")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_limite_edicion = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.fecha_limite_edicion = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def es_editable(self):
        return timezone.now() < self.fecha_limite_edicion

    class Meta:
        verbose_name = "Observación del Alumno"
        verbose_name_plural = "Observaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante}"


class Asistencia(models.Model):
    ESTADO_CHOICES = (
        ('ASISTIO', 'Asistió'),
        ('FALLA', 'Falla Injustificada'),
        ('EXCUSA', 'Falla Excusada'),
        ('TARDE', 'Llegada Tardía'),
    )
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asistencias')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='ASISTIO')
    observacion = models.CharField(max_length=200, blank=True, null=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='asistencias_tomadas')

    class Meta:
        unique_together = ('estudiante', 'materia', 'fecha')
        verbose_name = 'Registro de Asistencia'
        ordering = ['-fecha']

# ===================================================================
# HISTÓRICO Y ARCHIVOS (BOLETINES ANTIGUOS)
# ===================================================================

def ruta_archivo_boletin(instance, filename):
    grado_folder = instance.grado_archivado.replace(' ', '_').lower()
    anio_folder = instance.anio_lectivo_archivado.replace('-', '_')
    username_limpio = "".join(c for c in instance.username_estudiante if c.isalnum() or c in ('-', '_')).rstrip()
    filename = f"boletin_{username_limpio}_{anio_folder}.pdf"
    return os.path.join('boletines_archivados', anio_folder, grado_folder, filename)

class BoletinArchivado(models.Model):
    nombre_estudiante = models.CharField(max_length=255, db_index=True, help_text="Nombre completo del estudiante al momento del retiro.")
    username_estudiante = models.CharField(max_length=150, db_index=True, help_text="Username (documento) del estudiante para referencia.")
    grado_archivado = models.CharField(max_length=20, choices=GRADOS_CHOICES, db_index=True, help_text="El grado que cursaba el estudiante.")
    seccion_archivada = models.CharField(max_length=100, help_text="La sección que cursaba.")
    anio_lectivo_archivado = models.CharField(max_length=9, db_index=True, help_text="El año escolar de este boletín.")
    
    fecha_eliminado = models.DateTimeField(auto_now_add=True, help_text="Fecha y hora en que se generó este archivo.")
    eliminado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='boletines_archivados_por_mi')
    archivo_pdf = models.FileField(upload_to=ruta_archivo_boletin, help_text="El archivo PDF del boletín.")

    class Meta:
        verbose_name = "Boletín Archivado (Exalumno)"
        verbose_name_plural = "Boletines Archivados (Exalumnos)"
        ordering = ['-anio_lectivo_archivado', 'grado_archivado', 'nombre_estudiante']
        unique_together = ('username_estudiante', 'anio_lectivo_archivado')

    def __str__(self):
        return f"Boletín de {self.nombre_estudiante} ({self.anio_lectivo_archivado})"

# ===================================================================
# COMUNICACIÓN (FOROS, CHAT, NOTIFICACIONES)
# ===================================================================

class Question(models.Model):
    title = models.CharField(max_length=200, verbose_name='Título')
    content = models.TextField(verbose_name='Contenido')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['-created_at']


class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    content = models.TextField(verbose_name='Contenido')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')

    def __str__(self):
        return f'Respuesta de {self.user.username} en {self.question.title}'

    class Meta:
        verbose_name = 'Respuesta'
        verbose_name_plural = 'Respuestas'
        ordering = ['created_at']


class ChatRoom(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Sala de Chat'
        verbose_name_plural = 'Salas de Chat'


class ActiveUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, null=True, verbose_name='Sala de Chat')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Última Actividad')

    class Meta:
        unique_together = ('user', 'room')
        verbose_name = 'Usuario Activo'
        verbose_name_plural = 'Usuarios Activos'

    def __str__(self):
        return f'{self.user.username} en {self.room.name}'


class Notificacion(models.Model):
    TIPO_CHOICES = (
        ('ASISTENCIA', 'Novedad de Asistencia'),
        ('OBSERVADOR', 'Nueva Observación'),
        ('ACTIVIDAD', 'Nueva Actividad'),
        ('MENSAJE', 'Nuevo Mensaje'),
        ('SISTEMA', 'Sistema'),
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mis_notificaciones')
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SISTEMA')
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    link_destino = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['-fecha_creacion']


class MensajeInterno(models.Model):
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_enviados')
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_recibidos')
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    leido = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    
    archivo = models.FileField(upload_to='adjuntos_chat/', blank=True, null=True, verbose_name="Archivo Adjunto")
    
    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = "Mensaje Profesional"

    def __str__(self):
        return f"De {self.remitente} para {self.destinatario}: {self.asunto}"


# ===================================================================
# 🏗️ FASE I: RED SOCIAL (FEED, COMENTARIOS Y REACCIONES)
# ===================================================================

class Post(models.Model):
    TIPO_POST_CHOICES = (
        ('PUBLICACION', 'Publicación General'),
        ('ANUNCIO', 'Anuncio Oficial'), 
        ('EVENTO', 'Evento'),
    )

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    contenido = models.TextField(verbose_name="¿Qué estás pensando?")
    tipo = models.CharField(max_length=20, choices=TIPO_POST_CHOICES, default='PUBLICACION')
    
    imagen = models.ImageField(upload_to='social_feed/images/', blank=True, null=True)
    archivo = models.FileField(upload_to='social_feed/files/', blank=True, null=True)
    
    # Vinculado al modelo SocialGroup unificado
    grupo = models.ForeignKey('SocialGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='posts')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    es_destacado = models.BooleanField(default=False)

    reacciones = GenericRelation('Reaction') 

    class Meta:
        verbose_name = "Publicación Social"
        verbose_name_plural = "Publicaciones Sociales"
        ordering = ['-es_destacado', '-creado_en']

    def __str__(self):
        return f"{self.autor.username}: {self.contenido[:30]}..."

    @property
    def total_reacciones(self):
        return self.reacciones.count()

    @property
    def total_comentarios(self):
        return self.comentarios.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comentarios')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenido = models.TextField()
    
    padre = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='respuestas')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    reacciones = GenericRelation('Reaction')

    class Meta:
        ordering = ['creado_en'] 

    def __str__(self):
        return f"Comentario de {self.autor.username} en {self.post.id}"

    @property
    def es_respuesta(self):
        return self.padre is not None


class Reaction(models.Model):
    TIPO_REACCION_CHOICES = (
        ('LIKE', '👍 Me gusta'),
        ('LOVE', '❤️ Me encanta'),
        ('WOW', '😲 Me asombra'),
        ('SAD', '😢 Me entristece'),
        ('ANGRY', '😡 Me enoja'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_REACCION_CHOICES, default='LIKE')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.usuario.username} reaccionó {self.tipo}"

# ===================================================================
# 🏗️ FASE I (PASO 2): SEGUIDORES
# ===================================================================

class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='siguiendo', on_delete=models.CASCADE)
    following = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='seguidores', on_delete=models.CASCADE)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = "Seguimiento"
        verbose_name_plural = "Seguimientos"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.follower.username} sigue a {self.following.username}"


# ===================================================================
# 🏗️ FASE I (PASO 3): GAMIFICACIÓN Y RECOMPENSAS
# ===================================================================

class Logro(models.Model):
    CLASE_ICONO_CHOICES = (
        ('BRONZE', 'Bronce (Básico)'),
        ('SILVER', 'Plata (Intermedio)'),
        ('GOLD', 'Oro (Avanzado)'),
        ('DIAMOND', 'Diamante (Experto)'),
    )

    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, help_text="Identificador único")
    descripcion = models.TextField()
    imagen = models.ImageField(upload_to='gamification/badges/', blank=True, null=True)
    clase_css = models.CharField(max_length=20, choices=CLASE_ICONO_CHOICES, default='BRONZE')
    puntos_otorgados = models.IntegerField(default=10)
    es_oculto = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Definición de Logro"
        verbose_name_plural = "Definiciones de Logros"

    def __str__(self):
        return f"{self.nombre} (+{self.puntos_otorgados} pts)"


class UserLogro(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logros_obtenidos')
    logro = models.ForeignKey(Logro, on_delete=models.CASCADE)
    fecha_obtenido = models.DateTimeField(auto_now_add=True)
    es_destacado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('usuario', 'logro') 
        verbose_name = "Logro de Usuario"
        verbose_name_plural = "Logros de Usuarios"
        ordering = ['-fecha_obtenido']

    def __str__(self):
        return f"{self.usuario.username} ganó {self.logro.nombre}"

# ===================================================================
# 🏗️ FASE I (PASO 4): SEGURIDAD Y AUDITORÍA
# ===================================================================

class Report(models.Model):
    RAZONES_CHOICES = (
        ('BULLYING', 'Acoso o Intimidación'),
        ('HATE', 'Lenguaje de Odio'),
        ('SPAM', 'Spam o Contenido Basura'),
        ('VIOLENCE', 'Violencia o Amenazas'),
        ('SEXUAL', 'Contenido Sexual'),
        ('OTHER', 'Otro motivo'),
    )
    
    ESTADO_CHOICES = (
        ('PENDING', 'Pendiente de Revisión'),
        ('RESOLVED', 'Resuelto / Tomada Acción'),
        ('DISMISSED', 'Descartado / Falso Reporte'),
    )

    denunciante = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reportes_realizados', on_delete=models.CASCADE)
    razon = models.CharField(max_length=20, choices=RAZONES_CHOICES)
    descripcion = models.TextField(blank=True, verbose_name="Detalles adicionales")
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDING')
    resolucion = models.TextField(blank=True, help_text="Nota del moderador")
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reportes_resueltos', null=True, blank=True, on_delete=models.SET_NULL)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Reporte de Moderación"
        verbose_name_plural = "Reportes de Moderación"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Reporte {self.get_razon_display()} por {self.denunciante.username}"


class AuditLog(models.Model):
    ACCION_CHOICES = (
        ('CREATE', 'Creación'),
        ('UPDATE', 'Edición'),
        ('DELETE', 'Eliminación'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGIN_FAIL', 'Fallo de Login'),
        ('SENSITIVE', 'Acceso Sensible'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    modelo_afectado = models.CharField(max_length=100) 
    objeto_id = models.CharField(max_length=100, null=True, blank=True)
    detalles = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ['-fecha']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema/Anon"
        return f"[{self.fecha}] {user_str} - {self.accion} en {self.modelo_afectado}"


# In tasks/models.py

class SecurityLog(models.Model):
    TIPOS_ALERTA = (
        ('VOCABULARIO', 'Vocabulario Ofensivo'),
        ('ACOSO', 'Posible Acoso/Bullying'),
    )
    
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alertas_seguridad')
    contenido_intentado = models.TextField()
    razon_bloqueo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Reporte de Seguridad"
        verbose_name_plural = "Reportes de Seguridad"
        ordering = ['-fecha']

    def __str__(self):
        return f"ALERTA: {self.usuario.username} - {self.fecha}"


# ==============================================================================
# PASO 0.2: PERIODO ACADÉMICO (GOBERNANZA Y CONTROL DE COSTOS)
# ==============================================================================

class PeriodoAcademico(models.Model):
    """
    Representa un periodo académico institucional y actúa como el
    GOBERNADOR FISCAL del uso de IA.
    
    Controla: Tiempo, Costos (Límites) y Unicidad.
    """

    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Ej: 2025-1, Año Lectivo 2025, Trimestre 2"
    )

    fecha_inicio = models.DateField(
        help_text="Fecha oficial de inicio del periodo académico"
    )

    fecha_fin = models.DateField(
        help_text="Fecha oficial de finalización del periodo académico"
    )

    activo = models.BooleanField(
        default=False,
        help_text="🔴 CRÍTICO: Solo un periodo puede estar activo. Al activar este, se desactivan los demás."
    )

    # ------------------------------------------------------------------
    # GOBERNANZA DE IA (Control de Costos Dinámico)
    # ------------------------------------------------------------------
    # Definimos los límites AQUÍ para poder ajustarlos desde el Admin
    # sin tocar el código si el presupuesto cambia.
    
    limite_intentos_profesor = models.IntegerField(
        default=10,  # Aumentado un poco para dar margen a pruebas iniciales
        help_text="Intentos de IA profunda (DeepSeek) permitidos por periodo para docentes."
    )
    
    limite_intentos_estudiante = models.IntegerField(
        default=2,
        help_text="Intentos de IA profunda permitidos por periodo para estudiantes."
    )

    limite_intentos_acudiente = models.IntegerField(
        default=1,
        help_text="Intentos de IA para orientación familiar por periodo."
    )

    limite_intentos_staff = models.IntegerField(
        default=50,
        help_text="Intentos para Staff (Psicología/Coord) para análisis institucional."
    )

    # ------------------------------------------------------------------
    # AUDITORÍA
    # ------------------------------------------------------------------
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha en que el periodo fue cerrado institucionalmente"
    )

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = "Periodo Académico (Governance)"
        verbose_name_plural = "Periodos Académicos (Governance)"

    def __str__(self):
        estado = "✅ ACTIVO" if self.activo else "⏹ INACTIVO"
        return f"{self.nombre} ({estado})"

    def clean(self):
        """Validación de integridad de datos antes de guardar."""
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    def save(self, *args, **kwargs):
        """
        Garantiza que SOLO UN periodo sea activo a la vez.
        Si activamos este, matamos la actividad de los otros.
        """
        if self.activo:
            # Desactivar todos los demás periodos activos
            PeriodoAcademico.objects.filter(activo=True).exclude(pk=self.pk).update(activo=False)
        
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # LÓGICA DE NEGOCIO
    # ------------------------------------------------------------------

    def cerrar_periodo(self):
        """Cierra el periodo académicamente y detiene el consumo de IA asociado."""
        self.activo = False
        self.cerrado_en = timezone.now()
        self.save(update_fields=["activo", "cerrado_en"])

    @classmethod
    def obtener_periodo_activo(cls):
        """
        Devuelve el periodo académico activo (El Gobernador actual).
        Optimizado para no traer toda la tabla.
        """
        return cls.objects.filter(activo=True).first()

    @property
    def esta_vigente(self):
        """Verifica si HOY estamos dentro de las fechas calendario."""
        hoy = timezone.now().date()
        if not self.fecha_inicio or not self.fecha_fin:
            return False
        return self.fecha_inicio <= hoy <= self.fecha_fin



# ==============================================================================
# PASO 0.3: CEREBRO INSTITUCIONAL (PEI)
# ==============================================================================

class PEIResumen(models.Model):
    """
    Almacena el Proyecto Educativo Institucional (PEI) procesado.
    
    ESTRATEGIA DE AHORRO DE TOKENS:
    En lugar de enviar documentos crudos (PDF/Docx) al LLM, enviamos este JSON.
    El 'ContextBuilder' seleccionará solo las llaves necesarias para cada prompt.
    
    Ahorro estimado: 80% de tokens de entrada por consulta.
    """
    
    version = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Ej: v2025.1 - Actualización Manual Convivencia"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    activo = models.BooleanField(
        default=True, 
        help_text="Solo una versión del PEI es la 'Verdad Absoluta' a la vez."
    )
    
    # El Corazón del sistema:
    contenido_estructurado = models.JSONField(
        default=dict,
        help_text="JSON estructurado con Misión, Visión, Ejes, Evaluación y Convivencia."
    )
    
    comentarios_cambio = models.TextField(
        blank=True, 
        help_text="Justificación de los cambios en esta versión (Auditoría)."
    )

    class Meta:
        verbose_name = "Conocimiento PEI (JSON)"
        verbose_name_plural = "Versiones del PEI"
        ordering = ['-fecha_creacion']

    def __str__(self):
        estado = "🟢 VIGENTE" if self.activo else "archivado"
        return f"PEI {self.version} [{estado}]"

    def save(self, *args, **kwargs):
        """
        Gobernanza de Datos:
        Asegura que solo exista una versión del PEI activa para evitar
        esquizofrenia institucional en las respuestas de la IA.
        """
        if self.activo:
            PEIResumen.objects.filter(activo=True).exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)

    @property
    def resumen_hash(self):
        """
        Genera una firma rápida para el sistema de Caching (Fase 3).
        Si el PEI cambia, el caché debe invalidarse automáticamente.
        """
        return f"{self.version}-{self.fecha_creacion.timestamp()}"

class AIUsageLog(models.Model):
    """
    Registro forense inmutable de toda interacción con la IA.
    
    OBJETIVOS:
    1. Control de costos (Tokens exactos).
    2. Seguridad (Detectar abuso de usuarios).
    3. Depuración (Registro de errores de API).
    4. Auditoría (Cumplimiento pedagógico).
    """

    # 1. ¿QUIÉN Y CUÁNDO?
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Si se borra el usuario, el log queda (auditoría)
        null=True,
        related_name='ai_logs'
    )
    
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    
    periodo = models.ForeignKey(
        'PeriodoAcademico',
        on_delete=models.PROTECT, # 🔒 SEGURIDAD: No se puede borrar un periodo si ya se gastó dinero en él.
        null=True,
        help_text="Periodo académico activo durante la consulta."
    )

    # 2. ¿BAJO QUÉ REGLAS?
    rol_usado = models.CharField(
        max_length=50,
        choices=[(r, r) for r in ROLES_IA_PERMITIDOS],
        help_text="El rol con el que el usuario firmó la petición (Docente, Estudiante, etc)."
    )
    
    accion = models.CharField(
        max_length=50,
        choices=[(a, a) for a in ACCIONES_IA_PERMITIDAS],
        help_text="La intención pedagógica (Intents)."
    )

    # 3. ¿CUÁNTO COSTÓ? (LA FACTURA)
    modelo_utilizado = models.CharField(max_length=50, default=MODEL_NAME)
    
    tokens_entrada = models.IntegerField(default=0, help_text="Contexto + Prompt (Lo que enviamos)")
    tokens_salida = models.IntegerField(default=0, help_text="Respuesta generada (Lo que recibimos)")
    tiempo_ejecucion = models.FloatField(default=0.0, help_text="Segundos que tardó la respuesta")

    # 4. RESULTADO TÉCNICO
    exitoso = models.BooleanField(default=True)
    
    error_mensaje = models.TextField(
        blank=True, 
        null=True, 
        help_text="Si falló, aquí guardamos el stacktrace o mensaje de error de la API."
    )

    # 5. METADATA (NO GUARDAMOS EL PROMPT ENTERO POR PRIVACIDAD/ESPACIO)
    metadata_tecnica = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datalles técnicos: pei_version, razon_fallo, intentos_restantes, costo_estimado_usd."
    )

    class Meta:
        verbose_name = "Log de Uso IA"
        verbose_name_plural = "Auditoría de IA"
        ordering = ['-fecha']
        # Índices compuestos para reportes rápidos de consumo en el Dashboard
        indexes = [
            models.Index(fields=['usuario', 'periodo']),
            models.Index(fields=['rol_usado', 'fecha']),
        ]

    def __str__(self):
        status = "✅" if self.exitoso else "❌"
        user_str = str(self.usuario) if self.usuario else "ANÓNIMO"
        return f"{status} {self.fecha.strftime('%Y-%m-%d %H:%M')} | {user_str} | {self.accion}"

    @property
    def costo_total_tokens(self):
        """Suma total para cálculo rápido de impacto."""
        return self.tokens_entrada + self.tokens_salida



class AIDocumento(models.Model):
    """
    Representa un documento oficial generado por la IA.
    A diferencia del Log (técnico), esto es visible para el usuario.
    
    Ejemplos: "Plan de Mejora 2025-1", "Reporte de Curso 6A".
    """
    
    TIPOS_DOC_CHOICES = (
        (DOC_REPORTE_PEDAGOGICO, 'Reporte Pedagógico Docente'),
        (DOC_ORIENTACION_ESTUDIANTE, 'Plan de Mejora Estudiantil'),
        (DOC_ORIENTACION_ACUDIENTE, 'Orientación Familiar'),
        (DOC_REPORTE_CONVIVENCIA, 'Reporte de Convivencia'),
        (DOC_REPORTE_INSTITUCIONAL, 'Análisis Institucional (PEI)'),
    )

    titulo = models.CharField(max_length=200, help_text="Ej: Plan de Mejora - Matemáticas")
    
    tipo = models.CharField(max_length=50, choices=TIPOS_DOC_CHOICES)
    
    # PROPIEDAD Y TRAZABILIDAD
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='documentos_ia',
        verbose_name="Propietario del Documento"
    )
    
    periodo = models.ForeignKey(
        PeriodoAcademico, 
        on_delete=models.PROTECT,
        verbose_name="Periodo Académico"
    )
    
    pei_version = models.ForeignKey(
        PEIResumen, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text="Bajo qué versión del PEI se generó este documento."
    )
    
    # Enlace técnico (Opcional, pero recomendado para auditoría cruzada)
    log_origen = models.OneToOneField(
        AIUsageLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Enlace al log técnico que generó este documento."
    )

    # CONTENIDO
    contenido = models.TextField(help_text="Respuesta oficial de la IA en Markdown.")
    
    # EVIDENCIA (SNAPSHOT)
    contexto_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        FOTO EXACTA de los datos usados (Notas, Observaciones) al momento de generar.
        Sirve como evidencia inmutable.
        """
    )

    # ESTADO
    creado_en = models.DateTimeField(auto_now_add=True)
    es_publico = models.BooleanField(
        default=True, 
        help_text="Si es True, acudientes o directores pueden verlo."
    )

    class Meta:
        verbose_name = "Documento IA Oficial"
        verbose_name_plural = "Documentos IA Oficiales"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', 'tipo', 'periodo']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario} ({self.creado_en.strftime('%Y-%m-%d')})"

    def save(self, *args, **kwargs):
        # Generar título automático si no existe
        if not self.titulo:
            self.titulo = f"{self.get_tipo_display()} - {timezone.now().strftime('%d/%m/%Y')}"
        super().save(*args, **kwargs)


#desde aqui agrego la funcion de archivar el observardor 
# En tasks/models.py

class ObservadorArchivado(models.Model):
    """
    Modelo histórico que almacena el PDF del observador disciplinario
    en el momento exacto del retiro del estudiante.
    """
    estudiante_nombre = models.CharField(max_length=200)
    estudiante_username = models.CharField(max_length=150)
    
    # [NUEVO] Campo CRÍTICO: Permite diferenciar el observador de 2024 del de 2025
    # Se pone un default para que la migración no falle con datos existentes.
    anio_lectivo_archivado = models.CharField(
        max_length=20, 
        default='2025-2026', 
        verbose_name="Año Lectivo"
    )
    
    fecha_archivado = models.DateTimeField(auto_now_add=True)
    
    # Usuario que realizó la eliminación (El admin)
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    # El archivo PDF final
    archivo_pdf = models.FileField(upload_to='archivos/observadores_retirados/')

    class Meta:
        verbose_name = "Observador Archivado (Retirado)"
        verbose_name_plural = "Observadores Archivados"
        # Optimización Nivel Dios: Índice compuesto para búsquedas ultra-rápidas
        indexes = [
            models.Index(fields=['estudiante_username', 'anio_lectivo_archivado']),
        ]

    def __str__(self):
        return f"Observador: {self.estudiante_nombre} ({self.anio_lectivo_archivado})"
# En tasks/models.py

class Seguimiento(models.Model):
    TIPO_CHOICES = [
        ('CONVIVENCIA', 'Convivencia'),
        ('ACADEMICO', 'Académico'),
        ('PSICOLOGIA', 'Psicología'),
        ('FELICITACION', 'Felicitación / Reconocimiento'), # <--- NUEVA OPCIÓN AGREGADA
    ]
    
    estudiante = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seguimientos_recibidos')
    profesional = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seguimientos_realizados')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
    descripcion = models.TextField(verbose_name="Detalle Principal")
    
    # <--- ESTE ES EL CAMPO QUE FALTABA PARA QUE EL PDF MUESTRE EL SEGUNDO TEXTO
    observaciones_adicionales = models.TextField(blank=True, null=True, verbose_name="Observaciones Adicionales")
    
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante.username}"


###observador del profesor 
# tasks/models.py

# Aseguúrate de tener estos imports al inicio del archivo
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.db.models import Max

# ... (otros modelos anteriores) ...

class ActaInstitucional(models.Model):
    """
    Modelo profesional para la gestión documental institucional.
    Soporta gobernanza escolar, procesos disciplinarios, académicos y descargos.
    """
    
    TIPO_ACTA_CHOICES = (
        # --- GOBIERNO ESCOLAR Y DIRECTIVOS ---
        ('CONSEJO_DIRECTIVO', '🏛️ Consejo Directivo'),
        ('CONSEJO_ACADEMICO', '🎓 Consejo Académico'),
        ('RECTORIA', 'Despacho de Rectoría'),
        ('COORDINACION', 'Reunión de Coordinación'),
        
        # --- COMITÉS Y COMISIONES ---
        ('COMITE_CONVIVENCIA', '⚖️ Comité de Convivencia Escolar'),
        ('COMISION_EVALUACION', '📊 Comisión de Evaluación y Promoción'),
        ('COMITE_CALIDAD', '✅ Comité de Calidad / Gestión'),
        ('COMITE_INCLUSION', '🌈 Comité de Inclusión'),

        # --- GESTIÓN DOCENTE ---
        ('REUNION_AREA', '📚 Reunión de Área / Departamento'),
        ('CLAUSTRO', '👥 Claustro General de Docentes'),
        ('JORNADA_PEDAGOGICA', '🧠 Jornada Pedagógica'),

        # --- SEGUIMIENTO Y CASOS ---
        ('DESCARGOS', '⚠️ Diligencia de Descargos'),
        ('ACTA_COMPROMISO', '🤝 Acta de Compromiso (Académico/Convivencial)'),
        ('MEDIACION', '🕊️ Acta de Mediación / Conciliación'),
        ('SITUACION_ESPECIAL', '🚨 Protocolo de Situación Tipo II / III'),

        # --- COMUNIDAD ---
        ('REUNION_PADRES', '👨‍👩‍👧‍👦 Reunión de Padres de Familia'),
        ('ASOCIACION_PADRES', 'Asociación de Padres (Asopadres)'),
        ('CONSEJO_ESTUDIANTIL', 'Consejo Estudiantil'),
        
        ('OTRO', '📝 Otro / General'),
    )

    # 1. Identificación Única
    consecutivo = models.PositiveIntegerField(
        editable=False, 
        unique=True, 
        verbose_name="No. Acta",
        db_index=True
    )
    titulo = models.CharField(max_length=255, verbose_name="Asunto / Título Oficial")
    tipo = models.CharField(max_length=50, choices=TIPO_ACTA_CHOICES, default='OTRO')
    
    # 2. Detalles Logísticos
    lugar = models.CharField(max_length=200, blank=True, null=True, verbose_name="Lugar o Sala")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora de Inicio")
    hora_fin = models.TimeField(null=True, blank=True, verbose_name="Hora de Finalización")
    
    # 3. Personas Clave (Aquí agregamos al IMPLICADO)
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='actas_creadas',
        verbose_name="Secretario(a) / Elaboró"
    )
    
    # Nuevo campo vital para Descargos/Seguimiento
    implicado = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='actas_implicado',
        verbose_name="Persona Citada / Implicada"
    )

    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='actas_participacion',
        blank=True,
        verbose_name="Asistentes Registrados"
    )
    
    asistentes_externos = models.TextField(
        blank=True, 
        help_text="Nombres completos y cargos de invitados externos."
    )

    # 4. Contenido Estructurado
    orden_dia = models.TextField(blank=True, verbose_name="Orden del Día")
    contenido = models.TextField(verbose_name="Desarrollo y Discusiones")
    compromisos = models.TextField(blank=True, null=True, verbose_name="Acuerdos y Tareas")
    
    # 5. Evidencias y Auditoría
    archivo_adjunto = models.FileField(upload_to='actas/adjuntos/%Y/%m/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Acta Oficial"
        verbose_name_plural = "Libro de Actas"
        ordering = ['-consecutivo']

    def __str__(self):
        return f"Acta #{self.consecutivo:04d} - {self.titulo}"

    def save(self, *args, **kwargs):
        # Lógica atómica para garantizar consecutivos sin huecos ni duplicados
        if self.consecutivo is None:
            with transaction.atomic():
                # Bloqueo de fila para evitar condiciones de carrera en sistemas con alto tráfico
                max_val = ActaInstitucional.objects.select_for_update().aggregate(Max('consecutivo'))['consecutivo__max']
                self.consecutivo = (max_val or 0) + 1
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

#numero de identificacion

# ... (Tu código existente arriba permanece igual) ...

# ==========================================
#  ARQUITECTURA EDUTECH TIER 500K (NUEVA)
# ==========================================

class BancoLogro(models.Model):
    """
    Repositorio central de logros pedagógicos.
    """
    GRADOS_CHOICES = [
        ('6', 'Sexto'), ('7', 'Séptimo'), ('8', 'Octavo'), 
        ('9', 'Noveno'), ('10', 'Décimo'), ('11', 'Once')
    ]

    materia_referencia = models.CharField(max_length=100, db_index=True)
    grado_referencia = models.CharField(max_length=20, choices=GRADOS_CHOICES, db_index=True)
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    
    # Taxonomía
    es_cognitivo = models.BooleanField(default=True, verbose_name="Saber")
    es_procedimental = models.BooleanField(default=False, verbose_name="Hacer")
    es_actitudinal = models.BooleanField(default=False, verbose_name="Ser")
    
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Banco de Logro"
        indexes = [
            models.Index(fields=['materia_referencia', 'grado_referencia']),
            models.Index(fields=['titulo']),
        ]

    def __str__(self):
        return f"[{self.materia_referencia}] {self.titulo}"


class DefinicionNota(models.Model):
    """
    Configuración dinámica de la evaluación (Columnas de la sábana).
    """
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='plan_evaluacion')
    periodo = models.ForeignKey('Periodo', on_delete=models.CASCADE, related_name='plan_evaluacion')
    
    nombre = models.CharField(max_length=100)
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    orden = models.PositiveIntegerField(default=1)
    
    # CORREGIDO: Quitamos null=True para evitar inconsistencias en templates
    temas = models.TextField(help_text="Temas evaluados", blank=True, default="")
    subtemas = models.TextField(blank=True, default="")
    
    logros_asociados = models.ManyToManyField(BancoLogro, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden']
        unique_together = ['materia', 'periodo', 'orden'] 

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"


class NotaDetallada(models.Model):
    """
    MODELO NUEVO (Convivirá con 'Nota' durante la migración).
    """
    definicion = models.ForeignKey(DefinicionNota, on_delete=models.CASCADE, related_name='calificaciones')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mis_notas_v2')
    
    valor = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)]
    )
    
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['definicion', 'estudiante']
        indexes = [
            models.Index(fields=['estudiante', 'definicion']),
        ]

    def __str__(self):
        return f"{self.estudiante} - {self.definicion.nombre}: {self.valor}"


##mejoras de la ia 

# tasks/models.py

from django.db import models

class InstitucionKnowledgeBase(models.Model):
    """
    CEREBRO INSTITUCIONAL: Almacena la 'Verdad' del colegio de forma resumida.
    Optimizada para ahorrar tokens (no se sube el PDF a la IA, sino el resumen_ia).
    """
    TIPO_CHOICES = [
        ('PEI', 'Proyecto Educativo (Misión/Visión)'),
        ('MANUAL', 'Manual de Convivencia (Reglas)'),
        ('EVALUACION', 'Sistema de Evaluación (Escala Notas)'),
    ]

    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        unique=True,
        verbose_name="Tipo de Documento"
    )
    
    contenido_texto = models.TextField(
        verbose_name="Texto Legal Completo (Referencia)", 
        blank=True,
        help_text="Pega aquí el texto original del PDF por si necesitas consultarlo después."
    )
    
    # 🔥 LA IA LEERÁ SOLO ESTE CAMPO (Ahorro de Tokens)
    resumen_ia = models.TextField(
        verbose_name="Instrucciones Lógicas para IA",
        help_text="Reglas RESUMIDAS y CLARAS. Ej: 'Falta leve = Retardo. Aprueba con 3.0'.",
        blank=False # Obligatorio, sin esto la IA no funciona
    )
    
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cerebro Institucional (IA)"
        verbose_name_plural = "Reglas Institucionales (IA)"
        ordering = ['tipo']

    def __str__(self):
        return f"{self.get_tipo_display()} (Actualizado: {self.ultima_actualizacion.strftime('%d/%m')})"



# ==========================================
# ARQUITECTURA DE IMPORTACIÓN (ZERO-FAILURE V2)
# ==========================================

class ImportBatch(models.Model):
    """
    LA BÓVEDA DE AUDITORÍA:
    Rastrea cada intento de subida.
    MEJORA: Incluye Hash MD5 para evitar duplicados y lógica de bloqueo.
    """
    ESTADOS = [
        ('PENDING', '⏳ Analizando Estructura'),
        ('MAPPING', '🗺️ Esperando Mapeo de Columnas'),
        ('STAGING', '🛡️ En Cuarentena (Validando)'),
        ('READY', '✅ Listo para Importar'),
        ('IMPORTING', '🚀 Escribiendo en Producción'),
        ('COMPLETED', '🏆 Finalizado con Éxito'),
        ('FAILED', '❌ Fallido'),
        ('ROLLED_BACK', '⏪ Revertido (Deshecho)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cargas_masivas')
    archivo_original = models.FileField(upload_to='imports/%Y/%m/%d/')
    
    # CRÍTICO: Huella digital del archivo para prevenir duplicados exactos
    file_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    
    nombre_archivo = models.CharField(max_length=255)
    tipo_modelo = models.CharField(max_length=50, db_index=True, help_text="Ej: 'Estudiante', 'Profesor', 'Nota'")
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDING', db_index=True)
    log_errores = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    
    # Métricas de rendimiento (KPIs)
    total_filas = models.IntegerField(default=0)
    filas_procesadas = models.IntegerField(default=0)
    filas_exitosas = models.IntegerField(default=0)
    filas_con_error = models.IntegerField(default=0)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', 'creado_en']),
            models.Index(fields=['estado']),
            models.Index(fields=['file_hash']), # Búsqueda rápida de duplicados
        ]
        verbose_name = "Lote de Importación"

    def __str__(self):
        return f"[{self.get_estado_display()}] {self.tipo_modelo} - {self.nombre_archivo}"

    def save(self, *args, **kwargs):
        # Auto-calculo del Hash MD5 al guardar si es nuevo
        if not self.pk and self.archivo_original:
            md5 = hashlib.md5()
            for chunk in self.archivo_original.chunks():
                md5.update(chunk)
            self.file_hash = md5.hexdigest()
        super().save(*args, **kwargs)


class StagingRow(models.Model):
    """
    EL ÁREA DE CUARENTENA:
    MEJORA: Agregamos 'snapshot_backup' para permitir Rollback de actualizaciones (UPDATES),
    no solo de creaciones (INSERTS).
    """
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='filas_staging')
    numero_fila = models.IntegerField(db_index=True)
    
    data_original = models.JSONField(help_text="Datos crudos del Excel")
    data_normalizada = models.JSONField(null=True, blank=True, help_text="Datos limpios tras pasar por DataGuard")
    
    es_valido = models.BooleanField(default=False, db_index=True)
    errores = models.JSONField(default=list, blank=True)
    
    # TRAZABILIDAD Y ROLLBACK
    # 1. Si creamos un objeto nuevo, guardamos su ID aquí.
    id_objeto_creado = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    
    # 2. Si ACTUALIZAMOS un objeto existente, guardamos cómo estaba ANTES aquí.
    # Esto permite el "Undo" verdadero.
    snapshot_backup = models.JSONField(null=True, blank=True, help_text="Copia de seguridad del registro antes de ser modificado")

    class Meta:
        ordering = ['numero_fila']
        verbose_name = "Fila en Staging"

class ColumnMapping(models.Model):
    """
    EL CEREBRO (MEMORIA DEL SISTEMA):
    Aprende de las decisiones del usuario.
    """
    institucion_id = models.IntegerField(null=True, blank=True, db_index=True)
    modelo_objetivo = models.CharField(max_length=50)
    nombre_columna_csv = models.CharField(max_length=255) # "Apellido 1"
    campo_sistema = models.CharField(max_length=100)      # "last_name"
    
    confianza = models.FloatField(default=1.0) # 1.0 = Humano, <1.0 = IA
    usado_veces = models.IntegerField(default=1, help_text="Peso para el algoritmo de sugerencia")
    
    last_used = models.DateTimeField(auto_now=True) # Para saber si el mapeo es obsoleto

    class Meta:
        unique_together = ('modelo_objetivo', 'nombre_columna_csv', 'institucion_id')
        verbose_name = "Memoria de Mapeo"

    def __str__(self):
        return f"{self.nombre_columna_csv} -> {self.campo_sistema} (x{self.usado_veces})"



# --- AGREGAR AL FINAL DE tasks/models.py ---
#Version vieja antes del cierre del ano 
#class HistorialAcademico(models.Model):
    """
    BÓVEDA HISTÓRICA (Tabla de Destino):
    Aquí es donde aterrizan los datos finales después de la importación.
    Soporta versionado para poder hacer 'Deshacer' (Rollback).
    """
    # Relación con el estudiante (Ajusta 'Perfil' si tu modelo de usuario se llama diferente)
    #estudiante = models.ForeignKey('Perfil', on_delete=models.CASCADE, related_name='historiales')
    
    # Contexto Académico
    #anio_lectivo = models.IntegerField(db_index=True)
    #nombre_institucion = models.CharField(max_length=255, default="Sistema")
    
    # LAS NOTAS: Guardadas en JSON para flexibilidad total (Matemáticas, Inglés, etc.)
    #calificaciones_json = models.JSONField(default=dict)
    
    # Auditoría y Trazabilidad
    #meta_confianza = models.JSONField(default=dict, help_text="Evidencia de los valores originales del Excel")
    #lote_origen = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, null=True, related_name='registros_creados')
    
    # Sistema de Versionado (Snapshot Pattern)
    #version = models.IntegerField(default=1)
    #is_active = models.BooleanField(default=True, db_index=True) # Soft Delete
    #parent_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    
    #created_at = models.DateTimeField(auto_now_add=True)

    
    #class Meta:
        #ordering = ['-anio_lectivo', '-version']
        #indexes = [
            #models.Index(fields=['estudiante', 'anio_lectivo', 'is_active']),
        #]
        #verbose_name = "Historial Académico"
        #verbose_name_plural = "Historiales Académicos"

    #def __str__(self):
        #return f"{self.estudiante} - {self.anio_lectivo} (v{self.version})"

class HistorialAcademico(models.Model):
    """
    📚 BÓVEDA HISTÓRICA (Snapshot Inmutable)
    Guarda el estado congelado del estudiante al final del año lectivo.
    Incluye datos crudos (JSON), métricas (Promedio) y evidencia física (PDF).
    """
    
    # 1. IDENTIFICACIÓN Y RELACIONES
    # Relación con el Perfil del estudiante (Asegúrate que 'Perfil' exista en tu app)
    estudiante = models.ForeignKey(
        'Perfil', 
        on_delete=models.CASCADE, 
        related_name='historiales',
        help_text="Perfil del estudiante al momento del cierre."
    )
    
    # 2. CONTEXTO ACADÉMICO (FOTO DEL MOMENTO)
    anio_lectivo = models.IntegerField(db_index=True, help_text="Año escolar cerrado (Ej: 2026)")
    nombre_institucion = models.CharField(max_length=255, default="Sistema Stratos")
    curso_snapshot = models.CharField(
        max_length=100, 
        help_text="Nombre del curso en el momento exacto del cierre (Ej: 601, Transición)."
    )
    
    # 3. KPIS Y MÉTRICAS (PARA REPORTES RÁPIDOS)
    promedio_final = models.FloatField(default=0.0, db_index=True)
    puesto_ocupado = models.IntegerField(null=True, blank=True, help_text="Puesto en el curso según promedio.")
    
    # 4. VEREDICTO FINAL (SIEE)
    ESTADOS = [
        ('PROMOVIDO', 'Promovido'),  # Pasa al siguiente grado
        ('REPROBADO', 'Reprobado'),  # Repite el grado
        ('GRADUADO', 'Graduado'),    # Termina ciclo (Grado 11)
        ('PENDIENTE', 'Pendiente'),  # Requiere revisión manual
        ('RETIRADO', 'Retirado')     # Se fue antes del cierre
    ]
    estado_final = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='PENDIENTE', 
        db_index=True
    )

    # 5. DATA CAPSULE (LA "CAJA NEGRA")
    # Guarda las notas exactas en formato JSON para no depender de tablas externas.
    # Ejemplo: {"Matemáticas": 4.5, "Español": 3.2, "Convivencia": 5.0}
    calificaciones_json = models.JSONField(default=dict)
    
    # 6. EVIDENCIA FÍSICA (EL PDF) 🔥 CRÍTICO PARA TU REQUERIMIENTO
    archivo_boletin = models.FileField(
        upload_to='historiales/boletines/%Y/', 
        null=True, 
        blank=True,
        help_text="Copia digital inmutable del boletín entregado a los padres."
    )
    
    # 7. AUDITORÍA Y TRAZABILIDAD (VERSIONADO)
    meta_confianza = models.JSONField(
        default=dict, 
        help_text="Metadatos técnicos: materias perdidas, usuario que ejecutó el cierre, fecha exacta."
    )
    
    # Sistema de Versionado (Snapshot Pattern)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True) # Soft Delete para "Deshacer"
    parent_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    
    created_at = models.DateTimeField(auto_now_add=True)

    # Descomenta si usas ImportBatch en otro lado
    # lote_origen = models.ForeignKey('ImportBatch', on_delete=models.PROTECT, null=True, related_name='registros_creados')

    class Meta:
        ordering = ['-anio_lectivo', '-version']
        indexes = [
            # Índices compuestos para búsquedas ultra-rápidas
            models.Index(fields=['estudiante', 'anio_lectivo', 'is_active']),
        ]
        # Evita duplicados: Un estudiante solo puede tener UN historial activo por año y versión
        unique_together = ('estudiante', 'anio_lectivo', 'version')
        verbose_name = "Historial Académico"
        verbose_name_plural = "Historiales Académicos"

    def __str__(self):
        return f"{self.estudiante} - {self.anio_lectivo} [{self.estado_final}] (PDF: {'✅' if self.archivo_boletin else '❌'})"


def documento_path_builder(instance, filename):
    """
    Genera una ruta de almacenamiento segura, particionada y aislada por tipo de riesgo.
    
    Estrategia de Seguridad:
    - Los archivos ejecutables se aíslan en carpetas '/binaries/' para facilitar 
      reglas de firewall o antivirus a nivel de servidor.
    - Se usa UUID v4 para impedir la predicción de nombres de archivo.
    """
    ext = filename.split('.')[-1].lower()
    filename_secure = f"{instance.uuid}.{ext}"
    
    # Aislamiento de contenido riesgoso
    subfolder = instance.tipo
    if ext in ['exe', 'msi', 'bat', 'sh', 'bin']:
        subfolder = f"{instance.tipo}/quarantine_binaries"
    
    return f"historico/{instance.anio_lectivo}/{subfolder}/{filename_secure}"

class DocumentoHistorico(models.Model):
    """
    🏢 REPOSITORIO DOCUMENTAL INDUSTRIAL (EDMS Tier-1)
    
    Infraestructura diseñada para la preservación digital de activos académicos,
    incluyendo soporte para formatos legacy (Software antiguo) y Data (Excel).
    """
    
    TIPOS_DOCUMENTO = [
        ('OBSERVADOR', '📜 Observador / Disciplina'),
        ('BOLETIN', '📊 Boletín de Calificaciones'),
        ('ACTA', '⚖️ Acta de Comisión/Promoción'),
        ('CERTIFICADO', '🎓 Certificado de Estudio'),
        ('MATRICULA', '📝 Ficha de Matrícula'),
        ('PAZ_SALVO', '💰 Paz y Salvo'),
        ('DOCUMENTO_ID', '🆔 Documento de Identidad'),
        ('CLINICO', '🏥 Soporte Clínico/Médico'),
        ('LEGAL', '⚖️ Soporte Legal/Jurídico'),
        ('SOFTWARE_LEGACY', '💾 Software Educativo / Ejecutable'), # Soporte EXE
        ('DATA_DUMP', '🗃️ Base de Datos / Excel'),               # Soporte Excel
        ('OTRO', '📁 Otro Documento'),
    ]

    # --- IDENTIFICACIÓN ÚNICA ---
    uuid = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True, 
        db_index=True, 
        help_text="Identificador inmutable para referencias seguras (Anti-Enumeration)"
    )
    
    # --- RELACIONES JERÁRQUICAS ---
    estudiante = models.ForeignKey(
        'Perfil', 
        on_delete=models.CASCADE, 
        related_name='documentos_historicos', 
        null=True, 
        blank=True, 
        db_index=True
    )
    
    # --- CLASIFICACIÓN ---
    anio_lectivo = models.IntegerField(
        _("Año Lectivo"), 
        help_text="Año histórico del activo (ej: 1998)", 
        db_index=True
    )
    tipo = models.CharField(
        max_length=20, 
        choices=TIPOS_DOCUMENTO, 
        default='OTRO', 
        db_index=True
    )
    
    # --- EL ACTIVO DIGITAL (CORE) ---
    archivo = models.FileField(
        upload_to=documento_path_builder,
        validators=[FileExtensionValidator(allowed_extensions=[
            # Documentación Estándar
            'pdf', 'doc', 'docx', 'txt', 'rtf',
            # Evidencia Gráfica
            'jpg', 'jpeg', 'png', 'svg', 'webp',
            # Archivos Comprimidos
            'zip', 'rar', '7z', 'tar', 'gz',
            # Data & Hojas de Cálculo (Solicitado)
            'xlsx', 'xls', 'csv', 'json', 'xml',
            # Ejecutables Legacy (Solicitado - Manejo con Precaución)
            'exe', 'msi' 
        ])],
        help_text="Soporta Documentos, Imágenes, Excel y Ejecutables Legacy. Máx 100MB."
    )
    
    # --- METADATOS DE INTEGRIDAD & AUDITORÍA ---
    nombre_original = models.CharField(max_length=255, help_text="Nombre original sanitizado")
    extension = models.CharField(max_length=10, blank=True, editable=False)
    peso_kb = models.PositiveIntegerField(default=0, editable=False, help_text="Peso en Kilobytes")
    
    # Hash SHA-256: Huella digital criptográfica para verificar que el EXE/Excel no ha sido alterado (Integridad)
    hash_sha256 = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    
    # Metadata JSON: Para almacenar versión del software, autor del Excel, OCR, etc.
    metadata = models.JSONField(default=dict, blank=True)

    # --- TRAZABILIDAD ---
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # --- FLAGS DE SISTEMA ---
    procesado_automaticamente = models.BooleanField(default=False)
    es_confidencial = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Documento Histórico"
        verbose_name_plural = "Repositorio Digital"
        ordering = ['-anio_lectivo', 'tipo', 'nombre_original']
        indexes = [
            models.Index(fields=['estudiante', 'anio_lectivo', 'tipo']),
            models.Index(fields=['hash_sha256']),
        ]

    def __str__(self):
        return f"[{self.anio_lectivo}] {self.get_tipo_display()} - {self.nombre_original}"

    def save(self, *args, **kwargs):
        """
        Sobreescritura Industrial:
        1. Sanitiza nombres.
        2. Calcula huella SHA-256 (Integridad).
        3. Calcula peso.
        """
        if self.archivo and not self.hash_sha256:
            # Captura nombre original si es nuevo
            self.nombre_original = self.nombre_original or os.path.basename(self.archivo.name)
            self.extension = self.nombre_original.split('.')[-1].lower()
            
            # Cálculo de Hash (Stream-safe para archivos grandes como .exe de 100MB)
            md5 = hashlib.sha256()
            for chunk in self.archivo.chunks():
                md5.update(chunk)
            
            self.hash_sha256 = md5.hexdigest()
            self.peso_kb = self.archivo.size // 1024

        super().save(*args, **kwargs)

    @property
    def es_riesgoso(self):
        """Retorna True si el archivo requiere advertencia de seguridad al descargar"""
        return self.extension in ['exe', 'msi', 'bat', 'xlsm']

    @property
    def icon_class(self):
        """Retorna clase de FontAwesome para UI según el tipo de archivo"""
        icons = {
            'pdf': 'fa-file-pdf text-danger',
            'zip': 'fa-file-archive text-warning',
            'rar': 'fa-file-archive text-warning',
            '7z':  'fa-file-archive text-warning',
            
            # Imágenes
            'jpg':  'fa-file-image text-info',
            'jpeg': 'fa-file-image text-info',
            'png':  'fa-file-image text-info',
            
            # Data / Excel
            'xlsx': 'fa-file-excel text-success',
            'xls':  'fa-file-excel text-success',
            'csv':  'fa-file-csv text-success',
            'xml':  'fa-file-code text-secondary',
            
            # Ejecutables / Software
            'exe': 'fa-microchip text-dark',
            'msi': 'fa-box-open text-dark',
        }
        return icons.get(self.extension, 'fa-file text-secondary')


class CierreAnualLog(models.Model):
    """
    🦅 BITÁCORA DEL PROTOCOLO FÉNIX
    Registro forense de la ejecución del cierre de año.
    """
    anio_cerrado = models.IntegerField()
    anio_nuevo = models.IntegerField()
    fecha_ejecucion = models.DateTimeField(auto_now_add=True)
    ejecutado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    # Métricas de Impacto
    total_procesados = models.IntegerField(default=0)
    promovidos = models.IntegerField(default=0)
    reprobados = models.IntegerField(default=0)
    graduados = models.IntegerField(default=0)
    
    # The Data Capsule (Backup)
    archivo_backup = models.FileField(upload_to='security/backups/', null=True, blank=True)
    
    # Logs Técnicos
    exitoso = models.BooleanField(default=False)
    log_detalle = models.TextField(help_text="Traza técnica paso a paso")

    def __str__(self):
        return f"Cierre {self.anio_cerrado} -> {self.anio_nuevo}"



class BovedaSeguridad(models.Model):
    """
    🏦 BÓVEDA DIGITAL DE GRADO INDUSTRIAL
    Sistema de custodia de activos digitales con verificación de integridad 
    y sellado criptográfico.
    """
    # 1. TRAZABILIDAD DINÁMICA
    uuid_operacion = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nombre_identificador = models.CharField(max_length=150, db_index=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True, db_index=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name="respaldos_custodiados"
    )
    
    # 2. ALMACENAMIENTO RESILIENTE
    archivo_zip = models.FileField(
        upload_to='security/vault/%Y/%m/',
        help_text="Paquete encriptado de activos institucionales."
    )
    tamanio_mb = models.DecimalField(max_digits=12, decimal_places=2)

    # 3. VERIFICACIÓN CRIPTOGRÁFICA (The Integrity Shield)
    # Para asegurar que nadie modificó el ZIP directamente en el servidor
    checksum_sha256 = models.CharField(
        max_length=64, 
        editable=False, 
        help_text="Firma digital única del archivo para auditorías de integridad."
    )
    
    # 4. METADATOS DE AUDITORÍA (Snapshot Metadata)
    METADATOS_ESTRUCTURA = {
        'total_boletines': 0,
        'incluye_db': True,
        'version_sistema': '2.4.0',
        'engine': 'Fenix-Core-Industrial'
    }
    stats_contenido = models.JSONField(default=dict, help_text="Resumen detallado del contenido del paquete.")

    # 5. SEGURIDAD DE ACCESO
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True, help_text="Dispositivo desde donde se ordenó el respaldo.")

    class Meta:
        verbose_name = "Activo de Bóveda"
        verbose_name_plural = "Bóveda de Seguridad Institucional"
        ordering = ['-fecha_generacion']
        permissions = [
            ("can_restore_vault", "Puede ejecutar restauraciones desde la bóveda"),
            ("can_export_external", "Puede exportar archivos fuera del servidor"),
        ]

    def __str__(self):
        return f"REF: {self.uuid_operacion} | {self.nombre_identificador}"

    def verificar_integridad(self):
        """
        Calcula el hash del archivo actual y lo compara con el original.
        Si no coinciden, el archivo fue alterado o está corrupto.
        """
        sha256_hash = hashlib.sha256()
        with self.archivo_zip.open('rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() == self.checksum_sha256


