# apps/academics/forms.py
from django import forms
from tasks.models import Perfil, Curso, Materia, GRADOS_CHOICES

# ======================================================
# 📊 GESTIÓN DE DATOS MASIVOS
# ======================================================
class BulkCSVForm(forms.Form):
    """Formulario para la carga masiva de estudiantes vía CSV."""
    csv_file = forms.FileField(
        label="Seleccionar archivo CSV",
        help_text="Columnas requeridas: first_name, last_name, email, grado, acudiente_email, etc."
    )
    anio_escolar = forms.CharField(
        label="Año Escolar",
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2025-2026'})
    )

# ======================================================
# 📱 COMUNICACIÓN Y REGISTRO (SMS)
# ======================================================
class TelefonoAcudienteForm(forms.ModelForm):
    """
    Formulario para que el acudiente registre su número de alertas.
    Se movió aquí porque es parte de la ficha académica del estudiante.
    """
    class Meta:
        model = Perfil
        fields = ['telefono_sms', 'recibir_sms']
        labels = {
            'telefono_sms': 'Número de Celular (10 dígitos)',
            'recibir_sms': 'Autorizo envío de alertas SMS',
        }
        widgets = {
            'telefono_sms': forms.TextInput(attrs={
                'placeholder': 'Ej: 3001234567',
                'class': 'form-control',
                'pattern': '[0-9]{10}'
            }),
            'recibir_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

# ======================================================
# 🏫 GESTIÓN ESTRUCTURAL (OPCIONAL PERO RECOMENDADO)
# ======================================================
class CursoForm(forms.ModelForm):
    """Para formalizar la creación de cursos en la vista gestionar_cursos."""
    class Meta:
        model = Curso
        fields = ['grado', 'seccion', 'anio_escolar', 'capacidad_maxima', 'director']
        widgets = {
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'seccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A, B, 1...'}),
            'capacidad_maxima': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class MateriaForm(forms.ModelForm):
    """Para formalizar la creación de materias."""
    class Meta:
        model = Materia
        fields = ['nombre', 'curso']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la materia'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
        }