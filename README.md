# Sistema de Análisis de Incidentes en Medios Sociales

Sistema de monitoreo y análisis de incidentes de seguridad en redes sociales usando el [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction).

## Características

- 🔍 Monitoreo de Twitter para incidentes de seguridad
- 🤖 Análisis automático de contenido usando NLP
- 📊 Generación de informes con gráficos y estadísticas
- 🔄 Actualización automática cada hora
- 🌍 Soporte para español e inglés

## Requisitos

- Python 3.9+
- Docker y Docker Compose
- API Key de Twitter (Bearer Token)
- PostgreSQL (incluido en Docker Compose)

## Instalación

1. Clona este repositorio:
```bash
git clone <repositorio>
cd <directorio>
```

2. Copia el archivo de ejemplo de variables de entorno:
```bash
cp .env.example .env
```

3. Edita el archivo `.env` con tus credenciales:
```env
# Twitter API v2 Credentials
TWITTER_BEARER_TOKEN=your_bearer_token_here

# PostgreSQL Database
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=mcp_incidents
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Application Settings
DATA_RETENTION_DAYS=7
TWEETS_PER_HOUR=20
KEYWORDS=ransomware,phishing,data_breach
```

4. Construye y ejecuta los contenedores:
```bash
docker-compose up --build
```

## Uso del Sistema

### 1. Verificación de Límites de API

Antes de comenzar, verifica los límites de la API:
```bash
curl -X GET http://localhost:8000/api-limits
```

Respuesta:
```json
{
    "status": "ok",
    "limits": {
        "remaining_requests": 50,
        "last_request": null,
        "next_reset": null,
        "tweets_per_request": 20,
        "max_requests_per_15min": 50
    },
    "recomendaciones": [
        "La API gratuita permite 50 solicitudes cada 15 minutos",
        "Máximo 100 tweets por solicitud",
        "Solo tweets de los últimos 7 días",
        "Considere espaciar las solicitudes de recolección"
    ]
}
```

### 2. Recolección de Tweets

Para iniciar la recolección:
```bash
curl -X POST http://localhost:8000/collect
```

Respuesta:
```json
{
    "message": "Recolección de tweets completada",
    "tweets_procesados": 15
}
```

### 3. Consulta de Estadísticas

Para ver las estadísticas actuales:
```bash
curl -X GET http://localhost:8000/stats
```

Respuesta:
```json
{
    "total_tweets": 15,
    "categories": {
        "ransomware": 5,
        "phishing": 7,
        "data_breach": 3
    },
    "last_update": "2023-12-12T16:30:00Z"
}
```

### 4. Generación de Informes

Para generar un informe:
```bash
# Informe del día actual
curl -X POST http://localhost:8000/generate-report

# Informe de una fecha específica
curl -X POST "http://localhost:8000/generate-report?date=2023-12-12"
```

Respuesta:
```json
{
    "message": "Informe generado correctamente",
    "report_url": "/reports/report_20231212.html",
    "tweets_incluidos": 15,
    "fecha_reporte": "2023-12-12"
}
```

### 5. Acceso a los Informes

Los informes están disponibles en:
- `http://localhost:8000/reports/report_YYYYMMDD.html`

### 6. Limpieza Manual de Datos

Para limpiar datos antiguos:
```bash
curl -X POST http://localhost:8000/cleanup
```

## Tareas Automáticas

El sistema ejecuta automáticamente:
- Recolección de tweets cada hora
- Generación de informes diarios (00:05)
- Limpieza de datos antiguos (00:30)

## Limitaciones de la API Gratuita

- 50 solicitudes cada 15 minutos
- Máximo 100 tweets por solicitud
- Solo tweets de los últimos 7 días
- 500,000 tweets por mes

## Recomendaciones de Uso

1. **Ajuste de Frecuencia**:
   - Reduzca `TWEETS_PER_HOUR` si encuentra límites de tasa
   - Use el endpoint `/api-limits` para monitorear el uso

2. **Optimización de Búsqueda**:
   - Ajuste las palabras clave en `KEYWORDS`
   - Balance entre especificidad y cobertura

3. **Mantenimiento**:
   - Monitoree el espacio en disco
   - Revise los logs regularmente
   - Ajuste `DATA_RETENTION_DAYS` según necesidad

## Documentación API

La documentación completa de la API está disponible en:
- `http://localhost:8000/docs`

## Licencia

MIT