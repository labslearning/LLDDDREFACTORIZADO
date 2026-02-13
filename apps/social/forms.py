# apps/social/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Post, Comment, SocialGroup, MensajeInterno

# IMPORTACIONES TEMPORALES DESDE EL MONOLITO (tasks)
# Esto permite que el sistema funcione mientras se migra el resto
from tasks.models import Perfil, Question, Answer

User = get_user_model()

# ==========================================================
# 👤 1. FORMULARIOS DE PERFIL Y USUARIO
# ==========================================================

class UserEditForm(forms.ModelForm):
    """Permite al usuario editar su información básica de cuenta."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'})
        }

class EditarPerfilForm(forms.ModelForm):
    """
    🛡️ Versión Robusta: Usa 'exclude' para evitar FieldError.
    Django cargará automáticamente los campos que SÍ existan en tu BD (como 'foto').
    """
    class Meta:
        model = Perfil
        exclude = ['user', 'tenant', 'rol', 'requiere_cambio_clave', 'es_director']
        widgets = {
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# ==========================================================
# 📰 2. FORMULARIOS DEL MURO SOCIAL Y GRUPOS
# ==========================================================

class PostForm(forms.ModelForm):
    """Formulario para publicaciones en el feed o grupos."""
    class Meta:
        model = Post
        fields = ['contenido', 'imagen']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '¿Qué quieres compartir?'
            }),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }

class CommentForm(forms.ModelForm):
    """Formulario para comentar publicaciones."""
    class Meta:
        model = Comment
        fields = ['contenido']
        widgets = {
            'contenido': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Escribe un comentario...'
            })
        }

class SocialGroupForm(forms.ModelForm):
    """Formulario para gestión de grupos institucionales."""
    class Meta:
        model = SocialGroup
        fields = ['name', 'description', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del grupo'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }

# ==========================================================
# ❓ 3. FORMULARIOS DEL FORO (MIGRACIÓN PENDIENTE)
# ==========================================================

class QuestionForm(forms.ModelForm):
    """Formulario para crear una pregunta en el Foro."""
    class Meta:
        model = Question
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Escribe tu pregunta...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Detalla tu pregunta...'}),
        }

class AnswerForm(forms.ModelForm):
    """Formulario para responder en el Foro."""
    class Meta:
        model = Answer
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Escribe tu respuesta...'}),
        }

# ==========================================================
# 💬 4. FORMULARIO DE CHAT INTERNO (MENSAJERÍA MASIVA)
# ==========================================================

class MensajeForm(forms.ModelForm):
    """
    Formulario de mensajería Multi-Tenant.
    Filtra destinatarios según el colegio (Tenant) del remitente.
    """
    DESTINOS_MASIVOS = [
        ('', '--- Opciones de Envío Masivo ---'),
        ('ALL_DOCENTES', 'Todos los Docentes'),
        ('ALL_ESTUDIANTES', 'Todos los Estudiantes'),
        ('ALL_ACUDIENTES', 'Todos los Acudientes'),
        ('ALL_STAFF', 'Personal Administrativo'),
        ('MIS_ESTUDIANTES', 'Mis Estudiantes (Solo Docentes)'),
        ('MIS_ACUDIENTES', 'Mis Acudientes (Solo Docentes)'),
    ]

    destinatario = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="--- Seleccionar usuario específico ---",
        widget=forms.Select(attrs={'class': 'form-select select2-user', 'id': 'destinatario_select'})
    )
    
    destinatario_rol_masivo = forms.ChoiceField(
        choices=DESTINOS_MASIVOS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'rol_masivo_select'})
    )

    destinatario_curso_masivo = forms.ChoiceField(
        choices=[], 
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'curso_masivo_select'})
    )

    class Meta:
        model = MensajeInterno
        fields = ['asunto', 'cuerpo', 'archivo']
        widgets = {
            'asunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto...'}),
            'cuerpo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Escribe tu mensaje...'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, user, *args, **kwargs):
        super(MensajeForm, self).__init__(*args, **kwargs)
        
        # 1. Filtro de seguridad: Solo usuarios del mismo colegio
        tenant = getattr(user.perfil, 'tenant', None)
        self.fields['destinatario'].queryset = User.objects.filter(
            perfil__tenant=tenant
        ).exclude(id=user.id).order_by('last_name')
        
        # 2. Lógica para cargar cursos (Solo roles autorizados)
        if hasattr(user, 'perfil') and user.perfil.rol in ['DOCENTE', 'ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA']:
            from apps.academics.models import Curso
            
            if user.perfil.rol == 'DOCENTE':
                from apps.academics.models import AsignacionMateria
                c_ids = AsignacionMateria.objects.filter(docente=user, activo=True).values_list('curso_id', flat=True)
                cursos = Curso.objects.filter(id__in=c_ids, activo=True)
            else:
                cursos = Curso.objects.filter(tenant=tenant, activo=True)
                
            opciones = [('', '--- Enviar a un curso ---')]
            for c in cursos:
                opciones.append((c.id, f"{c.nombre}"))
            self.fields['destinatario_curso_masivo'].choices = opciones
        else:
            # Usuarios sin permisos de envío masivo
            self.fields['destinatario_rol_masivo'].widget.attrs['disabled'] = True
            self.fields['destinatario_curso_masivo'].widget.attrs['disabled'] = True

    def clean(self):
        cleaned_data = super().clean()
        dest = cleaned_data.get('destinatario')
        rol = cleaned_data.get('destinatario_rol_masivo')
        curso = cleaned_data.get('destinatario_curso_masivo')
        
        count = sum(bool(x) for x in [dest, rol, curso])
        
        if count == 0:
            raise forms.ValidationError("Debes indicar a quién va dirigido el mensaje.")
        if count > 1:
            raise forms.ValidationError("Por favor, elige solo un método de envío a la vez.")
            
        return cleaned_data