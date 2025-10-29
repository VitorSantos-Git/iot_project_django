# iot_project/devices/admin.py
from django.contrib import admin
from .models import Device, TelemetryData, ScheduledTask, DAY_OF_WEEK_CHOICES
from django.db import models
from django.forms import ModelForm, MultipleChoiceField, CheckboxSelectMultiple
from django.utils import timezone 
from datetime import timedelta
import csv
from django.http import HttpResponse
#from django.forms import ModelMultipleChoiceField # Import necessário para o campo personalizado 


# ==============================================================================
# 1. ADMIN DE DISPOSITIVOS
# ==============================================================================
class DeviceAdmin(admin.ModelAdmin):
    # Usando métodos customizados para tradução das colunas
    list_display = (
        'display_device_id', 'display_name', 'display_device_type', 
        'display_location', 'display_ip_address', 'display_is_active', 
        'display_last_seen'
    )
    search_fields = ('device_id', 'name', 'location')
    list_filter = ('is_active', 'device_type')
    readonly_fields = ('last_seen', 'ip_address')
    
    # Métodos de tradução para DeviceAdmin
    def display_device_id(self, obj): return obj.device_id
    display_device_id.short_description = 'ID do Dispositivo'
    display_device_id.admin_order_field = 'device_id'

    def display_name(self, obj): return obj.name
    display_name.short_description = 'Nome'
    display_name.admin_order_field = 'name'

    def display_device_type(self, obj): return obj.device_type
    display_device_type.short_description = 'Tipo de Dispositivo'
    display_device_type.admin_order_field = 'device_type'
    
    def display_location(self, obj): return obj.location
    display_location.short_description = 'Localização'
    display_location.admin_order_field = 'location'
    
    def display_ip_address(self, obj): return obj.ip_address
    display_ip_address.short_description = 'Endereço IP'
    display_ip_address.admin_order_field = 'ip_address'

    def display_is_active(self, obj): return obj.is_active
    display_is_active.short_description = 'Ativo'
    display_is_active.admin_order_field = 'is_active'
    display_is_active.boolean = True # Para mostrar o ícone de check/X

    def display_last_seen(self, obj): return obj.last_seen
    display_last_seen.short_description = 'Última conexão'
    display_last_seen.admin_order_field = 'last_seen'

    # Sobrescreve a view de lista (admin/devices/device/) para forçar o Heartbeat/Timeout
    def changelist_view(self, request, extra_context=None):
        
        now = timezone.now() 
        timeout_minutes = 5
        timeout_threshold = now - timedelta(minutes=timeout_minutes)
        
        devices = Device.objects.all()
        
        # Lógica de Heartbeat (Inativação por Timeout)
        for device in devices:
            if device.last_seen and device.last_seen < timeout_threshold and device.is_active:
                device.is_active = False
                device.save(update_fields=['is_active']) 
                print(f"Dispositivo {device.device_id} inativado por timeout ({timeout_minutes} minutos).")
        
        # Chama a view de lista original do Admin
        return super().changelist_view(request, extra_context=extra_context)
    
    # Campo para entrada de comandos no formato JSON
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('device_id', 'name', 'device_type', 'location', 'is_active')
        }),
        ('Comunicação e Status', {
            'fields': ('pending_command', 'last_command', 'ip_address', 'last_seen')
        }),
    )

    class Media:
        js = (
            'admin/js/auto_refresh.js', # Caminho para o script de auto refresh
        )

# ==============================================================================
# 2. ADMIN DE DADOS DE TELEMETRIA
# ==============================================================================
@admin.register(TelemetryData) # <--- Usando o decorator para registrar
class TelemetryDataAdmin(admin.ModelAdmin):
    # --- AÇÃO DE EXPORTAÇÃO CSV ---
    actions = ['export_to_csv'] # Adiciona a ação ao menu dropdown

    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="telemetry_export.csv"'

        writer = csv.writer(response)
        
        header = [
            'ID', 'Device ID', 'Nome do Dispositivo', 'Timestamp', 
            'Temperatura (°C)', 'Umidade (%)', 'Relé D1', 'Ação Botão', 'Dados Brutos'
        ]
        writer.writerow(header)

        for obj in queryset:
            # Usa timezone.localtime() para formatar com o fuso horário correto do projeto
            timestamp_str = timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            row = [
                obj.pk,
                obj.device.device_id if obj.device else 'N/A',
                obj.device.name if obj.device else 'N/A',
                timestamp_str, 
                obj.temperature_celsius if obj.temperature_celsius is not None else '',
                obj.humidity_percent if obj.humidity_percent is not None else '',
                obj.relay_state_D1,
                obj.last_button_action if obj.last_button_action else '',
                str(obj.raw_data) if obj.raw_data else ''
            ]
            writer.writerow(row)

        return response

    export_to_csv.short_description = "Exportar selecionados para CSV"
    # --- FIM DA AÇÃO DE EXPORTAÇÃO ---
    
    # Usando métodos customizados para tradução das colunas
    list_display = (
        'display_device', 'display_temperature_celsius', 'display_humidity_percent', 
        'display_relay_state_D1', 'raw_data', 'display_timestamp',
    )
    list_filter = ('device__name', 'timestamp') # Filtra por nome do dispositivo e data
    search_fields = ('device__device_id', 'device__name')
    readonly_fields = ('timestamp', 'raw_data')

    class Media:
        js = (
            'admin/js/auto_refresh.js', # Caminho para o script de auto refresh
        )

    # Métodos de tradução para TelemetryDataAdmin
    def display_device(self, obj): return obj.device
    display_device.short_description = 'Dispositivo'
    display_device.admin_order_field = 'device'

    def display_temperature_celsius(self, obj): return obj.temperature_celsius
    display_temperature_celsius.short_description = 'Temperatura (°C)'
    display_temperature_celsius.admin_order_field = 'temperature_celsius'

    def display_humidity_percent(self, obj): return obj.humidity_percent
    display_humidity_percent.short_description = 'Umidade (%)'
    display_humidity_percent.admin_order_field = 'humidity_percent'
    
    def display_relay_state_D1(self, obj): return obj.relay_state_D1
    display_relay_state_D1.short_description = 'Estado do Relé'
    display_relay_state_D1.admin_order_field = 'relay_state_D1'
    display_relay_state_D1.boolean = True # Para mostrar o ícone de check/X

    def display_timestamp(self, obj): return obj.timestamp
    display_timestamp.short_description = 'Data/Hora'
    display_timestamp.admin_order_field = 'timestamp'

# ==============================================================================
# 3. REGISTRO DOS MODELOS
# ==============================================================================
admin.site.register(Device, DeviceAdmin)


# ==============================================================================
# 4. ADMIN DE TAREFAS AGENDADAS 
#   (Ajustes na Criação/Visualização)
# ==============================================================================
class ScheduledTaskForm(ModelForm):
    # Sobrescrevemos o campo recurrent_days
    recurrent_days = MultipleChoiceField(
        choices=DAY_OF_WEEK_CHOICES,
        required=False,
        widget=CheckboxSelectMultiple,
        label="Dias da Semana",
        help_text="Selecione os dias da semana para execução (se for recorrente)"
    )

    """ # CUSTOMIZAÇÃO PARA O CAMPO DEVICES 
    devices = ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=True,
        widget=CheckboxSelectMultiple,
        label="Dispositivos Associados",
        help_text="Selecione os dispositivos que esta tarefa deve afetar"
    ) """
    
    class Meta:
        model = ScheduledTask
        fields = '__all__'
    
    # Converte a lista de dias (ex: ['1', '3', '5']) para a string '1,3,5' antes de salvar
    def clean_recurrent_days(self):
        return ",".join(self.cleaned_data['recurrent_days']) if self.cleaned_data['recurrent_days'] else ''

    # Converte a string '1,3,5' para a lista ['1', '3', '5'] ao carregar
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.recurrent_days:
            self.initial['recurrent_days'] = self.instance.recurrent_days.split(',')

@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    form = ScheduledTaskForm
    
    # Todas as colunas traduzidas
    list_display = (
        'display_name',
        'display_status',
        'display_last_run_at',
        'display_execution_time',
        'display_is_recurrent',
        'display_recurrent_time',
        'display_recurrent_days',
        'display_created_at'
    )
    
    list_filter = ('status', 'is_recurrent', 'created_at')
    search_fields = ('name', 'devices__device_id')
    #raw_id_fields = ('devices',)
    readonly_fields = ('last_run_at',)
    filter_horizontal = ('devices',) 

    class Media:
        js = (
            'admin/js/auto_refresh.js', # Caminho para o script de auto refresh
        )

    # Métodos para tradução das colunas 
    def display_name(self, obj): return obj.name
    display_name.short_description = 'Nome'
    display_name.admin_order_field = 'name'

    def display_status(self, obj): return obj.get_status_display()
    display_status.short_description = 'Status'
    display_status.admin_order_field = 'status'
    
    def display_last_run_at(self, obj): return obj.last_run_at
    display_last_run_at.short_description = 'Última Execução'
    display_last_run_at.admin_order_field = 'last_run_at'

    def display_execution_time(self, obj): return obj.execution_time
    display_execution_time.short_description = 'Data/Hora (Agendamento Único)'
    display_execution_time.admin_order_field = 'execution_time'

    def display_is_recurrent(self, obj): return obj.is_recurrent
    display_is_recurrent.short_description = 'Recorrente'
    display_is_recurrent.admin_order_field = 'is_recurrent'
    display_is_recurrent.boolean = True 
    
    def display_created_at(self, obj): return obj.created_at
    display_created_at.short_description = 'Criado em'
    display_created_at.admin_order_field = 'created_at'
    
    # Métodos customizados para recorrência
    def display_recurrent_time(self, obj):
        return obj.recurrent_time.strftime('%H:%M') if obj.recurrent_time else '-'
    display_recurrent_time.short_description = 'Horário Recorrente'
    display_recurrent_time.admin_order_field = 'recurrent_time'

    def display_recurrent_days(self, obj):
        if not obj.recurrent_days:
            return '-'
        days_map = dict(DAY_OF_WEEK_CHOICES)
        day_codes = obj.recurrent_days.split(',')
        day_names = [days_map.get(code, '?')[:3] for code in day_codes]
        return ", ".join(day_names)
        
    display_recurrent_days.short_description = 'Dias Recorrentes'
    display_recurrent_days.admin_order_field = 'recurrent_days'
    
    fieldsets = (
        ('Informação Básica', {
            'fields': ('name', 'devices', 'command_json', 'status')
        }),
        ('Agendamento Único', {
            'fields': ('execution_time',)
        }),
        ('Agendamento Recorrente', {
            'fields': ('is_recurrent', 'recurrent_time', 'recurrent_days') 
        }),
        ('Histórico', {
            'fields': ('last_run_at',)
        }),
    )


