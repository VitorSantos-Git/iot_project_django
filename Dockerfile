#iot_project/Dockerfile
# Use a imagem base oficial do Python para a versão 3.11
# Usaremos a variante "slim-buster" ou "slim-bullseye" por ser menor
FROM python:3.11-slim

# O Gunicorn é instalado aqui. Isso garante que o shell do container o encontre.
ENV PATH="/usr/local/bin:$PATH"

# Evita que o Python escreva arquivos .pyc no disco
ENV PYTHONDONTWRITEBYTECODE 1

# Força a saída de buffers para o terminal (útil para logs)
ENV PYTHONUNBUFFERED 1

# Define o diretório de trabalho no container
WORKDIR /app

# 1. Instalar dependências de sistema (necessárias para PostgreSQL)
# O "build-essential" é usado para compilar algumas bibliotecas Python (como o psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    # Dependências do PostgreSQL (libpq-dev)
    # Limpa o cache após a instalação para manter a imagem pequena
    && rm -rf /var/lib/apt/lists/*

# 2. Copiar o arquivo de requisitos e instalar as dependências
# Isso permite que o Docker utilize o cache se o requirements.txt não mudar
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 3. Copiar o restante do código do projeto para o diretório de trabalho
# O .dockerignore garantirá que arquivos como .git e .env não sejam copiados
COPY . /app/

# O Gunicorn será o servidor WSGI de produção
# O comando de inicialização será definido no docker-compose.yml