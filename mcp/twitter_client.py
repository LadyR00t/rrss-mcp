import tweepy
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
import os
from dotenv import load_dotenv
import time
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twitter_client")

class TwitterClient:
    """Cliente para la API v2 de Twitter."""
    
    def __init__(self):
        load_dotenv()
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if not self.bearer_token:
            logger.error("No se encontró TWITTER_BEARER_TOKEN en las variables de entorno")
            raise ValueError("TWITTER_BEARER_TOKEN es requerido")
            
        logger.info(f"Inicializando cliente de Twitter con token: {self.bearer_token[:10]}...")
        
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            wait_on_rate_limit=True
        )
        self.keywords = os.getenv('KEYWORDS', '').split(',')
        self.tweets_per_hour = min(int(os.getenv('TWEETS_PER_HOUR', '20')), 100)
        self.last_request_time = None
        self.remaining_requests = 50

        logger.info(f"Keywords configurados: {self.keywords}")
        logger.info(f"Tweets por hora configurados: {self.tweets_per_hour}")

    def _build_query(self) -> str:
        """Construye la consulta de búsqueda."""
        # Limpiamos y validamos keywords
        query_parts = [keyword.strip() for keyword in self.keywords if keyword.strip()]
        if not query_parts:
            logger.error("No se encontraron keywords válidos para la búsqueda")
            raise ValueError("Se requiere al menos un keyword válido")

        # Construimos la query base con los keywords
        base_query = ' OR '.join(query_parts)
        
        # Añadimos filtros
        filters = [
            '-is:retweet',  # Excluir retweets
            '(lang:es OR lang:en)'  # Filtrar por idioma
        ]
        
        # Combinamos todo
        final_query = f"({base_query}) {' '.join(filters)}"
        
        logger.info(f"Query construido: {final_query}")
        return final_query

    def _check_rate_limit(self) -> Tuple[bool, int]:
        """Verifica los límites de tasa y espera si es necesario."""
        if self.last_request_time:
            time_passed = datetime.now() - self.last_request_time
            if time_passed < timedelta(minutes=15) and self.remaining_requests <= 0:
                wait_time = 15*60 - time_passed.total_seconds()
                logger.warning(f"Límite de tasa alcanzado. Esperando {wait_time} segundos")
                return False, int(wait_time)
        return True, 0

    def get_recent_tweets(self) -> List[Dict]:
        """Obtiene tweets recientes basados en las palabras clave."""
        logger.info("Iniciando búsqueda de tweets recientes...")
        
        can_request, wait_time = self._check_rate_limit()
        if not can_request:
            msg = f"Límite de tasa excedido. Por favor, espere {wait_time} segundos."
            logger.error(msg)
            raise Exception(msg)

        query = self._build_query()
        tweets_data = []
        
        try:
            logger.info(f"Ejecutando búsqueda con max_results={self.tweets_per_hour}")
            response = self.client.search_recent_tweets(
                query=query,
                max_results=self.tweets_per_hour,
                tweet_fields=['created_at', 'lang', 'author_id', 'public_metrics'],
                user_fields=['username', 'description'],
                expansions=['author_id']
            )
            
            # Actualizar contadores de límite de tasa
            self.last_request_time = datetime.now()
            self.remaining_requests = int(response.meta.get('remaining', 0))
            
            logger.info(f"Respuesta recibida. Meta: {response.meta}")
            logger.info(f"Includes: {response.includes if hasattr(response, 'includes') else 'No includes'}")
            logger.info(f"Datos recibidos: {len(response.data) if response.data else 0} tweets")
            
            # Crear diccionario de usuarios
            users = {user.id: user for user in response.includes['users']} if response.includes else {}
            
            for tweet in response.data or []:
                author = users.get(tweet.author_id)
                tweet_data = {
                    'tweet_id': tweet.id,
                    'content': tweet.text,
                    'author': author.username if author else 'unknown',
                    'created_at': tweet.created_at,
                    'language': tweet.lang,
                    'metadata': {
                        'author_id': tweet.author_id,
                        'collected_at': datetime.now().isoformat(),
                        'rate_limit_remaining': self.remaining_requests,
                        'metrics': tweet.public_metrics if hasattr(tweet, 'public_metrics') else {},
                        'author_description': author.description if author else None
                    }
                }
                tweets_data.append(tweet_data)
                logger.debug(f"Tweet procesado: {tweet.id} de @{tweet_data['author']}")
            
            logger.info(f"Procesados {len(tweets_data)} tweets en total")
                
        except tweepy.TooManyRequests as e:
            reset_time = getattr(e, 'reset_time', 900)
            msg = f"Límite de tasa excedido. Reset en {reset_time} segundos."
            logger.error(msg)
            raise Exception(msg)
        except Exception as e:
            logger.error(f"Error inesperado al obtener tweets: {str(e)}", exc_info=True)
            raise
            
        return tweets_data

    def get_limits_info(self) -> Dict:
        """Obtiene información sobre los límites de la API."""
        info = {
            "remaining_requests": self.remaining_requests,
            "last_request": self.last_request_time.isoformat() if self.last_request_time else None,
            "next_reset": (self.last_request_time + timedelta(minutes=15)).isoformat() if self.last_request_time else None,
            "tweets_per_request": self.tweets_per_hour,
            "max_requests_per_15min": 50,
            "query_keywords": self.keywords
        }
        logger.info(f"Información de límites actual: {info}")
        return info

    def get_tweet_by_id(self, tweet_id: str) -> Dict:
        """Obtiene un tweet específico por su ID."""
        try:
            response = self.client.get_tweet(
                tweet_id,
                tweet_fields=['created_at', 'lang', 'author_id'],
                user_fields=['username'],
                expansions=['author_id']
            )
            
            if not response.data:
                return None
                
            tweet = response.data
            author = response.includes['users'][0] if response.includes.get('users') else None
            
            return {
                'tweet_id': tweet.id,
                'content': tweet.text,
                'author': author.username if author else 'unknown',
                'created_at': tweet.created_at,
                'language': tweet.lang,
                'metadata': {
                    'author_id': tweet.author_id,
                }
            }
            
        except Exception as e:
            print(f"Error al obtener tweet {tweet_id}: {str(e)}")
            return None 