# iot_project/core_system/authentication.py
from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from devices.models import Device # Importamos o modelo Device que usaremos para o token

class TokenAuthentication(authentication.BaseAuthentication):
    """
    Autenticação baseada em Token para dispositivos IoT (ESP8266).
    Espera o token no cabeçalho HTTP: Authorization: Token <SEU_TOKEN_AQUI>
    """
        
    # O DRF espera que este método verifique a autenticação
    def authenticate(self, request):
        # 1. Tenta extrair o token do cabeçalho 'Authorization'
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            # Se não houver cabeçalho, não autenticado
            return None

        # Esperamos o formato "Token SEU_TOKEN"
        try:
            # Divide a string "Token SEU_TOKEN" em ['Token', 'SEU_TOKEN']
            auth_type, auth_token = auth_header.split()
        except ValueError:
            # Se o formato estiver incorreto (ex: apenas um token sem "Token ")
            raise exceptions.AuthenticationFailed('Formato do cabeçalho Authorization incorreto.')

        if auth_type.lower() != 'token':
            raise exceptions.AuthenticationFailed('O tipo de autenticação deve ser "Token".')

        # 2. Busca o Device pelo Token fornecido
        try:
            # Usamos o próprio 'device_id' do ESP8266 como o "Token" de autenticação inicial, 
            # ou podemos gerar um campo de token real.
            # Para simplificar, usaremos o device_id como o "Token" que o ESP envia
            device = Device.objects.get(device_id=auth_token)
        except Device.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token de dispositivo inválido.')
        
        # # 3. Verifica se o dispositivo está ativo
        # if not device.is_active:
        #     raise exceptions.AuthenticationFailed('Dispositivo não está ativo.')

        # 4. Sucesso: retorna o usuário (device) e o token usado
        # Como o ESP não usa um usuário Django padrão, retornamos o objeto Device como o "user"
        return (device, auth_token)
    

    