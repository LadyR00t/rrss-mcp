# Sistema de Análisis de Incidentes en Medios Sociales con MCP

Sistema avanzado de monitoreo y análisis de incidentes de seguridad en redes sociales implementando el [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction).

## Características Principales

### Implementación MCP
- 🔄 Protocolo MCP completo para interacción estructurada
- 📝 Gestión de contexto y estado de conversaciones
- 🔍 Validación de funciones y parámetros
- 🚦 Control de flujo y manejo de errores
- 📊 Retroalimentación y métricas

### Análisis de Seguridad
- 🔍 Monitoreo en tiempo real de Twitter
- 🤖 Análisis NLP con modelos spaCy
- 📊 Informes detallados y visualizaciones
- 🔄 Actualización automática horaria
- 🌍 Soporte multilingüe (ES/EN)

### Características Técnicas
- 🔐 Sistema de roles y permisos
- 📡 API RESTful con FastAPI
- 🗄️ Persistencia PostgreSQL
- 🐳 Contenedores Docker
- ✅ Pruebas unitarias completas

## Requisitos

- Python 3.9+
- Docker y Docker Compose
- API Key de Twitter (Bearer Token)
- PostgreSQL (incluido en Docker)

## Instalación Rápida

1. Clonar el repositorio:
```bash
git clone <repositorio>
cd <directorio>
```

2. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

3. Iniciar con Docker:
```bash
docker-compose up --build
```

## Uso del Sistema

### 1. Interfaz Web

Accede a las interfaces web:
- Dashboard: `http://localhost:8000/`
- Configuración: `http://localhost:8000/config`
- Informes: `http://localhost:8000/reports/{YYYY-MM-DD}.html`

### 2. API REST

#### Configuración
```bash
# Obtener configuración actual
curl -X GET http://localhost:8000/api/config

# Actualizar configuración
curl -X PUT http://localhost:8000/api/config/TWITTER_API_TIER \
  -H "Content-Type: application/json" \
  -d '{"value": "basic", "description": "Actualizar a tier básico"}'
```

#### Recolección de Datos
```bash
# Recolección manual
curl -X POST http://localhost:8000/collect

# Búsqueda histórica
curl -X POST http://localhost:8000/collect/historical \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2023-12-01T00:00:00Z", "end_date": "2023-12-02T00:00:00Z"}'
```

#### Generación de Informes
```bash
# Generar informe
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{"date": "2023-12-12T00:00:00Z"}'
```

### 3. Uso del Protocolo MCP

```python
from mcp.client import MCPClient
from mcp.mcp_core import MCPMessage, MCPRole, MCPMessageType, MCPRequest

# Inicializar cliente
client = MCPClient(api_key="your_api_key")

# Registrar función
client.register_function(
    name="collect_tweets",
    description="Recolecta tweets recientes",
    parameters={},
    required=[]
)

# Crear solicitud
request = MCPRequest(
    conversation_id="unique_id",
    message=MCPMessage(
        role=MCPRole.USER,
        type=MCPMessageType.TEXT,
        content="Recolectar tweets sobre ciberseguridad"
    )
)

# Generar respuesta
response = await client.generate_response(request)

# Actualizar estado
client.update_conversation_state("unique_id", {"last_collection": "2023-12-12"})
```

## Configuración Avanzada

### Tiers de API
- **Free**: 50 solicitudes/15min, máx 7 días históricos
- **Basic**: 150 solicitudes/15min, máx 30 días históricos
- **Pro**: 300 solicitudes/15min, máx 90 días históricos

### Variables de Entorno
```env
# API Twitter
TWITTER_BEARER_TOKEN=your_token_here
TWITTER_API_TIER=basic

# Base de Datos
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=mcp_incidents
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Configuración App
DATA_RETENTION_DAYS=7
TWEETS_PER_HOUR=15
ENABLE_MONITORING=true
MONITORING_INTERVAL=3600

# Keywords (separados por comas)
KEYWORDS=ciberseguridad,cybersecurity,hacking,infosec,malware,ransomware,phishing
```

## Estructura del Proyecto
```
mcp/
├── __init__.py
├── api.py           # API REST
├── client.py        # Cliente MCP
├── mcp_core.py      # Implementación MCP
├── models.py        # Modelos de datos
├── analyzer.py      # Análisis NLP
├── reporter.py      # Generación informes
├── scheduler.py     # Tareas programadas
└── templates/       # Plantillas UI
    ├── dashboard.html
    ├── config.html
    └── daily_report.html
```

## Tareas Automáticas

El sistema ejecuta automáticamente:
- Recolección de tweets (cada hora)
- Generación de informes (00:05 UTC)
- Limpieza de datos antiguos (00:30 UTC)

## Desarrollo y Pruebas

### Ejecutar Pruebas
```bash
# Instalar dependencias de desarrollo
poetry install --with dev

# Ejecutar pruebas
pytest

# Ejecutar pruebas con cobertura
pytest --cov=mcp
```

### Convenciones de Código
- Seguimos PEP 8
- Documentación en español
- Tipos estáticos con mypy
- Formateo con black

## Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/amazing_feature`)
3. Commit tus cambios (`git commit -m 'Add amazing feature'`)
4. Push a la rama (`git push origin feature/amazing_feature`)
5. Abre un Pull Request

## Licencia

Este proyecto está licenciado bajo MIT - ver el archivo [LICENSE](LICENSE) para más detalles.