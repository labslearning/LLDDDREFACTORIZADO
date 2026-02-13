# apps/academics/forms.py
from django import forms
from django.contrib.auth.models import User
from tasks.models import (
    Perfil, Curso, Materia, AsignacionMateria, 
    Matricula, GRADOS_CHOICES
)
from apps.tenancy.utils import get_current_tenant

# ======================================================
# 📊 GESTIÓN DE DATOS MASIVOS
# ======================================================
class BulkCSVForm(forms.Form):
    """Formulario para la carga masiva de estudiantes vía CSV."""
    # Sincronizado con la vista: 'archivo_csv'
    archivo_csv = forms.FileField(
        label="Seleccionar archivo CSV",
        help_text="Columnas requeridas: first_name, last_name, email, documento, grado."
    )
    anio_escolar = forms.CharField(
        label="Año Escolar",
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2025-2026'})
    )

# ======================================================
# 👨‍🏫 REGISTRO DE DOCENTES (Resuelve el ImportError)
# ======================================================
class DocenteCreationForm(forms.ModelForm):
    """Formulario para crear la cuenta base del docente."""
    telefono = forms.CharField(max_length=15, required=False, label="Teléfono")
    numero_documento = forms.CharField(max_length=20, required=True, label="Documento de Identidad")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

# ======================================================
# 🎓 MATRICULAS (Resuelve el ImportError y aplica Filtro SaaS)
# ======================================================
class MatriculaForm(forms.ModelForm):
    """Formulario para matricular estudiante en curso."""
    class Meta:
        model = Matricula
        fields = ['estudiante', 'curso', 'anio_escolar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = get_current_tenant()
        if tenant:
            # 🛡️ AISLAMIENTO INDUSTRIAL: Solo alumnos y cursos de ESTE colegio
            self.fields['estudiante'].queryset = User.objects.filter(
                perfil__tenant=tenant, 
                perfil__rol='ESTUDIANTE'
            ).order_by('first_name')
            self.fields['curso'].queryset = Curso.objects.filter(tenant=tenant)
        
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-select'})

# ======================================================
# 🔗 ASIGNACIONES (Resuelve el ImportError y aplica Filtro SaaS)
# ======================================================
# apps/academics/forms.py

class AsignacionMateriaForm(forms.ModelForm):
    """Vincula un Docente con una Materia y un Curso."""
    class Meta:
        model = AsignacionMateria
        # ✅ 'intensidad_horaria' ELIMINADO de esta lista
        fields = ['docente', 'materia', 'curso'] 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = get_current_tenant()
        if tenant:
            # 🛡️ Aislamiento Industrial: Solo datos de este colegio
            self.fields['docente'].queryset = User.objects.filter(
                perfil__tenant=tenant, 
                perfil__rol='DOCENTE'
            ).order_by('first_name')
            self.fields['materia'].queryset = Materia.objects.filter(tenant=tenant)
            self.fields['curso'].queryset = Curso.objects.filter(tenant=tenant)

        # Estética de los campos
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-select'})# ======================================================
# 📱 OTROS FORMULARIOS
# ======================================================
class TelefonoAcudienteForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['telefono_sms', 'recibir_sms']
        widgets = {
            'telefono_sms': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{10}'}),
            'recibir_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['grado', 'seccion', 'anio_escolar', 'capacidad_maxima', 'director']
        widgets = {
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'seccion': forms.TextInput(attrs={'class': 'form-control'}),
            'capacidad_maxima': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ['nombre', 'curso']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
        }


# apps/academics/forms.py

class AsignacionMateriaForm(forms.ModelForm):
    """Vincula un Docente con una Materia y un Curso sin intensidad horaria."""
    class Meta:
        model = AsignacionMateria
        # ❌ Eliminado: 'intensidad_horaria'
        fields = ['docente', 'materia', 'curso'] 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = get_current_tenant()
        if tenant:
            # 🛡️ Aislamiento: Solo personal y datos de este colegio
            self.fields['docente'].queryset = User.objects.filter(
                perfil__tenant=tenant, 
                perfil__rol='DOCENTE'
            ).order_by('first_name')
            self.fields['materia'].queryset = Materia.objects.filter(tenant=tenant)
            self.fields['curso'].queryset = Curso.objects.filter(tenant=tenant)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-select'})