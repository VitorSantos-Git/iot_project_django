# iot_project/core_system/authentication.py

from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from devices.models import Device 
from decouple import config

# --- Classe que simula um usuário autenticado para o Celery/Sistema ---
class CeleryUser:
    """Objeto que simula um usuário autenticado e com permissões (is_staff=True)."""
    # DRF Permissions geralmente verificam is_authenticated e is_staff/is_superuser
    is_staff = True
    is_active = True
    pk = -1 # Um PK inválido/não usado para o Celery
    
    def __str__(self):
        return "Celery Master User"
    
    @property
    def is_authenticated(self):
        """Propriedade para compatibilidade com versões mais recentes do Django."""
        return True

CELERY_MASTER_TOKEN = config('CELERY_API_TOKEN', default='CELERY_TOKEN_MISSING')

class TokenAuthentication(authentication.BaseAuthentication):
    """
    Autenticação baseada em Token para dispositivos IoT (ESP8266) e Celery.
    Espera o token no cabeçalho HTTP: Authorization: Token <SEU_TOKEN_AQUI>
    """
        
    def authenticate(self, request):
        # 1. Tenta extrair o token do cabeçalho 'Authorization'
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return None

        try:
            auth_type, auth_token = auth_header.split()
        except ValueError:
            raise exceptions.AuthenticationFailed('Formato do cabeçalho Authorization incorreto.')

        if auth_type.lower() != 'token':
            raise exceptions.AuthenticationFailed('O tipo de autenticação deve ser "Token".')
        
        # VERIFICAÇÃO 1: TOKEN MESTRE (CELERY)
        if auth_token == CELERY_MASTER_TOKEN:
            # RETORNA O USUÁRIO FANTASMA (CeleryUser) para autenticar o processo Celery
            return (CeleryUser(), auth_token)

        # VERIFICAÇÃO 2: TOKEN DO DISPOSITIVO (ESP8266)
        try:
            device = Device.objects.get(device_id=auth_token)
        except Device.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token de dispositivo inválido.')
        
        # 4. Sucesso: retorna o objeto Device como o \"user\" para o DRF
        return (device, auth_token)
    
