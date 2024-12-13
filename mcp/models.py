from typing import Dict, List, Optional, Union
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, create_engine, BigInteger, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.types import TypeDecorator
from contextlib import contextmanager
from pydantic import BaseModel, Field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Metadata para migraciones
metadata = MetaData()

# Definición explícita de la tabla para migraciones
tweets_table = Table(
    'tweets',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('tweet_id', BigInteger, unique=True, index=True),
    Column('content', String),
    Column('author', String),
    Column('created_at', DateTime, index=True),
    Column('language', String),
    Column('category', String, index=True),
    Column('tweet_metadata', JSON),
    Column('relevance_score', Integer),
    Column('processed_at', DateTime)
)

Base = declarative_base(metadata=metadata)

def normalize_tweet_id(tweet_id: Union[str, int]) -> int:
    """Normaliza el ID del tweet a entero."""
    try:
        if isinstance(tweet_id, str):
            return int(tweet_id)
        return int(tweet_id)
    except (ValueError, TypeError) as e:
        logger.error(f"Error al normalizar tweet_id {tweet_id}: {str(e)}")
        raise ValueError(f"El tweet_id debe ser un número válido: {tweet_id}")

class Tweet(Base):
    """Modelo para almacenar tweets relacionados con incidentes."""
    __table__ = tweets_table

class Report(Base):
    """Modelo para almacenar informes generados."""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, index=True)
    total_tweets = Column(Integer)
    categories_count = Column(JSON)
    summary = Column(String)
    report_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic models for API
class TweetCreate(BaseModel):
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
    id: int
    processed_at: datetime

    class Config:
        from_attributes = True

class ReportResponse(BaseModel):
    id: int
    date: datetime
    total_tweets: int
    categories_count: Dict[str, int]
    summary: str
    report_path: str
    created_at: datetime

    class Config:
        from_attributes = True

def get_database_url():
    from os import getenv
    from dotenv import load_dotenv
    load_dotenv()
    
    return f"postgresql://{getenv('POSTGRES_USER')}:{getenv('POSTGRES_PASSWORD')}@{getenv('POSTGRES_HOST')}:{getenv('POSTGRES_PORT')}/{getenv('POSTGRES_DB')}"

def create_engine_with_retries():
    """Crea el engine de SQLAlchemy con reintentos."""
    url = get_database_url()
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=True  # Activamos el logging de SQL para depuración
    )

def drop_tables(engine):
    """Elimina todas las tablas existentes."""
    logger.info("Eliminando tablas existentes...")
    Base.metadata.drop_all(engine)

def init_db():
    """Inicializa la base de datos."""
    engine = create_engine_with_retries()
    # Primero eliminamos las tablas existentes
    drop_tables(engine)
    # Luego creamos las tablas nuevas
    logger.info("Creando tablas nuevas...")
    Base.metadata.create_all(engine)
    return engine

# Session Factory
SessionLocal = None
engine = None

def setup_database():
    """Configura la base de datos y crea el session factory."""
    global SessionLocal, engine
    engine = create_engine_with_retries()
    SessionLocal = scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    ))
    Base.metadata.create_all(engine)

@contextmanager
def get_db_session():
    """Proporciona una sesión de base de datos en un contexto seguro."""
    if SessionLocal is None:
        setup_database()
    
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
    return SessionLocal() 