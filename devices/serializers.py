# iot_project/devices/serializers.py

from rest_framework import serializers
from .models import Device, TelemetryData
from django.utils import timezone
import json 

# Serializer para o modelo Device
class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        # Incluímos todos os campos principais que o ESP8266/Celery irá interagir
        fields = [
            'device_id', 'name', 'device_type', 'location', 'ip_address', 
            'is_active', 'pending_command', 'last_command', 'last_seen'
        ]
        read_only_fields = ['last_seen'] # last_seen será preenchido pelo Django/API

        extra_kwargs = {
            # Torna o 'pending_command' opcional para o PATCH do Celery
            'pending_command': {'required': False}, 
            # Garante que os outros campos sejam opcionais para o PATCH
            'name': {'required': False},
            'device_type': {'required': False},
            'location': {'required': False},
            'ip_address': {'required': False},
            'is_active': {'required': False},
            'last_command': {'required': False},
        }

# Serializer para o modelo TelemetryData
class TelemetryDataSerializer(serializers.ModelSerializer):
    # Campos do Device para serem enviados junto com a Telemetria (POST)
    name = serializers.CharField(write_only=True, required=False)
    device_type = serializers.CharField(write_only=True, required=False)
    location = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = TelemetryData
        # Estes campos serão enviados pelo ESP8266 no POST
        fields = [
            'device', 
            'temperature_celsius', 'humidity_percent', 
            'relay_state_D1', 'last_button_action',
            'name', 'device_type', 'location' # Campos do Device para o POST
        ]
        read_only_fields = ['device']
    
    # Sobrescreve o método 'create' para atualizar o Device ao mesmo tempo que cria a Telemetria
    def create(self, validated_data):
        device_instance = self.context['request'].user
        
        device_name = validated_data.pop('name', None)
        device_type = validated_data.pop('device_type', None)
        device_location = validated_data.pop('location', None)
        
        telemetry_record = TelemetryData.objects.create(device=device_instance, **validated_data)
        
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

        # Atualiza o last_seen do dispositivo e o IP
        device_instance.last_seen = timezone.now()
        device_instance.ip_address = self.context['request'].META.get('REMOTE_ADDR') 
 
        device_instance.save(update_fields=update_fields)

        return telemetry_record
    
