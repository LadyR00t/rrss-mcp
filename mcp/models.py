from typing import Dict, List, Optional, Union
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Date, create_engine, BigInteger, MetaData, Table, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.types import TypeDecorator
from contextlib import contextmanager
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import time
import os
from datetime import datetime, timezone
from pydantic import validator

logger = logging.getLogger(__name__)

# Metadata para migraciones
metadata = MetaData()

# Base declarativa
Base = declarative_base(metadata=metadata)

class Tweet(Base):
    """Modelo para almacenar tweets."""
    __tablename__ = 'tweets'
    
    id = Column(Integer, primary_key=True)
    tweet_id = Column(BigInteger, unique=True, nullable=False)
    content = Column(String, nullable=False)
    author = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    language = Column(String(2), nullable=False)
    category = Column(String, nullable=False)
    tweet_metadata = Column(JSON, nullable=True)
    relevance_score = Column(Float, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    def __init__(self, **kwargs):
        # Convertir tweet_id a entero si es string
        if 'tweet_id' in kwargs and isinstance(kwargs['tweet_id'], str):
            kwargs['tweet_id'] = int(kwargs['tweet_id'])
        super().__init__(**kwargs)

class Report(Base):
    """Modelo para almacenar informes."""
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    total_tweets = Column(Integer, nullable=False)
    categories = Column(JSON, nullable=False)
    report_url = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class ServiceConfig(Base):
    """Modelo para configuraciones del servicio."""
    __tablename__ = "service_config"
    
    # Configuraciones predeterminadas
    TWITTER_TIERS = {
        'free': {
            'max_requests_15min': 50,
            'max_tweets_request': 100,
            'max_historical_days': 7,
            'tweets_per_month': 500000,
            'rate_limit_requests': 25,
            'rate_limit_window': 900,
            'tweets_per_hour': 10,
            'description': 'API Gratuita - Límites básicos'
        },
        'basic': {
            'max_requests_15min': 150,
            'max_tweets_request': 100,
            'max_historical_days': 30,
            'tweets_per_month': 2000000,
            'rate_limit_requests': 50,
            'rate_limit_window': 900,
            'tweets_per_hour': 15,
            'description': 'API Basic - Límites intermedios'
        },
        'pro': {
            'max_requests_15min': 300,
            'max_tweets_request': 500,
            'max_historical_days': 90,
            'tweets_per_month': 5000000,
            'rate_limit_requests': 100,
            'rate_limit_window': 900,
            'tweets_per_hour': 30,
            'description': 'API Pro - Límites avanzados'
        }
    }

    # Mapeo de configuraciones que dependen del tier
    TIER_DEPENDENT_CONFIGS = {
        'MAX_HISTORICAL_DAYS': 'max_historical_days',
        'RATE_LIMIT_REQUESTS': 'rate_limit_requests',
        'RATE_LIMIT_WINDOW': 'rate_limit_window',
        'TWEETS_PER_HOUR': 'tweets_per_hour'
    }

    # Configuraciones por defecto del sistema
    DEFAULT_CONFIGS = {
        'TWITTER_API_TIER': ('free', 'Tier actual de la API de Twitter'),
        'TWITTER_BEARER_TOKEN': ('', 'Token de autenticación para la API de Twitter'),
        'DATA_RETENTION_DAYS': ('7', 'Días de retención de datos'),
        'ENABLE_MONITORING': ('true', 'Habilitar monitoreo continuo'),
        'MONITORING_INTERVAL': ('3600', 'Intervalo de monitoreo en segundos')
    }
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    @classmethod
    def get_config(cls, db: Session, key: str, default: str = None) -> str:
        """Obtener valor de configuración."""
        try:
            # Si la configuración depende del tier, obtener el valor según el tier actual
            if key in cls.TIER_DEPENDENT_CONFIGS:
                tier = cls.get_config(db, "TWITTER_API_TIER", "free")
                tier_config = cls.TWITTER_TIERS[tier][cls.TIER_DEPENDENT_CONFIGS[key]]
                return str(tier_config)
            
            config = db.query(cls).filter(cls.key == key).first()
            if config is None:
                # Si no existe la configuración, usar el valor por defecto del sistema
                if key in cls.DEFAULT_CONFIGS:
                    default_value, description = cls.DEFAULT_CONFIGS[key]
                    cls.set_config(db, key, default_value, description)
                    return default_value
            return config.value if config else default
        except Exception as e:
            logger.error(f"Error al obtener configuración {key}: {str(e)}")
            return default
    
    @classmethod
    def set_config(cls, db: Session, key: str, value: str, description: str = None) -> None:
        """Establecer valor de configuración."""
        try:
            # Validaciones específicas
            if key == "TWITTER_API_TIER":
                if value not in cls.TWITTER_TIERS:
                    raise ValueError(f"Valor inválido para TWITTER_API_TIER. Debe ser uno de: {list(cls.TWITTER_TIERS.keys())}")
                
                # Actualizar todas las configuraciones dependientes del tier
                for config_key, tier_key in cls.TIER_DEPENDENT_CONFIGS.items():
                    new_value = str(cls.TWITTER_TIERS[value][tier_key])
                    cls.update_or_create(db, config_key, new_value, f"Configuración automática según tier {value}")
            
            # Validar valores numéricos
            elif key in ["MAX_HISTORICAL_DAYS", "RATE_LIMIT_REQUESTS", "RATE_LIMIT_WINDOW", "TWEETS_PER_HOUR", "DATA_RETENTION_DAYS", "MONITORING_INTERVAL"]:
                try:
                    num_value = int(value)
                    if num_value <= 0:
                        raise ValueError()
                except ValueError:
                    raise ValueError(f"{key} debe ser un número entero positivo")
            
            # Validar valores booleanos
            elif key == "ENABLE_MONITORING":
                if value.lower() not in ["true", "false"]:
                    raise ValueError(f"{key} debe ser 'true' o 'false'")
            
            cls.update_or_create(db, key, value, description)
            
        except ValueError as e:
            logger.error(f"Error de validación al establecer configuración {key}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error al establecer configuración {key}: {str(e)}")
            db.rollback()
            raise ValueError(f"Error al establecer configuración {key}: {str(e)}")
    
    @classmethod
    def update_or_create(cls, db: Session, key: str, value: str, description: str = None) -> None:
        """Actualizar o crear una configuración."""
        config = db.query(cls).filter(cls.key == key).first()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = cls(key=key, value=value, description=description)
            db.add(config)
        
        db.flush()

def get_database_url():
    """Obtiene la URL de conexión a la base de datos."""
    from os import getenv
    from dotenv import load_dotenv
    load_dotenv()
    
    # Si estamos en modo prueba, usar SQLite en memoria
    if getenv('TESTING') == 'true':
        return 'sqlite:///:memory:'
    
    # En producción, usar PostgreSQL
    return f"postgresql://{getenv('POSTGRES_USER')}:{getenv('POSTGRES_PASSWORD')}@{getenv('POSTGRES_HOST')}:{getenv('POSTGRES_PORT')}/{getenv('POSTGRES_DB')}"

def create_engine_with_retries(max_retries=3, retry_interval=1):
    """Crea el motor de la base de datos con reintentos."""
    url = get_database_url()
    connect_args = {}
    
    if url.startswith('sqlite'):
        connect_args['check_same_thread'] = False
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                connect_args=connect_args
            )
            # Verificar la conexión
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Error al crear el motor de base de datos después de {max_retries} intentos: {e}")
                raise
            time.sleep(retry_interval)

# Session Factory global
SessionLocal = None
engine = None

def setup_database():
    """Configura la base de datos y crea el session factory."""
    global SessionLocal, engine
    
    if SessionLocal is not None:
        return  # Ya está inicializada
    
    try:
        engine = create_engine_with_retries()
        SessionLocal = scoped_session(sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        ))
        
        # Crear todas las tablas
        Base.metadata.create_all(bind=engine)
        
        # Configurar valores por defecto solo si estamos en producción
        if os.getenv('TESTING') != 'true':
            session = SessionLocal()
            try:
                if session.query(ServiceConfig).count() == 0:
                    # Usar las configuraciones por defecto de ServiceConfig
                    for key, (value, description) in ServiceConfig.DEFAULT_CONFIGS.items():
                        config = ServiceConfig(key=key, value=value, description=description)
                        session.add(config)
                    
                    session.commit()
            except Exception as e:
                logger.error(f"Error al configurar valores por defecto: {e}")
                session.rollback()
                raise
            finally:
                session.close()
                
        return SessionLocal
    except Exception as e:
        logger.error(f"Error al configurar la base de datos: {e}")
        raise

@contextmanager
def get_db_session():
    """Proporciona una sesión de base de datos en un contexto seguro."""
    if SessionLocal is None:
        setup_database()
        
    # Asegurar que las tablas existen
    if engine is not None:
        Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en la sesión de base de datos: {str(e)}")
        raise
    finally:
        session.close()

def get_session():
    """Obtiene una nueva sesión de la base de datos."""
    if SessionLocal is None:
        setup_database()
        
    # Asegurar que las tablas existen
    if engine is not None:
        Base.metadata.create_all(bind=engine)
    
    return SessionLocal()

def init_db():
    """Inicializa la base de datos."""
    setup_database()

# Pydantic models for API
class TweetCreate(BaseModel):
    """Modelo para crear tweets."""
    tweet_id: Union[str, int]
    content: str
    author: str
    created_at: datetime
    language: str
    category: str
    tweet_metadata: Dict = Field(default_factory=dict)
    relevance_score: int

    def normalize(self) -> 'TweetCreate':
        """Normaliza los datos del tweet."""
        if isinstance(self.tweet_id, str):
            self.tweet_id = int(self.tweet_id)
        return self

class TweetResponse(TweetCreate):
    """Modelo para respuesta de tweets."""
    id: int
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True

class ReportResponse(BaseModel):
    """Modelo para respuesta de informes."""
    id: int
    date: datetime
    total_tweets: int
    categories_count: Dict[str, int]
    summary: str
    report_path: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConfigUpdate(BaseModel):
    """Modelo para actualizar la configuración."""
    value: str = Field(..., description="Valor de la configuración")
    description: Optional[str] = Field(None, description="Descripción opcional de la configuración")

    @classmethod
    def validate_tier(cls, value: str) -> bool:
        """Validar valor de tier."""
        return value in ServiceConfig.TWITTER_TIERS
    
    @classmethod
    def validate_numeric(cls, value: str) -> bool:
        """Validar valor numérico."""
        try:
            num = int(value)
            return num > 0
        except ValueError:
            return False

class ConfigResponse(BaseModel):
    """Modelo para respuesta de configuración."""
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True

class DateRange(BaseModel):
    """Modelo para rango de fechas."""
    start_date: datetime = Field(
        ...,
        description="Fecha de inicio (YYYY-MM-DD)",
        example="2023-12-01T00:00:00Z"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="Fecha final (YYYY-MM-DD, opcional)",
        example="2023-12-02T00:00:00Z"
    )

    @validator('start_date', 'end_date')
    def validate_dates(cls, v):
        """Validar fechas."""
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v

    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validar rango de fechas."""
        if v is None:
            return v
        if 'start_date' in values and v < values['start_date']:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial")
        return v

class ReportDate(BaseModel):
    """Modelo para fecha de informe."""
    date: datetime = Field(..., description="Fecha del informe (YYYY-MM-DD)")
  