from django.db import models

class Tenant(models.Model):
    """
    Representa a cada Colegio (Inquilino) en el sistema.
    """
    name = models.CharField(max_length=100, unique=True)
    subdomain = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Instituciones"

    def __str__(self):
        return self.name