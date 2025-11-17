from django.db import models

# Create your models here.
from django.db import models
import json


class VINProcessing(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'ממתין'),
        ('PROCESSING', 'מעבד'),
        ('COMPLETED', 'הושלם'),
        ('FAILED', 'נכשל'),
    ]

    vin = models.CharField(max_length=17, unique=True, verbose_name='מספר VIN')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    progress = models.IntegerField(default=0)  # 0-100
    current_step = models.CharField(max_length=100, blank=True)
    result_json = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'עיבוד VIN'
        verbose_name_plural = 'עיבודי VIN'
        ordering = ['-created_at']

    def get_result_dict(self):
        if self.result_json:
            return json.loads(self.result_json)
        return None
