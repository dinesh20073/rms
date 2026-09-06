import secrets
from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    domain = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to='tenants/logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class UserTenantRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_roles')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=50, default='ADMIN', choices=[
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member'),
        ('REVIEWER', 'Reviewer'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'tenant')

    def __str__(self):
        return f"{self.user.username} ({self.role}) - {self.tenant.name}"

class ApiKey(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, default='Default Key')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"ems_live_{secrets.token_hex(24)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
