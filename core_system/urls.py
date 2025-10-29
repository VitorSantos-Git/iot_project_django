# iot_project/core_system/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.generic.base import RedirectView

from devices.views import DeviceViewSet, TelemetryDataViewSet, device_dashboard

# O DefaultRouter do DRF registra automaticamente os ViewSets
router = DefaultRouter()
# 1. Rota para gerenciar dispositivos (GET/PUT/PATCH/DELETE)
# URL: /api/devices/ -> POST para Telemetria
# URL: /api/devices/ESP8266_002/ -> GET para Comandos / PUT para Confirmação
router.register(r'devices', DeviceViewSet, basename='device')

# A rota 'telemetry' será aninhada dentro de 'devices' ou, para simplicidade do ESP, 
# usaremos a rota principal de 'devices' para o POST. 
# Para manter a clareza, vamos usar o POST para TelemetryDataViewSet
# Se usássemos uma rota separada, seria: router.register(r'telemetry', TelemetryDataViewSet, basename='telemetry')


urlpatterns = [
    # 1. ROTA RAIZ ('/') REDIRECIONA PARA O ADMIN (LOGIN)
    # RedirectView.as_view(url='/admin/', permanent=True) fará o redirecionamento.
    # Esta rota no topo para que seja a primeira a ser verificada.
    path('', RedirectView.as_view(url='/admin/', permanent=False), name='index_redirect'),


    # Rotas da Interface Web (Admin e Futuras Páginas)
    path('admin/', admin.site.urls),
    
    # Rotas da API REST (Dispositivos/Telemetria)
    # Rota principal da API REST (inclui o /devices/ e /devices/{id}/)
    path('api/', include(router.urls)),

    # Rotas do App Devices (inclui /devices/dashboard/)
    path('devices/', include('devices.urls')),
    
    # Adicionamos uma rota específica para o POST de telemetria
    # Usaremos o TelemetryDataViewSet apenas para o POST (criação de registro)
    path('api/telemetry/', TelemetryDataViewSet.as_view({'post': 'create'}), name='telemetry-post'),
    
    # Rota opcional do DRF para login via browser (útil para debug)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]

# Nota de Ajuda ao ESP: 
# O ESP fará:
# 1. POST (Telemetria): http://[IP_DO_SERVIDOR]:8000/api/telemetry/
# 2. GET (Comandos): http://[IP_DO_SERVIDOR]:8000/api/devices/ESP8266_002/
# 3. PUT (Confirmação): http://[IP_DO_SERVIDOR]:8000/api/devices/ESP8266_002/