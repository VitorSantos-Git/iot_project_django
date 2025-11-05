# iot_project/devices/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Device, ScheduledTask
import requests
import json
from decouple import config
import logging

# Configuração de logger para melhor rastreamento no Celery Worker
logger = logging.getLogger(__name__)

# Base API URL para comunicação com o servidor Django
# DEVE USAR O NOME INTERNO DO SERVIÇO DENTRO DO DOCKER (web)
BASE_API_URL = "http://web:8000/api/devices"

CELERY_AUTH_TOKEN = config('CELERY_API_TOKEN', default='CELERY_TOKEN_MISSING')


# ==============================================================================
# TAREFA PRINCIPAL: PROCESSA E ENVIA O COMANDO PARA O DISPOSITIVO
# ==============================================================================
@shared_task
def process_scheduled_task(task_id):
    """
    Busca o ScheduledTask pelo ID, envia o comando via API para todos os devices associados
    e atualiza o status/histórico (last_run_at).
    """
    try:
        task = ScheduledTask.objects.get(pk=task_id)
    except ScheduledTask.DoesNotExist:
        logger.error(f"Tarefa agendada com ID {task_id} não encontrada.")
        return

    # Só processa se a tarefa estiver PENDENTE.
    if task.status != 'PENDING' and task.is_recurrent == False:
        logger.warning(f"Tarefa {task.pk} ('{task.name}') não está PENDENTE. Pulando execução.")
        return

    # Prepara o comando
    command_data = task.command_json
    all_success = True
    
    # Itera sobre todos os dispositivos associados à tarefa
    for device in task.devices.all():
        try:
            # 1. Tenta enviar o comando para o dispositivo (PATCH no registro do Device)
            device_api_url = f"{BASE_API_URL}/{device.device_id}/"
            
            # Cabeçalhos para autenticação e tipo de conteúdo
            headers = {
                'Authorization': f'Token {CELERY_AUTH_TOKEN}',
                # 'Content-Type': 'application/json'
            }
            
            # Payload para definir o comando pendente
            payload = {'pending_command': command_data}

            try:
                # Faz a requisição PATCH para atualizar o comando pendente
                response = requests.patch(
                    device_api_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=10
                ) 
            
                # Verifica o status da resposta
                if response.status_code == 200:
                    logger.info(f"Comando '{task.name}' enviado para {device.device_id}. Status: OK.")
                else:
                    # CRÍTICO: Exibe a resposta da API em caso de erro (ex: 401/403)
                    logger.error(f"Falha ao enviar comando para {device.device_id}. Status: {response.status_code}. Resposta: {response.text}")
                    # Aqui você pode mudar o status da tarefa para 'FALHOU'
                    task.status = 'FAILED'
                    task.save()
                    
            except requests.RequestException as e:
                logger.error(f"Erro de rede ao enviar comando para {device.device_id}: {e}")
                # Mude o status da tarefa para 'FALHOU' se houver erro de rede
                task.status = 'FAILED'
                task.save()

            
            
            

            # Usa PATCH para atualizar apenas o campo pending_command
            response = requests.patch(
                device_api_url, 
                json=payload, 
                headers=headers,
                timeout=10 
            )
            
            response.raise_for_status() # Lança exceção para códigos de status 4xx/5xx

            logger.warning(f"Comando '{command_data.get('action', 'N/A')}' enviado para {device.device_id} com sucesso. Status: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao enviar comando para o dispositivo {device.device_id}: {e}")
            all_success = False 
        except Exception as e:
            logger.error(f"Erro inesperado ao processar a tarefa {task.pk} para o dispositivo {device.device_id}: {e}")
            all_success = False

    # 2. Atualiza o status e o histórico da tarefa
    if all_success:
        # Tarefas únicas: marca como executada. Tarefas recorrentes: mantêm PENDING.
        if not task.is_recurrent:
            task.status = 'EXECUTED'
            
        task.last_run_at = timezone.now()
        task.save(update_fields=['status', 'last_run_at'])
        
        logger.info(f"Tarefa {task.pk} ('{task.name}') processada com sucesso. Status e histórico atualizados.")
        
    else:
        # Falha: se única, marca como FAILED. Se recorrente, atualiza last_run_at para evitar re-execução hoje.
        if not task.is_recurrent:
            task.status = 'FAILED'
            task.save(update_fields=['status'])
            logger.error(f"Tarefa única {task.pk} ('{task.name}') falhou e foi marcada como FAILED.")
        else:
            task.last_run_at = timezone.now() 
            task.save(update_fields=['last_run_at'])
            logger.error(f"Tarefa recorrente {task.pk} ('{task.name}') falhou, mas o last_run_at foi atualizado para evitar re-execução hoje.")


# ==============================================================================
# TAREFA AGENDADORA: CHAMADA PELO CELERY BEAT A CADA MINUTO
# ==============================================================================
@shared_task
def check_scheduled_tasks():
    """
    Verifica no banco de dados por tarefas agendadas que estão prontas para execução.
    """
    now = timezone.now()
    
    # 1. Obtém a HORA ATUAL LOCAL (America/Sao_Paulo) arredondada para o minuto (HH:MM:00)
    # É crucial usar a hora com o fuso horário ativo (TIME_ZONE)
    local_now = timezone.localtime(now) 
    current_time_str = local_now.strftime('%H:%M:00')
    
    # Obtém o dia da semana atual (0=Segunda, 6=Domingo) + 1
    current_day_of_week_str = str(local_now.weekday() + 1)
    
    # 1. Filtra por tarefas de agendamento ÚNICO
    unique_tasks = ScheduledTask.objects.filter(
        is_recurrent=False,
        status='PENDING',
        execution_time__lte=now
    ).distinct()

    # 2. Filtra por tarefas de agendamento RECORRENTE (Usando string de tempo para consulta ORM)
    recurrent_tasks_candidates = ScheduledTask.objects.filter(
        is_recurrent=True,
        status='PENDING',
        # Compara a hora agendada (TimeField) com a string de tempo (HH:MM:00)
        recurrent_time__lte=current_time_str,
    ).exclude(
        # Exclui tarefas que já rodaram HOJE.
        last_run_at__date=local_now.date() 
    )
    
    tasks_to_run = list(unique_tasks)
    
    # 3. Filtro de dias da semana para as recorrentes (Filtragem em memória)
    for task in recurrent_tasks_candidates:
        
        # 3a. Filtro de Dia da Semana: Checa se o dia atual está na lista.
        recurrent_days_list = task.recurrent_days.split(',') if task.recurrent_days else []
        
        if current_day_of_week_str in recurrent_days_list:
            tasks_to_run.append(task)

    logger.warning(f"[{local_now.strftime('%H:%M:%S')}] Encontradas {len(tasks_to_run)} tarefas prontas para rodar.")

    # Enfileira as tarefas para o Celery Worker
    run_count = 0
    for task in tasks_to_run:
        task_type = 'única' if not task.is_recurrent else 'recorrente'
        logger.warning(f" -> Tarefa {task_type} {task.pk} ('{task.name}') enfileirada para execução.")
        process_scheduled_task.delay(task.pk)
        run_count += 1

    return run_count


@shared_task
def check_device_status():
    """
    Verifica se algum dispositivo está inativo (sem heartbeat) e atualiza seu status.
    Esta tarefa deve ser executada a cada minuto pelo Celery Beat para garantir a precisão do status.
    """
    now = timezone.now()
    timeout_minutes = 5
    timeout_threshold = now - timedelta(minutes=timeout_minutes)
    
    # Busca dispositivos ativos que não foram vistos após o limite de tempo
    inactive_devices = Device.objects.filter(
        is_active=True,
        last_seen__lte=timeout_threshold
    )
    
    inactivated_count = inactive_devices.update(is_active=False)
    
    if inactivated_count > 0:
        logger.warning(f"Total de {inactivated_count} dispositivos inativados por timeout.")
        
    return inactivated_count