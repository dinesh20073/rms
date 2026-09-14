from django.db import models
from django.utils.text import slugify
from apps.events.models import Event

class Form(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='registration_form')
    title = models.CharField(max_length=255, default='Registration Form')
    description = models.TextField(blank=True, default='Please fill in the required details to complete your registration.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Form for {self.event.title}"

    def create_default_fields(self):
        """Provision streamlined standard fields for event registration"""
        defaults = [
            {'label': 'Full Name', 'field_type': 'text', 'is_required': True, 'order': 1, 'placeholder': 'Enter your full name'},
            {'label': 'Email Address', 'field_type': 'email', 'is_required': True, 'order': 2, 'placeholder': 'Enter your email address'},
            {'label': 'Phone Number', 'field_type': 'phone', 'is_required': True, 'order': 3, 'placeholder': 'Enter your phone number'},
            {'label': 'Age', 'field_type': 'number', 'is_required': True, 'order': 4, 'placeholder': 'Enter your age'},
            {'label': 'Gender', 'field_type': 'dropdown', 'is_required': True, 'order': 5, 'options': ['Male', 'Female', 'Other']},
            {'label': 'Ticket Count', 'field_type': 'number', 'is_required': True, 'order': 6, 'placeholder': '1'},
        ]
        for item in defaults:
            field_key = slugify(item['label']).replace('-', '_')
            f_obj, created = FormField.objects.get_or_create(
                form=self,
                field_key=field_key,
                defaults={
                    'label': item['label'],
                    'field_type': item['field_type'],
                    'is_required': item['is_required'],
                    'order': item['order'],
                    'placeholder': item.get('placeholder', ''),
                    'help_text': item.get('help_text', ''),
                    'options': item.get('options', [])
                }
            )
            if not created:
                f_obj.label = item['label']
                f_obj.placeholder = item.get('placeholder', '')
                if item.get('help_text'):
                    f_obj.help_text = item.get('help_text', '')
                if item.get('options'):
                    f_obj.options = item.get('options', [])
                f_obj.save()

class FormField(models.Model):
    FIELD_TYPE_CHOICES = [
        ('text', 'Short Text'),
        ('email', 'Email Address'),
        ('phone', 'Phone Number'),
        ('number', 'Number'),
        ('textarea', 'Long Text / Paragraph'),
        ('dropdown', 'Dropdown Select'),
        ('radio', 'Radio Buttons'),
        ('checkbox', 'Checkbox Toggle'),
    ]

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    field_key = models.SlugField(max_length=100)
    field_type = models.CharField(max_length=50, choices=FIELD_TYPE_CHOICES, default='text')
    placeholder = models.CharField(max_length=255, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)
    options = models.JSONField(default=list, blank=True, help_text="List of choices for dropdown or radio")

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('form', 'field_key')

    def __str__(self):
        return f"{self.label} ({self.form.event.title})"

    def save(self, *args, **kwargs):
        if not self.field_key:
            self.field_key = slugify(self.label).replace('-', '_')
        super().save(*args, **kwargs)
