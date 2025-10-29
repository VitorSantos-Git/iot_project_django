# iot_project/devices/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

DAY_OF_WEEK_CHOICES = (
    ('1', 'Segunda-feira'),
    ('2', 'Terça-feira'),
    ('3', 'Quarta-feira'),
    ('4', 'Quinta-feira'),
    ('5', 'Sexta-feira'),
    ('6', 'Sábado'),
    ('7', 'Domingo'),
)

# ==============================================================================
# 1. MODELO DEVICE (REGISTRO DO ESP8266)
# ==============================================================================
class Device(models.Model):
    """
    Representa um dispositivo IoT (ESP8266).
    É o registro principal para autenticação e comandos.
    """
    # Dados de Identificação
    device_id = models.CharField(
        'ID do Dispositivo', 
        max_length=50, 
        unique=True, 
        db_index=True,
        help_text="ID único enviado pelo ESP8266 (ex: A113)"
    )
    name = models.CharField(
        'Nome', 
        max_length=100, 
        default="Dispositivo IoT",
        help_text="Nome amigável para exibição na interface"
    )
    device_type = models.CharField(
        'Tipo de Dispositivo', 
        max_length=100, 
        default="Genérico",
        help_text="Tipo de dispositivo (ex: Rele Iluminação, Controle Ar, Sensor Temperatura)"
    )
    location = models.CharField(
        'Localização', 
        max_length=100, 
        default="Desconhecido",
        help_text="Localização física do dispositivo"
    )
    
    # Dados de Status e Conexão
    ip_address = models.GenericIPAddressField(
        'Endereço IP', 
        null=True, 
        blank=True,
        help_text="Último endereço IP conhecido do dispositivo"
    )
    is_active = models.BooleanField(
        'Ativo', 
        default=True,
        help_text="Indica se o dispositivo está ativo"
    )
    
    # Dados de Comunicação (Comandos)
    # Comando JSON pendente para ser lido pelo ESP8266
    pending_command = models.JSONField(
        'Comando Pendente', 
        null=True, 
        blank=True,
        help_text="Comando pendente no formato JSON para execução (ex: {'action': 'ligar_rele', 'target': 'rele_D1', 'value': 1})"
    )
    # Último comando executado/lido
    last_command = models.CharField(
        'Último Comando', 
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Confirmação do último comando executado pelo dispositivo"
    )
    
    # Timestamps
    last_seen = models.DateTimeField(
        'Última Conexão', 
        default=timezone.now,
        help_text="Registro do último check-in (POST) do dispositivo"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # --- ATRIBUTOS DE AUTENTICAÇÃO NECESSÁRIOS PARA DJANGO/DRF ---
    @property
    def is_authenticated(self):
        """Sinaliza ao DRF que este 'usuário' está autenticado."""
        return True

    @property
    def is_anonymous(self):
        """Sinaliza ao DRF que este 'usuário' não é anônimo."""
        return False
    # -----------------------------------------------------------

    def __str__(self):
        return f"[{self.device_id}] {self.name} ({self.location})"
    
    class Meta:
        verbose_name = "Dispositivo"
        verbose_name_plural = "Dispositivos"
        ordering = ['name']

# ==============================================================================
# 2. MODELO TELEMETRYDATA (DADOS DE SENSORES)
# ==============================================================================
class TelemetryData(models.Model):
    """
    Armazena os dados de telemetria (sensores e estado) enviados por um Device.
    """
    device = models.ForeignKey(
        Device, 
        verbose_name='Dispositivo',
        on_delete=models.SET_NULL,
        related_name='telemetry_records',
        null=True,
        blank=True,
        help_text="Dispositivo que enviou este registro"
    )
    
    # Telemetria Principal
    temperature_celsius = models.FloatField(
        'Temperatura (Celsius)', 
        null=True, 
        blank=True,
        help_text="Temperatura em Celsius"
    )
    humidity_percent = models.FloatField(
        'Umidade (Porcentagem)', 
        null=True, 
        blank=True,
        help_text="Umidade do ar em porcentagem"
    )
    relay_state_D1 = models.BooleanField(
        'Estado do Relé', 
        default=False,
        help_text="Estado do relé (True/False)"
    )
    last_button_action = models.CharField(
        'Última Ação do Botão', 
        max_length=50, 
        null=True, 
        blank=True,
        help_text="Ação local acionada por botão (se houver)"
    )

    # Dados brutos adicionais
    raw_data = models.JSONField(
        'Dados Brutos', 
        null=True, 
        blank=True,
        help_text="Dados JSON brutos enviados pelo dispositivo"
    )

    # Timestamps
    timestamp = models.DateTimeField(
        'Data/Hora do Registro', 
        default=timezone.now,
        db_index=True,
        help_text="Timestamp do registro (quando foi recebido)"
    )
    
    def __str__(self):
        device_name = self.device.name if self.device and self.device.name else "DISPOSITIVO DESCONHECIDO"
        return f"{device_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Dado de Telemetria"
        verbose_name_plural = "Dados de Telemetria"
        ordering = ['-timestamp'] # Ordena do mais recente para o mais antigo

# ==============================================================================
# 3. MODELO SCHEDULEDTASK (COMANDOS AGENDADOS)
# ==============================================================================
class ScheduledTask(models.Model):
    """
    Armazena comandos que serão executados em um Device ou em múltiplos Devices
    em uma data/hora específica ou de forma recorrente.
    """
    TASK_STATUS = [
        ('PENDING', 'Pendente'),
        ('EXECUTED', 'Executado'),
        ('FAILED', 'Falhou'),
        ('CANCELLED', 'Cancelado'),
    ]

    name = models.CharField('Nome da Tarefa', max_length=255, help_text="Nome descritivo da tarefa (ex: Ligar às 7h)")
    
    # Campo para selecionar o(s) dispositivo(s)
    # Usamos ManyToManyField para permitir que uma tarefa afete vários dispositivos
    devices = models.ManyToManyField(
        Device, 
        verbose_name='Dispositivos', 
        related_name='scheduled_tasks',
        help_text="Dispositivos que receberão este comando"
    )

    # Comando a ser enviado (JSON, exemplo: {"action": "ligar_rele", "target": "rele_D1", "value": 1})
    command_json = models.JSONField('Comando JSON', help_text='Comando a ser enviado (JSON). Exemplo: {"value": 0, "action": "ligar_rele", "target": "rele_D1"}') 

    # Agendamento
    execution_time = models.DateTimeField(
        'Data e Hora de Execução', 
        null=True, blank=True,
        help_text="Data e hora para execução (se não for recorrente)"
    )

    # Campo para o horário recorrente (hora e minuto)
    # Para guardar o horário da tarefa recorrente
    recurrent_time = models.TimeField(
        'Horário Recorrente', 
        null=True, blank=True,
        help_text="Hora (HH:MM) para execução diária ou semanal (se for recorrente)"
    )
    
    #Campo para escolher os dias da semana (ex: 1=Seg, 7=Dom)
    recurrent_days = models.CharField(
        'Dias da Semana (Recorrência)', 
        max_length=15, 
        null=True, blank=True,
        help_text="Dias da semana para recorrência (ex: 1,3,5 para Seg, Qua, Sex)"
    )

    is_recurrent = models.BooleanField(
        'Recorrente', 
        default=False, 
        help_text="Se selecionado, será reexecutado nos dias e horários definidos"
    )
    
    # Campo para Histórico
    last_run_at = models.DateTimeField(
        'Última Execução', 
        null=True, blank=True,
        help_text="Hora da última execução bem-sucedida desta tarefa."
    )

    status = models.CharField(
        max_length=50, 
        choices=TASK_STATUS, 
        default='PENDING',
        help_text="Para ser executada, a tarefa deve estar em 'Pendente'. Tarefas recorrentes permanecerão 'Pendente' durante o ciclo de recorrência."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.status})"

    class Meta:
        verbose_name = "Tarefa Agendada"
        verbose_name_plural = "Tarefas Agendadas"