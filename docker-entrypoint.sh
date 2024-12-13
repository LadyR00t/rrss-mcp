#!/bin/bash
set -e

# Función para manejar la señal de terminación
cleanup() {
    echo "Recibida señal de terminación. Deteniendo servicios..."
    kill -TERM "$child"
    wait "$child"
    exit 0
}

# Registrar el manejador de señales
trap cleanup SIGTERM SIGINT

# Ejecutar el comando principal
exec "$@" &
child=$!
wait "$child" 