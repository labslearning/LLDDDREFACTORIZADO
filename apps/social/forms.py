# apps/social/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
# Importamos los modelos desde el legacy (tasks)
from tasks.models import Post, Comment, SocialGroup, Perfil, Question, Answer

User = get_user_model()

# ===================================================================
# 🛡️ MIXIN DE SEGURIDAD (Inyectado para autonomía de la App)
# ===================================================================
try:
    from tasks.utils import validar_lenguaje_apropiado
except ImportError:
    def validar_lenguaje_apropiado(texto): return True

class ContentSecurityMixin:
    """Valida que el contenido no tenga lenguaje ofensivo."""
    def validar_contenido_seguro(self, contenido, campo_nombre):
        if contenido and not validar_lenguaje_apropiado(contenido):
            raise ValidationError(
                f"El contenido en '{campo_nombre}' infringe las normas de convivencia."
            )
        return contenido

# ===================================================================
# 📱 FORMULARIOS DE CONTENIDO (FEED & FORO)
# ===================================================================

class PostForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Post
        fields = ['contenido', 'imagen', 'archivo']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '¿Qué estás pensando? Comparte con tu clase...'
            }),
            'imagen': forms.FileInput(attrs={'class': 'form-control'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_contenido(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('contenido'), 'Publicación')

class CommentForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Comment
        fields = ['contenido']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 1, 
                'placeholder': 'Escribe un comentario...'
            }),
        }

    def clean_contenido(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('contenido'), 'Comentario')

class QuestionForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Question
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título de tu duda'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean_title(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('title'), 'Título')

    def clean_content(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('content'), 'Contenido')

class AnswerForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Answer
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_content(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('content'), 'Respuesta')

# ===================================================================
# 👥 GESTIÓN DE COMUNIDAD (GRUPOS & PERFIL)
# ===================================================================

class SocialGroupForm(forms.ModelForm):
    class Meta:
        model = SocialGroup
        fields = ['name', 'description', 'image', 'tipo_privacidad']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del grupo'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'tipo_privacidad': forms.Select(attrs={'class': 'form-select'}),
        }

class UserEditForm(forms.ModelForm):
    """Formulario para datos básicos de cuenta."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class EditarPerfilForm(forms.ModelForm): # ✅ CORREGIDO: Era ModelForm, no ModelModelForm
    class Meta:
        model = Perfil
        fields = [
            'foto_portada', 'foto_perfil', 'biografia', 
            'hobbies', 'gustos_musicales', 'libros_favoritos', 
            'materia_favorita', 'metas_anio'
        ]
        widgets = {
            'biografia': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'hobbies': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'gustos_musicales': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'libros_favoritos': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'materia_favorita': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'metas_anio': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'foto_portada': forms.FileInput(attrs={'class': 'form-control'}),
            'foto_perfil': forms.FileInput(attrs={'class': 'form-control'}),
        }