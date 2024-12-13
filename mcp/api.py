from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from datetime import datetime, timedelta
import os
import logging

from .models import Tweet, Report, get_session, init_db, normalize_tweet_id
from .twitter_client import TwitterClient
from .analyzer import ContentAnalyzer
from .reporter import ReportGenerator

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_api")

app = FastAPI(title="Sistema de Análisis de Incidentes en Medios Sociales")

# Inicializar componentes
twitter_client = TwitterClient()
content_analyzer = ContentAnalyzer()
report_generator = ReportGenerator()

# Montar directorio de reportes
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

def cleanup_old_data():
    """Limpia datos antiguos según la configuración."""
    session = get_session()
    retention_days = int(os.getenv('DATA_RETENTION_DAYS', '7'))
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    deleted_count = session.query(Tweet).filter(Tweet.created_at < cutoff_date).delete()
    session.commit()
    logger.info(f"Limpieza completada: {deleted_count} tweets eliminados")
    return deleted_count

async def process_tweets():
    """Procesa nuevos tweets y los almacena en la base de datos."""
    logger.info("Iniciando proceso de recolección de tweets")
    
    try:
        tweets = twitter_client.get_recent_tweets()
        logger.info(f"Obtenidos {len(tweets)} tweets de la API")
        
        processed_count = 0
        skipped_count = 0
        failed_count = 0
        categories_found = {}
        
        for tweet_data in tweets:
            # Crear una nueva sesión para cada tweet
            session = get_session()
            try:
                with session.begin():
                    # Convertir tweet_id a entero
                    try:
                        tweet_id = normalize_tweet_id(tweet_data['tweet_id'])
                        logger.debug(f"Tweet ID normalizado: {tweet_id}")
                    except ValueError as e:
                        logger.error(f"Error al normalizar tweet_id: {str(e)}")
                        failed_count += 1
                        continue
                    
                    # Verificar si el tweet ya existe
                    existing = session.query(Tweet).filter_by(tweet_id=tweet_id).first()
                    if existing:
                        logger.debug(f"Tweet {tweet_id} ya existe en la base de datos")
                        skipped_count += 1
                        continue
                        
                    # Analizar contenido
                    category, relevance = content_analyzer.analyze_tweet(
                        tweet_data['content'],
                        tweet_data['language']
                    )
                    
                    if category and relevance > 0:
                        tweet = Tweet(
                            tweet_id=tweet_id,
                            content=tweet_data['content'],
                            author=tweet_data['author'],
                            created_at=tweet_data['created_at'],
                            language=tweet_data['language'],
                            category=category,
                            relevance_score=relevance,
                            tweet_metadata=tweet_data['metadata']
                        )
                        session.add(tweet)
                        processed_count += 1
                        categories_found[category] = categories_found.get(category, 0) + 1
                        logger.debug(f"Tweet {tweet_id} procesado exitosamente")
                    else:
                        logger.debug(f"Tweet {tweet_id} descartado por baja relevancia")
                        failed_count += 1
                        
            except Exception as e:
                logger.error(f"Error procesando tweet {tweet_data.get('tweet_id', 'unknown')}: {str(e)}")
                failed_count += 1
            finally:
                session.close()
        
        logger.info(f"Proceso completado: {processed_count} tweets procesados, {skipped_count} omitidos, {failed_count} fallidos")
        logger.info(f"Categorías encontradas: {categories_found}")
        
        return {
            "processed": processed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "categories": categories_found
        }
        
    except Exception as e:
        logger.error(f"Error en el proceso de recolección: {str(e)}", exc_info=True)
        raise

@app.on_event("startup")
async def startup_event():
    """Inicializa la base de datos y crea las tablas."""
    logger.info("Iniciando aplicación...")
    init_db()
    logger.info("Base de datos inicializada")

@app.get("/health")
async def health_check():
    """Endpoint de verificación de salud."""
    return {"status": "healthy"}

@app.post("/collect")
async def collect_tweets(background_tasks: BackgroundTasks):
    """Inicia la recolección de tweets."""
    try:
        logger.info("Iniciando recolección de tweets")
        results = await process_tweets()
        
        return {
            "message": "Recolección de tweets completada",
            "resultados": {
                "tweets_procesados": results["processed"],
                "tweets_omitidos": results["skipped"],
                "tweets_fallidos": results["failed"],
                "categorias_encontradas": results["categories"]
            }
        }
    except Exception as e:
        logger.error(f"Error en la recolección de tweets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en la recolección de tweets: {str(e)}"
        )

@app.post("/generate-report")
async def generate_report(date: Optional[str] = None):
    """Genera un informe para la fecha especificada."""
    try:
        # Verificar si hay tweets en la base de datos
        session = get_session()
        report_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow()
        
        # Definir el rango de fechas para el reporte
        start_date = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        # Contar tweets en el rango de fechas
        tweet_count = session.query(Tweet).filter(
            Tweet.created_at >= start_date,
            Tweet.created_at < end_date
        ).count()
        
        if tweet_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No hay tweets disponibles para la fecha {start_date.date()}. Por favor, ejecute primero /collect para recolectar datos."
            )
            
        report_path = report_generator.generate_daily_report(report_date)
        
        if not report_path:
            raise HTTPException(
                status_code=500,
                detail="Error al generar el informe. Verifica los logs para más detalles."
            )
            
        return {
            "message": "Informe generado correctamente",
            "report_url": f"/reports/{os.path.basename(report_path)}",
            "tweets_incluidos": tweet_count,
            "fecha_reporte": start_date.date().isoformat()
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado: {str(e)}"
        )

@app.get("/stats")
async def get_stats():
    """Obtiene estadísticas generales."""
    session = get_session()
    
    total_tweets = session.query(Tweet).count()
    
    if total_tweets == 0:
        return {
            "message": "No hay datos disponibles. Ejecute primero /collect para recolectar tweets.",
            "total_tweets": 0,
            "categories": {},
            "last_update": datetime.utcnow()
        }
    
    categories = session.query(Tweet.category).distinct().all()
    category_counts = {}
    
    for (category,) in categories:
        count = session.query(Tweet).filter_by(category=category).count()
        category_counts[category] = count
        
    return {
        "total_tweets": total_tweets,
        "categories": category_counts,
        "last_update": datetime.utcnow()
    }

@app.post("/cleanup")
async def cleanup_data():
    """Limpia datos antiguos manualmente."""
    try:
        cleanup_old_data()
        return {"message": "Limpieza completada"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la limpieza: {str(e)}"
        )

@app.get("/api-limits")
async def get_api_limits():
    """Obtiene información sobre los límites de la API de Twitter."""
    try:
        limits = twitter_client.get_limits_info()
        return {
            "status": "ok",
            "limits": limits,
            "recomendaciones": [
                "La API gratuita permite 50 solicitudes cada 15 minutos",
                "Máximo 100 tweets por solicitud",
                "Solo tweets de los últimos 7 días",
                "Considere espaciar las solicitudes de recolección"
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener límites: {str(e)}"
        ) 