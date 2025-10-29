# iot_project/core_system/__init__.py

# Isso garante que o app Celery sempre será importado quando o Django iniciar
from .celery import app as celery_app

__all__ = ('celery_app',)