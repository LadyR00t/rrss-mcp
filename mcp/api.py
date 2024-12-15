from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import logging
import os
from . import models
from .models import ServiceConfig
from .twitter_client import TwitterClient
from sqlalchemy import func

# Configurar logger
logger = logging.getLogger(__name__)

app = FastAPI()

# Configurar templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Montar directorio de reportes como estático
reports_dir = os.path.join(os.getcwd(), "reports")
os.makedirs(reports_dir, exist_ok=True)
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")

# Configurar el cliente de Twitter
twitter_client = TwitterClient()

# Obtener una sesión de base de datos
def get_db():
    """Obtener una sesión de base de datos."""
    db = models.get_session()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación."""
    models.setup_database()

@app.get("/health")
def health_check():
    """Endpoint de verificación de salud."""
    return {"status": "healthy"}

@app.get("/api/config")
def get_configs(db: Session = Depends(get_db)):
    """Obtener todas las configuraciones."""
    try:
        configs = db.query(models.ServiceConfig).all()
        if not configs:
            logger.warning("No se encontraron configuraciones")
        return [{"key": c.key, "value": c.value, "description": c.description} for c in configs]
    except Exception as e:
        logger.error(f"Error al obtener configuraciones: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener configuraciones")

@app.put("/api/config/{key}")
def update_config(
    key: str,
    config: models.ConfigUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar una configuración."""
    try:
        # Validar que la configuración existe
        existing_config = db.query(models.ServiceConfig).filter(
            models.ServiceConfig.key == key
        ).first()
        
        if not existing_config:
            raise HTTPException(status_code=404, detail=f"Configuración {key} no encontrada")
        
        # Validaciones específicas según el tipo de configuración
        if key == "TWITTER_API_TIER":
            if not models.ConfigUpdate.validate_tier(config.value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Valor inválido para TWITTER_API_TIER. Debe ser uno de: {list(models.TWITTER_TIERS.keys())}"
                )
        elif key in models.TIER_DEPENDENT_CONFIGS:
            if not models.ConfigUpdate.validate_numeric(config.value):
                raise HTTPException(
                    status_code=400,
                    detail=f"{key} debe ser un número entero positivo"
                )
        
        # Actualizar la configuración
        try:
            models.ServiceConfig.set_config(
                db,
                key,
                config.value,
                config.description
            )
            db.commit()
            return {"key": key, "value": config.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar configuración: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar configuración")

def normalize_datetime(dt: datetime) -> datetime:
    """Normaliza un datetime a UTC sin zona horaria."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas del sistema."""
    try:
        # Obtener estadísticas de tweets
        total_tweets = db.query(models.Tweet).count()
        categories = db.query(
            models.Tweet.category,
            func.count(models.Tweet.id).label('count')
        ).group_by(models.Tweet.category).all()
        
        # Obtener última actualización
        last_tweet = db.query(models.Tweet).order_by(
            models.Tweet.created_at.desc()
        ).first()
        
        return {
            "total_tweets": total_tweets,
            "categories": {cat: count for cat, count in categories},
            "last_update": last_tweet.created_at if last_tweet else None
        }
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error al obtener estadísticas"
        )

@app.post("/collect/historical")
async def collect_historical_tweets(
    date_range: models.DateRange,
    db: Session = Depends(get_db)
):
    """Recolectar tweets históricos."""
    try:
        # Normalizar fechas
        start_date = normalize_datetime(date_range.start_date)
        current_time = normalize_datetime(datetime.utcnow())
        
        # Validar fechas
        max_days = int(models.ServiceConfig.get_config(db, 'MAX_HISTORICAL_DAYS', '7'))
        if (current_time - start_date).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"No se pueden buscar tweets de más de {max_days} días atrás"
            )
        
        # Configurar fecha final
        end_date = None
        if date_range.end_date:
            end_date = normalize_datetime(date_range.end_date)
            if end_date > current_time:
                end_date = current_time
        
        tweets = await twitter_client.get_historical_tweets(
            start_date,
            end_date
        )
        
        if not tweets:
            return {
                "message": "No se encontraron tweets en el rango especificado",
                "resultados": {
                    "tweets_procesados": 0,
                    "tweets_omitidos": 0,
                    "tweets_fallidos": 0,
                    "categorias": {}
                }
            }
        
        results = process_tweets(db, tweets)
        return {
            "message": "Tweets históricos recolectados exitosamente",
            "resultados": {
                "tweets_procesados": results["processed"],
                "tweets_omitidos": results["skipped"],
                "tweets_fallidos": results["failed"],
                "categorias": results["categories"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en búsqueda histórica: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en búsqueda histórica: {str(e)}"
        )

@app.post("/collect")
async def collect_tweets(db: Session = Depends(get_db)):
    """Recolectar tweets recientes."""
    try:
        # Verificar configuración
        token = ServiceConfig.get_config(db, "TWITTER_BEARER_TOKEN")
        if not token:
            raise HTTPException(
                status_code=400,
                detail="No se ha configurado el token de autenticación"
            )
        
        # Verificar límites
        limits = twitter_client.get_limits_info()
        if limits["remaining_requests"] <= 0:
            raise HTTPException(
                status_code=429,
                detail="Se ha alcanzado el límite de solicitudes. Por favor, espere."
            )
        
        # Obtener tweets
        tweets = await twitter_client.get_recent_tweets()
        if not tweets:
            return {
                "message": "No se encontraron tweets nuevos",
                "resultados": {
                    "tweets_procesados": 0,
                    "tweets_omitidos": 0,
                    "tweets_fallidos": 0,
                    "categorias": {}
                }
            }
        
        # Procesar tweets
        results = process_tweets(db, tweets)
        return {
            "message": "Tweets recolectados exitosamente",
            "resultados": {
                "tweets_procesados": results["processed"],
                "tweets_omitidos": results["skipped"],
                "tweets_fallidos": results["failed"],
                "categorias": results["categories"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al recolectar tweets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al recolectar tweets: {str(e)}"
        )

@app.post("/generate-report")
def generate_report(
    report_date: models.ReportDate,
    db: Session = Depends(get_db)
):
    """Generar informe para una fecha específica."""
    # Obtener tweets del día
    start_date = report_date.date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1)
    
    tweets = db.query(models.Tweet).filter(
        models.Tweet.created_at >= start_date,
        models.Tweet.created_at < end_date
    ).all()
    
    if not tweets:
        raise HTTPException(
            status_code=404,
            detail="No hay tweets disponibles para generar el informe"
        )
    
    # Generar informe
    categories = {}
    for tweet in tweets:
        categories[tweet.category] = categories.get(tweet.category, 0) + 1
    
    report = models.Report(
        date=start_date.date(),
        total_tweets=len(tweets),
        categories=categories,
        report_url=f"/reports/{start_date.strftime('%Y-%m-%d')}.html"
    )
    
    db.add(report)
    db.commit()
    
    return {
        "message": "Informe generado exitosamente",
        "report_url": report.report_url
    }

@app.get("/api-limits")
def get_api_limits(db: Session = Depends(get_db)):
    """Obtener información sobre límites de API."""
    tier = models.ServiceConfig.get_config(db, "TWITTER_API_TIER", "free")
    limits = twitter_client.get_limits_info()
    
    return {
        "tier": {
            "nombre": tier,
            "descripcion": "Tier actual de la API"
        },
        "limites_configurados": {
            "dias_historicos": int(models.ServiceConfig.get_config(db, "MAX_HISTORICAL_DAYS", "7")),
            "solicitudes_por_ventana": int(models.ServiceConfig.get_config(db, "RATE_LIMIT_REQUESTS", "50")),
            "ventana_tiempo": int(models.ServiceConfig.get_config(db, "RATE_LIMIT_WINDOW", "900"))
        },
        "estado_actual": {
            "solicitudes_restantes": limits["remaining_requests"],
            "ultima_solicitud": limits["last_request"],
            "siguiente_reinicio": limits["next_reset"]
        },
        "recomendaciones": [
            "Considere actualizar a un tier superior si necesita más capacidad",
            "Distribuya las solicitudes uniformemente durante el día",
            "Utilice la búsqueda histórica con moderación"
        ]
    }

def process_tweets(db: Session, tweets: List[Dict]) -> Dict:
    """Procesar tweets y guardarlos en la base de datos."""
    results = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "categories": {}
    }
    
    for tweet in tweets:
        try:
            # Verificar si el tweet ya existe
            existing = db.query(models.Tweet).filter_by(
                tweet_id=int(tweet["id"])
            ).first()
            
            if existing:
                results["skipped"] += 1
                continue
            
            # Crear nuevo tweet
            new_tweet = models.Tweet(
                tweet_id=int(tweet["id"]),
                content=tweet["text"],
                author=tweet["author_id"],
                created_at=datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")),
                language=tweet.get("lang", "es"),
                category=tweet.get("category", "otros"),
                relevance_score=float(tweet.get("relevance_score", 0.5))
            )
            
            db.add(new_tweet)
            results["processed"] += 1
            results["categories"][new_tweet.category] = results["categories"].get(
                new_tweet.category, 0
            ) + 1
            
        except Exception as e:
            results["failed"] += 1
            continue
    
    db.commit()
    return results 

def cleanup_old_data(db: Session):
    """Limpiar datos antiguos basado en la configuración de retención."""
    try:
        # Obtener días de retención de la configuración
        retention_days = int(ServiceConfig.get_config(db, "DATA_RETENTION_DAYS", "7"))
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Eliminar tweets antiguos
        deleted_tweets = db.query(models.Tweet).filter(
            models.Tweet.created_at < cutoff_date
        ).delete()
        
        # Eliminar informes antiguos
        deleted_reports = db.query(models.Report).filter(
            models.Report.date < cutoff_date.date()
        ).delete()
        
        db.commit()
        
        logger.info(
            f"Limpieza completada: {deleted_tweets} tweets y {deleted_reports} "
            f"informes más antiguos que {retention_days} días fueron eliminados"
        )
        
        return {
            "tweets_eliminados": deleted_tweets,
            "informes_eliminados": deleted_reports,
            "fecha_corte": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error durante la limpieza de datos: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la limpieza de datos: {str(e)}"
        ) 

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Renderizar el dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/config", response_class=HTMLResponse)
async def get_config_page(request: Request):
    """Renderizar la página de configuración."""
    return templates.TemplateResponse("config.html", {"request": request})

@app.get("/reports/{report_name}")
async def get_report(report_name: str):
    """Servir un informe específico."""
    report_path = os.path.join(reports_dir, report_name)
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Informe no encontrado")
    
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content) 