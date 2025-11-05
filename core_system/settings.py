#iot_project/core_system/settings.py

from pathlib import Path
from decouple import config
from django.utils import timezone
from datetime import timedelta
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# Adicionamos 'localhost' e o IP do host (lido do .env)
ALLOWED_HOSTS = ['localhost', '127.0.0.1', config('ALLOWED_HOST', default='')]


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- Nossas Aplicações ---
    'rest_framework',        # 1. Habilita o Django REST Framework
    'devices.apps.DevicesConfig', # 2. Registra a aplicação 'devices'
    'django_celery_beat', # 3. Habilita o Django para usar o Celery Beat
    # --------------------------
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core_system.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE'),
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'client_encoding': 'UTF8'
        }
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Pasta de destino para os arquivos estáticos coletados no modo DEBUG=False (Produção)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================================================
# CELERY CONFIGURATION (Para Agendamento de Tarefas)
# ==============================================================================
# O Celery usará o Redis como broker para mensagens e backend para resultados
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')

# Define o formato de serialização dos dados
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE # Reusa a configuração de TimeZone do Django

# ==============================================================================
# CONFIGURAÇÃO CELERY BEAT (Agendador Recorrente)
# ==============================================================================
CELERY_BEAT_SCHEDULE = {
    'check-scheduled-tasks-every-minute': {
        # O caminho completo para a função da tarefa agendadora
        'task': 'devices.tasks.check_scheduled_tasks',
        # Agendar para rodar a cada 60 segundos
        'schedule': timedelta(seconds=60), 
        # Argumentos vazios para a função (ela não aceita argumentos)
        'args': (), 
    },
    'check-device-status-every-minute': { 
        'task': 'devices.tasks.check_device_status',
        'schedule': timedelta(seconds=60), 
        'args': (), 
    },
}


# ==============================================================================
# CONFIGURAÇÃO JAZZMIN (Tema para o Admin do Django)
# ==============================================================================
JAZZMIN_SETTINGS = {
     # --- Configurações Gerais da Interface (Global) ---

    # Título da janela do navegador (aparece na aba do navegador)
    # Se ausente ou None, usará o site_title do admin.site do Django.
    "site_title": "IoT",
    
    # Título na tela de login do painel administrativo (máximo 19 caracteres)
    # Se ausente ou None, usará o site_header do admin.site do Django.
    "site_header": "IoT Login (IFSP-CMP)",
    
    ## Título da marca que aparece no canto superior esquerdo da sidebar (máximo 19 caracteres)
    # Geralmente acompanha o site_logo.
    "site_brand": "Sistema IoT",
    
    # Caminho relativo para o logo do seu site. Deve estar na pasta de arquivos estáticos.
    # Usado como logo principal no canto superior esquerdo (próximo ao site_brand).
    "site_logo": "img/logoV.png", # (opcional)
    
    # Logo específico para a tela de login. Se None, usará o site_logo.
    "login_logo": None, # Opcional: Logo para a página de login

    # Classes CSS adicionais aplicadas à imagem do logo (site_logo).
    # Ex: "img-circle" para deixá-lo circular.
    #"site_logo_classes": None,

    # Caminho relativo para um favicon (o pequeno ícone na aba do navegador).
    # Se ausente, tentará usar o site_logo. Idealmente 32x32 pixels.
    #"site_icon": None,

    # Texto de boas-vindas exibido na tela de login.
    "welcome_sign": "Bem-vindo ao Painel de Controle IoT",

    # Remover o rodapé 
    "show_footer": False,

    # Texto de direitos autorais exibido no rodapé do painel administrativo.
    #"copyright": "Painel de Controle IoT - Projeto de Ensino",

    # Se você quiser usar um único campo de busca, não precisa usar uma lista, pode usar uma string simples
    # Lista de modelos (formato 'app_label.ModelName') que serão incluídos na barra de pesquisa global.
    # Se esta configuração for omitida, a barra de pesquisa não será exibida.
    # "search_model": ["auth.User", "auth.Group"],

    # Nome do campo no seu modelo de usuário que contém a imagem/URL do avatar.
    # Pode ser o nome de um campo ou uma função que retorna a URL do avatar do usuário.
    "user_avatar": None,

    

    
    
    ############
    # Top Menu #
    ############

    # URLs de atalho (ajudará a navegar para o dashboard)
    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        # URL principal
        #{"name": "Início", "url": "/"}, 
        # Link para documentação (opcional)
        #{"model": "auth.User"},
        # Link para o Dashboard de Dispositivos (a nova rota que configuramos)
        {"name": "*Dispositivo Painel*", "url": "/devices/dashboard/", "new_window": True},
        # Link para site da escola (opcional)
        {"name": "**IFSP CMP**", "url": "https://portal.cmp.ifsp.edu.br"},
    ],
    
    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # for the full list of 5.13.0 free icon classes
    # Dicionário para definir ícones Font Awesome personalizados para aplicativos e modelos no menu lateral.
    # Ícones para as aplicações
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "devices.device": "fas fa-microchip",
        "devices.telemetrydata": "fa-solid fa-book",
        "devices.scheduledtask": "fas fa-clock",
    },

    #Necessário esconder o rodapé completo e messagem do loggout
    "custom_css": "admin/css/custom_admin.css", # Caminho para o CSS CUSTOMIZADO
    
    "show_ui_controls": False,
    "navigation_expanded": True,
    "current_url_name": "admin:index", # Garante que o menu ativo funciona
    "changeform_format": "vertical_tabs", # Layout mais limpo para formulários
    "changeform_format_overrides": {"auth.user": "vertical_tabs"},
}

# Opcional: Para traduzir títulos no Admin
JAZZMIN_UI_TWEAKS = {
    "theme": "united",
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-light",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_accordion": True,
    "dark_mode_listener": False,
    "footer_text": "",
    "heading_title_mapping": {
        "General": "Geral ou Informações Básicas",  # Mapeia o título "General" para o seu texto
        # Adicione outras traduções aqui se necessário, ex:
        # "Permissions": "Permissões de Acesso", 
    },
}