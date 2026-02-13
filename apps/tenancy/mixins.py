from django.db import models
from .utils import get_current_tenant

class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        queryset = super().get_queryset()
        if tenant:
            # FILTRADO AUTOMÁTICO: Seguridad de datos a nivel de base de datos
            return queryset.filter(tenant=tenant)
        return queryset

class TenantAwareModel(models.Model):
    """Clase base para todos los modelos que pertenecen a un colegio."""
    tenant = models.ForeignKey(
        'tenancy.Tenant', 
        on_delete=models.CASCADE,
        related_name='%(class)s_records',
        verbose_name="Institución"
    )
    
    objects = TenantManager() # Manager con filtro de seguridad
    all_objects = models.Manager() # Manager sin filtro (SuperAdmin)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            self.tenant = get_current_tenant()
        super().save(*args, **kwargs)
