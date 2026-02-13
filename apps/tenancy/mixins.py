from django.db import models
from .utils import get_current_tenant

class TenantManager(models.Manager):
    """
    Manager personalizado para filtrar automáticamente los registros
    según el colegio (tenant) activo en la sesión.
    """
    def get_queryset(self):
        tenant = get_current_tenant()
        queryset = super().get_queryset()
        if tenant:
            # FILTRADO AUTOMÁTICO: Seguridad de datos a nivel de base de datos
            return queryset.filter(tenant=tenant)
        return queryset

class TenantAwareModel(models.Model):
    """
    Clase base abstracta para todos los modelos que pertenecen a un colegio.
    Incluye la relación con el Tenant y la lógica de guardado automático.
    """
    tenant = models.ForeignKey(
        'tenancy.Tenant', 
        on_delete=models.CASCADE,
        related_name='%(class)s_records',
        verbose_name="Institución",
        # Permitir nulos temporalmente para facilitar la migración de datos legacy
        null=True,   
        blank=True   
    )
    
    # Managers
    objects = TenantManager()         # Manager por defecto con filtrado por tenant
    all_objects = models.Manager()    # Manager sin filtro (útil para administradores globales)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para asegurar que cada registro 
        tenga asignado el tenant actual si no se ha definido uno.
        """
        if not self.tenant_id:
            tenant_actual = get_current_tenant()
            if tenant_actual:
                self.tenant = tenant_actual
        super().save(*args, **kwargs)