FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install poetry==1.8.5

# Configurar Poetry para no crear entorno virtual
RUN poetry config virtualenvs.create false

# Directorio de trabajo
WORKDIR /app

# Copiar solo los archivos de configuración primero
COPY pyproject.toml ./

# Generar el archivo lock
RUN poetry lock

# Instalar dependencias principales
RUN poetry install --only main

# Descargar modelos de spaCy
RUN python -m spacy download es_core_news_sm
RUN python -m spacy download en_core_web_sm

# Copiar el resto del código fuente
COPY . .

# Puerto para FastAPI
EXPOSE 8000

# Script de inicio que maneja señales
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Comando para ejecutar la aplicación
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "mcp"] 