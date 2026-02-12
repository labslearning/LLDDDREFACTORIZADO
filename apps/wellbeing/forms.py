# apps/wellbeing/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

# 🩸 CONEXIÓN CON EL LEGACY
from tasks.models import (
    Observacion, Seguimiento, ActaInstitucional, 
    Perfil, Matricula, Periodo, Curso
)

User = get_user_model()

# ===================================================================
# 🛡️ MIXIN DE SEGURIDAD (Sentinel Local)
# ===================================================================
try:
    from tasks.utils import validar_lenguaje_apropiado
except ImportError:
    def validar_lenguaje_apropiado(texto): return True

class ContentSecurityMixin:
    """Evita que se registre lenguaje ofensivo en el observador."""
    def validar_contenido_seguro(self, contenido, campo_nombre):
        if contenido and not validar_lenguaje_apropiado(contenido):
            raise ValidationError(
                f"El contenido en '{campo_nombre}' infringe las normas de convivencia escolar."
            )
        return contenido

# ===================================================================
# 📝 FORMULARIO DE OBSERVADOR (CON FILTRO DINÁMICO)
# ===================================================================
# apps/wellbeing/forms.py

class ObservacionForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Observacion
        # 💉 CIRUGÍA: Quitamos 'evidencia' de la lista porque no existe en el modelo
        fields = ['tipo', 'periodo', 'descripcion', 'compromisos_estudiante', 'compromisos_familia']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'periodo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalle la situación...'}),
            'compromisos_estudiante': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'compromisos_familia': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # Quitamos el widget de evidencia también
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.estudiante = kwargs.pop('estudiante', None)
        super().__init__(*args, **kwargs)

        # Lógica de periodos dinámica
        periodos_qs = Periodo.objects.none()
        if self.estudiante:
            matricula = Matricula.objects.filter(estudiante=self.estudiante, activo=True).first()
            if matricula and matricula.curso:
                periodos_qs = Periodo.objects.filter(curso=matricula.curso, activo=True).order_by('id')

        if not periodos_qs.exists():
            periodos_qs = Periodo.objects.filter(activo=True).order_by('id')

        self.fields['periodo'].queryset = periodos_qs

    def clean(self):
        cd = super().clean()
        if cd.get('descripcion'):
            self.validar_contenido_seguro(cd.get('descripcion'), 'Descripción')
        if cd.get('compromisos_estudiante'):
            self.validar_contenido_seguro(cd.get('compromisos_estudiante'), 'Compromisos Estudiante')
        return cd

# ===================================================================
# 🔍 FORMULARIO DE SEGUIMIENTO PROFESIONAL
# ===================================================================

class SeguimientoForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Seguimiento
        fields = ['tipo', 'descripcion', 'observaciones_adicionales']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'observaciones_adicionales': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_descripcion(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('descripcion'), 'Detalle')

# ===================================================================
# 📜 GESTIÓN DE ACTAS (CON AGRUPACIÓN DE PARTICIPANTES)
# ===================================================================

class ActaInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ActaInstitucional
        fields = [
            'titulo', 'tipo', 'implicado', 'lugar', 'fecha', 'hora_fin', 
            'participantes', 'asistentes_externos', 'orden_dia', 
            'contenido', 'compromisos', 'archivo_adjunto'
        ]
        widgets = {
            'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'participantes': forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
            'implicado': forms.Select(attrs={'class': 'form-control select2-single'}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'orden_dia': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'compromisos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 📂 ORGANIZACIÓN DE TEJIDO: Agrupar usuarios por rol para el buscador
        users = User.objects.filter(is_active=True).select_related('perfil').order_with_respect_to('last_name')
        
        docentes, directivos, estudiantes, acudientes = [], [], [], []

        for u in users:
            label = (u.id, f"{u.get_full_name()} ({u.username})")
            rol = getattr(u.perfil, 'rol', 'OTRO')
            
            if rol in ['DOCENTE', 'DIRECTOR_CURSO']: docentes.append(label)
            elif rol in ['ADMINISTRADOR', 'PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']: directivos.append(label)
            elif rol == 'ESTUDIANTE': estudiantes.append(label)
            elif rol == 'ACUDIENTE': acudientes.append(label)

        choices = [
            ('Estudiantes', estudiantes),
            ('Staff de Bienestar y Directivos', directivos),
            ('Cuerpo Docente', docentes),
            ('Padres y Acudientes', acudientes),
        ]
        
        self.fields['participantes'].choices = choices
        self.fields['implicado'].choices = [('', '--- Ninguno ---')] + choices