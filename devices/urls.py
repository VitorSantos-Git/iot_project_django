# iot_project/devices/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Rota principal para o dashboard web de dispositivos
    path('dashboard/', views.device_dashboard, name='device_dashboard'),
]