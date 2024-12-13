#!/bin/bash

# Verificar si .env existe
if [ ! -f .env ]; then
    echo "Creando archivo .env desde .env.example..."
    cp .env.example .env
    echo "Por favor, edita el archivo .env con tus credenciales antes de continuar."
    exit 1
fi

# Limpiar contenedores existentes
echo "Limpiando contenedores existentes..."
docker-compose down -v

# Construir las imágenes
echo "Construyendo las imágenes..."
docker-compose build --no-cache

# Iniciar los servicios
echo "Iniciando los servicios..."
docker-compose up 