#!/bin/bash

# Limpiar contenedores existentes
echo "Limpiando contenedores existentes..."
docker-compose down -v

# Construir las imágenes
echo "Construyendo las imágenes..."
docker-compose build --no-cache

# Iniciar los servicios
echo "Iniciando los servicios..."
docker-compose up 