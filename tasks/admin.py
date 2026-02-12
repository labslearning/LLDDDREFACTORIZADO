# tasks/admin.py

from django.contrib import admin
from .models import ObservadorArchivado # <--- Agrega el import arriba

from .models import PeriodoAcademico, PEIResumen, AIUsageLog, AIDocumento
# 1. IMPORTS UNIFICADOS (Tus modelos viejos + Los nuevos de IA)
from .models import (
    Perfil,
    Curso,
    Materia,
    Periodo,          # Tu periodo académico antiguo (calificaciones)
    Nota,
    Question,
    Answer,
    ChatRoom,
    ActiveUser,
    Matricula,
    AsignacionMateria,
    ActividadSemanal,
    LogroPeriodo,
    Convivencia,
    Acudiente,
    Institucion,
    # --- NUEVOS MODELOS DE IA (FASE 0 y 1) ---
    PeriodoAcademico, # Nuestro nuevo "Gobernador de IA"
    PEIResumen,       # El Cerebro Institucional
    AIUsageLog        # La Caja Negra
)

# ===================================================================
# REGISTRO DE TUS MODELOS EXISTENTES (NO TOCAR)
# ===================================================================
admin.site.register(Perfil)
admin.site.register(Curso)
admin.site.register(Materia)
admin.site.register(Periodo) # Este es tu periodo de notas original
admin.site.register(Nota)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(ChatRoom)
admin.site.register(ActiveUser)
admin.site.register(Matricula)
admin.site.register(AsignacionMateria)
admin.site.register(ActividadSemanal)
admin.site.register(LogroPeriodo)
admin.site.register(Convivencia)
admin.site.register(Acudiente)
admin.site.register(Institucion)

# ===================================================================
# NUEVA SECCIÓN: GOBERNANZA IA (AGREGADO POR EL CIRUJANO)
# ===================================================================

# 1. GOBERNADOR DE TIEMPO Y COSTOS
@admin.register(PeriodoAcademico)
class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin', 'activo', 'limite_intentos_profesor')
    list_editable = ('activo',) # Checkbox rápido para activar/desactivar
    list_filter = ('activo',)
    ordering = ('-fecha_inicio',)

# 2. CEREBRO PEI (AQUÍ PEGARÁS EL JSON)
@admin.register(PEIResumen)
class PEIResumenAdmin(admin.ModelAdmin):
    list_display = ('version', 'fecha_creacion', 'activo')
    readonly_fields = ('resumen_hash',) 
    
    fieldsets = (
        ('Control de Versión', {
            'fields': ('version', 'activo', 'comentarios_cambio')
        }),
        ('Cerebro Institucional', {
            'fields': ('contenido_estructurado', 'resumen_hash'),
            'description': 'Pegue aquí el JSON del PEI. Este es el conocimiento base de la IA.'
        }),
    )

# 3. AUDITORÍA DE USO (Solo lectura para seguridad)
@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'rol_usado', 'accion', 'tokens_entrada', 'tokens_salida', 'exitoso')
    list_filter = ('periodo', 'rol_usado', 'exitoso', 'accion')
    search_fields = ('usuario__username', 'error_mensaje')
    
    # Bloqueamos edición para garantizar integridad forense
    readonly_fields = [field.name for field in AIUsageLog._meta.fields] 
    
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIDocumento)
class AIDocumentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'usuario', 'periodo', 'creado_en')
    list_filter = ('tipo', 'periodo', 'creado_en')
    search_fields = ('titulo', 'usuario__username', 'usuario__first_name')
    readonly_fields = ('creado_en', 'contexto_snapshot', 'log_origen')
    
    fieldsets = (
        ('Información General', {
            'fields': ('titulo', 'tipo', 'usuario', 'periodo', 'es_publico')
        }),
        ('Contenido', {
            'fields': ('contenido',)
        }),
        ('Auditoría y Evidencia', {
            'fields': ('pei_version', 'log_origen', 'contexto_snapshot', 'creado_en'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ObservadorArchivado)
class ObservadorArchivadoAdmin(admin.ModelAdmin):
    list_display = ('estudiante_nombre', 'estudiante_username', 'fecha_archivado', 'eliminado_por')
    search_fields = ('estudiante_nombre', 'estudiante_username')
    readonly_fields = ('fecha_archivado', 'archivo_pdf', 'eliminado_por')
    list_filter = ('fecha_archivado',)