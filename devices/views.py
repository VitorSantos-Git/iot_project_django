# iot_project/devices/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.shortcuts import render 
from datetime import timedelta

from .models import Device, TelemetryData
from .serializers import DeviceSerializer, TelemetryDataSerializer
from core_system.authentication import TokenAuthentication
from django.db.models import F
from decouple import config

# ==============================================================================
# 1. VIEWSET PARA GERENCIAR DISPOSITIVOS (Autenticado pelo Token do ESP)
#    (Usado para GET de comandos pendentes e PUT de confirmação)
# ==============================================================================
class DeviceViewSet(viewsets.ModelViewSet):
    """
    Endpoint para gerenciamento de Dispositivos (Device).
    Permite aos clientes (ESP8266) buscar comandos (GET) e 
    atualizar status/confirmar comandos (PUT/PATCH).
    """
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    # Usaremos uma autenticação customizada baseada em Token
    authentication_classes = [TokenAuthentication] 
    #permission_classes = [IsAuthenticated] # Exige autenticação
    permission_classes = [IsAuthenticated]

    lookup_field = 'device_id'

    def get_queryset(self):
        # Lógica de segurança: O dispositivo só pode ver o próprio registro,
        # A MENOS QUE seja o Celery Worker (Token Mestre) ou Admin.

        if self.request.user is None and self.request.auth is not None:
             # Se o self.request.user é None, mas a autenticação foi bem-sucedida,
             # significa que o Token Mestre foi usado.
             return Device.objects.all()

        # Dispositivo Individual: Só pode ver e modificar o próprio registro.
        if self.request.user and isinstance(self.request.user, Device):
            return Device.objects.filter(pk=self.request.user.pk)
        
        return Device.objects.none() # Nenhuma outra requisição deve ter acesso.

    # Sobrescrevemos o método retrieve (GET detalhado)
    def retrieve(self, request, *args, **kwargs):
        device = self.get_object()
        
        # 1. ATUALIZAÇÃO DO STATUS: OCORRE APENAS SE HOUVE COMUNICAÇÃO
        device.last_seen = timezone.now()
        device.ip_address = request.META.get('REMOTE_ADDR')
        
        # Reativa se estava inativo, pois acabou de se comunicar
        if not device.is_active:
             device.is_active = True
             print(f"Dispositivo {device.device_id} reativado com sucesso.")
            
        device.save()
        
        # 2. Prepara a resposta (o restante é o mesmo)
        response_data = {
            "device_id": device.device_id,
            "status": "no_command",
            "last_seen": device.last_seen,
            "ip_address": device.ip_address,
            "pending_command": device.pending_command
        }
        
        # 3. Verifica se há comando pendente
        if device.pending_command:
            response_data["status"] = "command_pending"
            response_data["command"] = device.pending_command
            
        return Response(response_data)
    
    def partial_update(self, request, *args, **kwargs):
        """
        Customiza o PATCH para garantir que a validação seja parcial (partial=True),
        o que permite que apenas o campo pending_command seja enviado pelo Celery.
        """
        instance = self.get_object()
        # O self.get_serializer precisa ser chamado com partial=True
        serializer = self.get_serializer(instance, data=request.data, partial=True) 
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # Recria o cache de objetos pré-buscados se necessário
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    # Sobrescrevemos o método update/partial_update (PUT/PATCH)
    # Usado pelo ESP8266 para confirmar que um comando foi executado.
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False) # Deve ser True para PATCH
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        # --- PONTO CRÍTICO DE DEBUG ---
        if not serializer.is_valid():
            # **Imprime o erro de validação detalhado no log do Docker Web**
            print(f"ERRO DE VALIDAÇÃO DO DRF: {serializer.errors}") 
            # Retorna o erro 400 com o JSON detalhado (se o DEBUG=True estiver funcionando)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # -----------------------------

        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # Se 'prefetch_related' foi usado, recarregue a instância
            instance = self.get_object()

        return Response(serializer.data)


# ==============================================================================
# 2. VIEWSET PARA RECEBER TELEMETRIA (Autenticado pelo Token do ESP)
#    (Usado para POST de dados de sensores)
# ==============================================================================
class TelemetryDataViewSet(viewsets.ModelViewSet):
    """
    Endpoint para envio de dados de Telemetria.
    Permite apenas requisições POST para o ESP8266 enviar dados.
    """
    queryset = TelemetryData.objects.all().order_by('-timestamp')
    serializer_class = TelemetryDataSerializer
    authentication_classes = [TokenAuthentication]
    #permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    # Restringe a viewset para permitir apenas POST (criação)
    http_method_names = ['post'] 
    
    # Sobrescrevemos create (POST)
    def create(self, request, *args, **kwargs):
        # Precisamos injetar o request no contexto do Serializer para obter o IP
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"message": "Dados de telemetria recebidos e processados com sucesso."}, 
            status=status.HTTP_201_CREATED, 
            headers=headers
        )
    

# Lógica para a Interface Web (Visualização)
def device_dashboard(request):
    """
    Exibe uma lista de dispositivos, seus dados mais recentes e status.
    Esta é a view principal para o dashboard web.
    """
    
    # 1. Pré-processamento e Sincronização de Status
    timeout_minutes = 5
    timeout_threshold = timezone.now() - timedelta(minutes=timeout_minutes)

    devices_list = []
    
    for device in Device.objects.all():
        
        # Replicando a lógica de inativação do Admin para o Dashboard
        if device.last_seen < timeout_threshold and device.is_active:
             device.is_active = False
             device.save(update_fields=['is_active']) 
        
        # Define as propriedades dinâmicas usadas no template e para ordenação local
        device.is_online = device.is_active
        device.latest_telemetry = TelemetryData.objects.filter(device=device).order_by('-timestamp').first()
        
        devices_list.append(device)

    # 2. ORDENAÇÃO FINAL (Em memória, pois as propriedades dinâmicas foram adicionadas)
    # Ordena: 
    #   a) Por is_online (False=0, True=1). O sinal de menos (-) inverte, colocando True (1) primeiro.
    #   b) Secundariamente, pelo nome.
    
    # Usamos uma função lambda com key para ordenar com base nas propriedades adicionadas ao objeto
    devices_list.sort(key=lambda d: (-d.is_online, d.name))
    
    
    context = {
        'devices': devices_list,
        'timeout_minutes': timeout_minutes,
    }

    return render(request, 'devices/dashboard.html', context)


