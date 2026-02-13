from contextvars import ContextVar

# Variable global segura para hilos y async (Soporte Industrial)
_current_tenant = ContextVar('current_tenant', default=None)

def get_current_tenant():
    """Retorna el colegio activo en la petición actual."""
    return _current_tenant.get()

def set_current_tenant(tenant):
    """Define el colegio activo. Retorna un token para resetearlo después."""
    return _current_tenant.set(tenant)

def reset_current_tenant(token):
    """Limpia la memoria al finalizar el request."""
    _current_tenant.reset(token)

def tenant_upload_path(instance, filename):
    """
    Genera rutas de archivos aisladas: uploads/tenant_{id}/{modelo}/{filename}
    """
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 'public'
    model_name = instance._meta.model_name 
    return f'uploads/tenant_{tenant_id}/{model_name}/{filename}'
