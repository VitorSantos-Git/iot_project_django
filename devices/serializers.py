# iot_project/devices/serializers.py
from rest_framework import serializers
from .models import Device, TelemetryData
from django.utils import timezone
import json

# Serializer para o modelo Device
class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        # Incluímos SOMENTE os campos que podem ser lidos OU atualizados pelo ESP/Celery
        fields = [
            'device_id',            # Chave de Lookup (Apenas leitura/identificação)
            'pending_command',      # Único campo que o Celery PATCH envia
            'last_command',         # O ESP PATCH envia isso de volta (confirmação)
            'is_active',            # O ESP PATCH envia isso de volta
            'last_seen',            # Apenas leitura
            'ip_address',           # Apenas leitura
            # Campos estáticos como 'name', 'device_type', 'location' não precisam estar aqui
        ]
        
        read_only_fields = [
            'device_id',            # Vem da URL, não do corpo
            'last_seen',            # Gerado pelo Django
            'ip_address',           # Gerado pelo Django
        ] 
        
        extra_kwargs = {
            # O PATCH só envia 'pending_command' (tasks.py), então o resto é opcional
            'pending_command': {'required': False},
            'last_command': {'required': False},
            'is_active': {'required': False},
        }

# Serializer para o modelo TelemetryData
class TelemetryDataSerializer(serializers.ModelSerializer):
    # Usamos o StringRelatedField para exibir o nome do dispositivo, mas 
    # o FK 'device' é o que precisamos para salvar
    # Adiciona campos do Device como write_only.
    # write_only=True garante que eles são aceitos na requisição POST,
    # mas não são esperados no modelo TelemetryData.
    name = serializers.CharField(write_only=True, required=False)
    device_type = serializers.CharField(write_only=True, required=False)
    location = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = TelemetryData
        # Estes campos serão enviados pelo ESP8266 no POST
        fields = [
            #'device_id', # Campo auxiliar para facilitar a criação via API
            'name', 
            'device_type', 
            'location',
            'temperature_celsius', 
            'humidity_percent', 
            'relay_state_D1', 
            'last_button_action',
            'raw_data' # Para dados extras
        ]
        # Note que 'device' (FK) não está aqui, pois será obtido dinamicamente pelo Device ID

    # Sobrescrevemos create para associar o TelemetryData ao Device correto e atualizar o Device
    def create(self, validated_data):
        # Tentativa de buscar o Device pelo device_id que virá no payload
        #device_id = validated_data.pop('device_id', None) 
        device_instance = self.context['request'].user

        #Extrai os campos de Device de validated_data (eles devem ser removidos antes de criar TelemetryData)
        device_name = validated_data.pop('name', None)
        device_type = validated_data.pop('device_type', None)
        device_location = validated_data.pop('location', None)
        
        # Cria o registro de telemetria associado ao dispositivo encontrado
        telemetry_record = TelemetryData.objects.create(device=device_instance, **validated_data)
        
        #Atualiza os campos do Device
        update_fields = ['last_seen', 'ip_address']
        
        # Verifica e atualiza apenas se o valor for enviado e for diferente do valor atual
        if device_name is not None and device_instance.name != device_name:
            device_instance.name = device_name
            update_fields.append('name')
            
        if device_type is not None and device_instance.device_type != device_type:
            device_instance.device_type = device_type
            update_fields.append('device_type')
            
        if device_location is not None and device_instance.location != device_location:
            device_instance.location = device_location
            update_fields.append('location')

        # Atualiza o last_seen do dispositivo
        device_instance.last_seen = timezone.now()
        device_instance.ip_address = self.context['request'].META.get('REMOTE_ADDR') # Captura o IP da requisição
        
        # Salva o dispositivo, atualizando apenas os campos alterados
        device_instance.save(update_fields=update_fields)

        return telemetry_record