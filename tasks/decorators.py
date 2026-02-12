# tasks/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def role_required(rol_o_roles):
    """
    Decorador para restringir el acceso a vistas según el rol del usuario.
    Acepta un string con un rol o una lista de strings con varios roles permitidos.
    """
    if not isinstance(rol_o_roles, list):
        rol_o_roles = [rol_o_roles]

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            # 1. Verificar si el usuario tiene un perfil
            if not hasattr(request.user, 'perfil'):
                messages.error(request, 'No tienes un perfil de usuario configurado. Contacta al administrador.')
                return redirect('home')

            perfil = request.user.perfil
            
            # 2. Verificar si el rol del usuario está en la lista de roles permitidos
            # O si es un director de curso y se le da acceso como tal.
            if perfil.rol in rol_o_roles:
                return view_func(request, *args, **kwargs)
            
            # Caso especial: Un director de curso también puede acceder a vistas de 'DOCENTE'
            if 'DOCENTE' in rol_o_roles and perfil.es_director:
                return view_func(request, *args, **kwargs)
            
            # Caso especial: 'DIRECTOR_CURSO' es un permiso, no un rol. Se otorga si es_director es True.
            if 'DIRECTOR_CURSO' in rol_o_roles and perfil.es_director:
                return view_func(request, *args, **kwargs)

            # 3. Si no tiene permisos, mostrar error
            roles_legibles = ", ".join(rol.replace("_", " ").title() for rol in rol_o_roles)
            messages.error(request, f'No tienes los permisos necesarios ({roles_legibles}) para acceder a esta página.')
            return redirect('home')
        return wrapper_func
    return decorator
