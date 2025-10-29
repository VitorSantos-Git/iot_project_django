# iot_project/core_system/celery.py

import os
from celery import Celery
from decouple import config

# Define o módulo de settings padrão do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_system.settings')

# Cria a instância da aplicação Celery. O argumento principal é o nome do módulo.
# O namespace='CELERY' fará com que todas as configurações relacionadas ao Celery
# sejam prefixadas com CELERY_ no settings.py (ex: CELERY_BROKER_URL).
app = Celery('core_system')

# Carrega as configurações do Django. As configurações do Celery devem estar no settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descobre as tarefas em todos os apps registrados no settings.py
# Celery procurará por um arquivo chamado 'tasks.py' em cada app.
app.autodiscover_tasks()

# Esta é uma tarefa de debug, você pode removê-la depois
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')