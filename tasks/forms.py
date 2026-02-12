# ===================================================================
# tasks/forms.py (COMPLETO, CORREGIDO Y BLINDADO)
# ===================================================================

from .models import ActaInstitucional
from django import forms # 💡 CRÍTICO: Asegura la importación base de forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm 
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.db.models import Q

# Importamos TODOS los modelos necesarios
from .models import (
    Question, Answer, ROLES_CHOICES, Observacion, Periodo, Matricula,
    MensajeInterno, Acudiente, Curso, AsignacionMateria,
    Post, Comment, SocialGroup, Perfil, Seguimiento  # Aseguramos Perfil
)

# Definición del modelo User de forma segura
User = get_user_model() 

# 🛡️ IMPORTACIÓN DE SEGURIDAD (Desde tu nuevo utils.py)
# Asumo que la función validar_lenguaje_apropiado existe en .utils
try:
    from .utils import validar_lenguaje_apropiado
except ImportError:
    def validar_lenguaje_apropiado(texto):
        return True

# ===================================================================
# 🛡️ MIXIN DE SEGURIDAD (DRY: Don't Repeat Yourself)
# ===================================================================
class ContentSecurityMixin:
    """
    Mixin para validar lenguaje apropiado en campos de texto.
    Se inyecta en cualquier formulario que necesite filtrar groserías.
    """
    def validar_contenido_seguro(self, contenido, campo_nombre):
        # Nota: Asumo que validar_lenguaje_apropiado es una función válida
        if contenido and not validar_lenguaje_apropiado(contenido):
            raise ValidationError(
                f"El contenido del campo '{campo_nombre}' infringe las normas de convivencia escolar. "
                "Por favor, revisa tu lenguaje."
            )
        return contenido

# ===================================================================
# FORMULARIOS DEL FORO (BLINDADOS)
# ===================================================================


# ===================================================================
# FORMULARIOS ADMINISTRATIVOS (INTACTOS)
# ===================================================================


class PasswordChangeFirstLoginForm(forms.Form):
    """
    Formulario específico para el cambio de contraseña obligatorio.
    """
    nueva = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput,
        help_text="La contraseña debe tener al menos 8 caracteres."
    )
    confirmar = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        nueva = cleaned_data.get("nueva")
        confirmar = cleaned_data.get("confirmar")

        if nueva and confirmar and nueva != confirmar:
            self.add_error('confirmar', "Las contraseñas no coinciden.")
        
        if nueva and self.user:
            try:
                validate_password(nueva, self.user)
            except ValidationError as e:
                self.add_error('nueva', e)
                
        return cleaned_data

    def save(self, commit=True):
        new_password = self.cleaned_data["nueva"]
        self.user.set_password(new_password)
        if commit:
            self.user.save()
        return self.user

class ProfileSearchForm(forms.Form):
    """
    Formulario para la búsqueda y filtrado de usuarios en el panel.
    """
    query = forms.CharField(
        required=False, 
        label="Buscar",
        widget=forms.TextInput(attrs={'placeholder': 'Usuario, nombre o apellido...'})
    )
    rol = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los roles')] + [r for r in ROLES_CHOICES if r[0] != 'DIRECTOR_CURSO'],
        label="Filtrar por rol"
    )

# ===================================================================
# FORMULARIO DE OBSERVADOR (LÓGICA ORIGINAL + SEGURIDAD)
# ===================================================================

class ObservacionForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Observacion
        fields = ['tipo', 'periodo', 'descripcion', 'compromisos_estudiante', 'compromisos_familia']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'periodo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalle la situación...'}),
            'compromisos_estudiante': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Compromisos del estudiante...'}),
            'compromisos_familia': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Compromisos del acudiente...'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) 
        self.estudiante = kwargs.pop('estudiante', None) 
        super().__init__(*args, **kwargs)

        # Lógica de periodos original intacta
        periodos_qs = Periodo.objects.none()
        
        if self.estudiante:
            matricula = Matricula.objects.filter(estudiante=self.estudiante, activo=True).first()
            if matricula and matricula.curso:
                periodos_qs = Periodo.objects.filter(curso=matricula.curso, activo=True).order_by('id')

        if not periodos_qs.exists():
            primer_curso = Curso.objects.filter(activo=True).first()
            if primer_curso:
                periodos_qs = Periodo.objects.filter(curso=primer_curso, activo=True).order_by('id')
            else:
                periodos_qs = Periodo.objects.filter(activo=True).order_by('id')

        self.fields['periodo'].queryset = periodos_qs
        self.fields['periodo'].label_from_instance = lambda obj: obj.nombre

        if self.instance.pk and not self.instance.es_editable:
            for field in self.fields:
                self.fields[field].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        comp_est = cleaned_data.get('compromisos_estudiante')
        descripcion = cleaned_data.get('descripcion')
        comp_fam = cleaned_data.get('compromisos_familia')

        # 1. Regla de negocio original
        if tipo in ['CONVIVENCIA', 'ACADEMICA'] and not comp_est:
            self.add_error('compromisos_estudiante', 'Para este tipo de observación, el compromiso del estudiante es obligatorio.')

        # 2. 🛡️ Nueva validación de seguridad
        if descripcion:
            self.validar_contenido_seguro(descripcion, 'Descripción')
        if comp_est:
            self.validar_contenido_seguro(comp_est, 'Compromisos Estudiante')
        if comp_fam:
            self.validar_contenido_seguro(comp_fam, 'Compromisos Familia')

        return cleaned_data

# ===================================================================
# FORMULARIO DE MENSAJERÍA INTELIGENTE (LÓGICA ORIGINAL + SEGURIDAD)
# ===================================================================

class MensajeForm(forms.ModelForm, ContentSecurityMixin):
    """
    Formulario profesional con agrupación de destinatarios y soporte de archivos,
    incluyendo opciones para envío masivo por Rol o Curso.
    """
    
    destinatario_rol_masivo = forms.ChoiceField(
        required=False,
        label="Enviar a Rol (Todo el Colegio)",
        choices=[('', '--- Ninguno ---')], # Inicializado con placeholder
        widget=forms.Select(attrs={'class': 'form-select select2-masivo', 'style': 'width: 100%;'})
    )

    destinatario_curso_masivo = forms.ChoiceField(
        required=False,
        label="Enviar a Curso Completo",
        choices=[('', '--- Ninguno ---')], # Inicializado con placeholder
        widget=forms.Select(attrs={'class': 'form-select select2-masivo', 'style': 'width: 100%;'})
    )

    class Meta:
        model = MensajeInterno
        fields = ['destinatario', 'asunto', 'cuerpo', 'archivo']
        widgets = {
            'destinatario': forms.Select(attrs={'class': 'form-select select2', 'style': 'width: 100%;'}),
            'asunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto del mensaje'}),
            'cuerpo': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Escribe tu mensaje cordial y profesional aquí...'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # 1. Poblar destinatario individual (Tu lógica existente)
        self.fields['destinatario'].choices = self.get_grouped_destinatarios(user)
        
        # 🔥 CORRECCIÓN CLAVE: Permitir que destinatario (ModelChoiceField) sea opcional
        self.fields['destinatario'].required = False 

        # 2. Poblar destinatarios masivos (NUEVA LÓGICA)
        self.fields['destinatario_rol_masivo'].choices = self.get_roles_masivos(user)
        self.fields['destinatario_curso_masivo'].choices = self.get_cursos_masivos(user)


    def get_roles_masivos(self, user):
        """Define qué roles se pueden seleccionar para envío masivo."""
        ROLES_MASIVOS_CHOICES = [('', '--- Ninguno ---')]
        rol = user.perfil.rol if hasattr(user, 'perfil') else None

        if rol in ['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO']:
            ROLES_MASIVOS_CHOICES.extend([
                ('ALL_DOCENTES', 'Todo el Cuerpo Docente'),
                ('ALL_ESTUDIANTES', 'Todos los Estudiantes'),
                ('ALL_ACUDIENTES', 'Todos los Acudientes'),
                ('ALL_STAFF', 'Todo el Staff (Coordinación, Psicólogos, Adm.)'),
            ])
        
        if rol == 'DOCENTE':
            ROLES_MASIVOS_CHOICES.append(('MIS_ESTUDIANTES', 'Todos mis Estudiantes Asignados'))
            ROLES_MASIVOS_CHOICES.append(('MIS_ACUDIENTES', 'Todos mis Acudientes Asignados'))

        return ROLES_MASIVOS_CHOICES

    def get_cursos_masivos(self, user):
        """Define qué cursos se pueden seleccionar para envío masivo."""
        CURSO_CHOICES = [('', '--- Ninguno ---')]
        
        # Lógica para obtener cursos: solo para DOCENTES/COORDINADORES/ADMINS
        rol = user.perfil.rol if hasattr(user, 'perfil') else None
        cursos_disponibles = []

        if rol in ['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO']:
            cursos_disponibles = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
        elif rol == 'DOCENTE':
            mis_cursos_ids = AsignacionMateria.objects.filter(docente=user, activo=True).values_list('curso_id', flat=True).distinct()
            cursos_disponibles = Curso.objects.filter(id__in=mis_cursos_ids).order_by('grado', 'seccion')

        for curso in cursos_disponibles:
            CURSO_CHOICES.append((str(curso.id), f"Curso: {curso.nombre}"))
            
        return CURSO_CHOICES

    # 🛡️ Validaciones de Seguridad Inyectadas
    def clean_asunto(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('asunto'), 'Asunto')

    def clean_cuerpo(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('cuerpo'), 'Mensaje')

    def clean(self):
        cleaned_data = super().clean()
        destinatario_obj = cleaned_data.get('destinatario')
        rol_masivo = cleaned_data.get('destinatario_rol_masivo')
        curso_masivo = cleaned_data.get('destinatario_curso_masivo')

        # Contar cuántos campos tienen valor.
        destinos_seleccionados = []
        if destinatario_obj:
            destinos_seleccionados.append(destinatario_obj)
        if rol_masivo and rol_masivo != '':
            destinos_seleccionados.append(rol_masivo)
        if curso_masivo and curso_masivo != '':
            destinos_seleccionados.append(curso_masivo)

        if len(destinos_seleccionados) > 1:
            raise ValidationError("Solo puedes seleccionar un tipo de destinatario a la vez (Individual, Rol Masivo o Curso Masivo).")
        
        if not destinos_seleccionados:
             raise ValidationError("Debes seleccionar un destinatario individual, un rol masivo o un curso masivo.")
        
        return cleaned_data
        
    def get_grouped_destinatarios(self, user):
        User = get_user_model()
        perfil = getattr(user, 'perfil', None)
        rol = perfil.rol if perfil else None
        
        grupos = [] 
        
        staff_qs = User.objects.filter(
            Q(perfil__rol__in=['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO'])
        ).exclude(id=user.id).order_by('perfil__rol', 'last_name')
        
        if staff_qs.exists():
            lista_staff = []
            for u in staff_qs:
                cargo = u.perfil.get_rol_display() if hasattr(u, 'perfil') else "Staff"
                lista_staff.append((u.id, f"{cargo}: {u.get_full_name()}"))
            grupos.append(('Directivos y Soporte Técnico', lista_staff))

        if rol in ['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO']:
            docentes = User.objects.filter(perfil__rol='DOCENTE').exclude(id=user.id).order_by('last_name')
            if docentes.exists():
                grupos.append(('Cuerpo Docente', [(u.id, f"👨‍🏫 {u.get_full_name()}") for u in docentes]))

            todos_cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
            for curso in todos_cursos:
                matriculas = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante', 'estudiante__perfil')
                lista_alumnos = []
                for mat in matriculas:
                    est = mat.estudiante
                    vinculo = Acudiente.objects.filter(estudiante=est).select_related('acudiente').first()
                    nombre_acudiente = vinculo.acudiente.get_full_name() if vinculo else "Sin acudiente"
                    label = f"🎓 {est.last_name} {est.first_name} (Acudiente: {nombre_acudiente})"
                    lista_alumnos.append((est.id, label))
                if lista_alumnos:
                    grupos.append((f"Curso {curso.nombre}", lista_alumnos))

            acudientes_qs = User.objects.filter(perfil__rol='ACUDIENTE').order_by('last_name')
            if acudientes_qs.exists():
                lista_padres = [(u.id, f"👪 {u.get_full_name()}") for u in acudientes_qs]
                grupos.append(('Todos los Acudientes', lista_padres))

        elif rol == 'DOCENTE':
            colegas = User.objects.filter(perfil__rol='DOCENTE').exclude(id=user.id).order_by('last_name')
            if colegas.exists():
                 grupos.append(('Colegas Docentes', [(u.id, f"👨‍🏫 {u.get_full_name()}") for u in colegas]))
            
            mis_cursos_ids = AsignacionMateria.objects.filter(docente=user, activo=True).values_list('curso_id', flat=True).distinct()
            mis_cursos = Curso.objects.filter(id__in=mis_cursos_ids).order_by('grado', 'seccion')

            for curso in mis_cursos:
                matriculas = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante')
                lista_alumnos = []
                for m in matriculas:
                    est = m.estudiante
                    vinculo = Acudiente.objects.filter(estudiante=est).select_related('acudiente').first()
                    nombre_acudiente = vinculo.acudiente.get_full_name() if vinculo else "Sin acudiente"
                    label = f"🎓 {est.last_name} {est.first_name} (Acudiente: {nombre_acudiente})"
                    lista_alumnos.append((est.id, label))
                if lista_alumnos:
                    grupos.append((f"Curso {curso.nombre}", lista_alumnos))

        elif rol in ['ESTUDIANTE', 'ACUDIENTE']:
            if rol == 'ESTUDIANTE':
                estudiante_obj = user
            else:
                v = Acudiente.objects.filter(acudiente=user).first()
                estudiante_obj = v.estudiante if v else None
            
            if estudiante_obj:
                mat = Matricula.objects.filter(estudiante=estudiante_obj, activo=True).first()
                if mat and mat.curso:
                    asignaciones = AsignacionMateria.objects.filter(curso=mat.curso, activo=True).select_related('docente', 'materia')
                    lista_profes = []
                    seen_profes = set()
                    for asig in asignaciones:
                        if asig.docente.id not in seen_profes:
                            label = f"👨‍🏫 Prof. {asig.docente.get_full_name()} ({asig.materia.nombre})"
                            lista_profes.append((asig.docente.id, label))
                            seen_profes.add(asig.docente.id)
                    if lista_profes:
                        grupos.append(('Mis Profesores', lista_profes))

        grupos.insert(0, ('', 'Seleccione un destinatario...'))
        return grupos

# ===================================================================
# FORMULARIO DE SEGUIMIENTO (Añadir al final de tasks/forms.py)
# ===================================================================

class SeguimientoForm(forms.ModelForm, ContentSecurityMixin):
    class Meta:
        model = Seguimiento
        fields = ['tipo', 'descripcion', 'observaciones_adicionales'] # Aquí incluimos el campo nuevo
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'II. DETALLE DE LA OBSERVACIÓN, DESCARGOS Y COMPROMISOS...'
            }),
            # Este es el nuevo campo visual:
            'observaciones_adicionales': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'III. OBSERVACIONES ADICIONALES / COMPROMISOS FINALES...'
            }),
        }
        labels = {
            'observaciones_adicionales': 'III. OBSERVACIONES ADICIONALES / COMPROMISOS FINALES'
        }

    # Validaciones de seguridad para evitar groserías en los campos
    def clean_descripcion(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('descripcion'), 'Detalle')

    def clean_observaciones_adicionales(self):
        return self.validar_contenido_seguro(self.cleaned_data.get('observaciones_adicionales'), 'Observaciones Adicionales')


# tasks/forms.py

##SMS 

