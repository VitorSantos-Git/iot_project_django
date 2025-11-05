# iot_project/core_system/authentication.py

from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from devices.models import Device
from decouple import config

# --- Novo Usuário Fantasma para Celery ---
class CeleryUser:
    """Classe que simula um usuário para a requisição Celery/Sistema."""
    is_staff = True
    is_active = True
    pk = -1
    def __str__(self):
        return "Celery Master User"
    def is_authenticated(self):
        return True
    
CELERY_MASTER_TOKEN = config('CELERY_API_TOKEN', default='CELERY_TOKEN_MISSING')

class TokenAuthentication(authentication.BaseAuthentication):
    """
    Autenticação baseada em Token para dispositivos IoT (ESP8266).
    Espera o token no cabeçalho HTTP: Authorization: Token <SEU_TOKEN_AQUI>
    """
        
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return None

        try:
            auth_type, auth_token = auth_header.split()
        except ValueError:
            raise exceptions.AuthenticationFailed('Formato do cabeçalho Authorization incorreto.')

        if auth_type.lower() != 'token':
            raise exceptions.AuthenticationFailed('O tipo de autenticação deve ser "Token".')
        
        # VERIFICAÇÃO DO TOKEN MESTRE (CELERY)
        if auth_token == CELERY_MASTER_TOKEN:
            # Se for o Celery, retornamos o usuário fantasma (CeleryUser) para autenticar
            # e dar acesso total. O DRF espera (user, auth_token).
            return (CeleryUser(), auth_token)

        # 2. Busca o Device pelo Token fornecido (Para requisições do ESP)
        try:
            device = Device.objects.get(device_id=auth_token)
        except Device.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token de dispositivo inválido.')
        
        # 3. Sucesso: retorna o objeto Device como o \"user\" (pois o DRF espera um user-like object)
        return (device, auth_token)
    

