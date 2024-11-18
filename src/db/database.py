import asyncio
import logging
from typing import Optional, Tuple
import asyncpg
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.utils.constants import DB_SETTINGS, CACHE_SETTINGS
from src.config.settings import get_settings
from .init_v3_schema import init_v3_schema
from .init_rsi_schema import init_rsi_schema

logger = logging.getLogger('DraXon_OCULUS')

async def init_db(database_url: str) -> asyncpg.Pool:
    """Initialize PostgreSQL connection pool and create tables"""
    try:
        # Create the connection pool
        pool = await asyncpg.create_pool(
            database_url,
            min_size=DB_SETTINGS['POOL_SIZE'],
            max_size=DB_SETTINGS['POOL_SIZE'] + DB_SETTINGS['MAX_OVERFLOW'],
            command_timeout=DB_SETTINGS['POOL_TIMEOUT'],
            statement_cache_size=0,  # Disable statement cache for better memory usage
        )
        
        if not pool:
            raise Exception("Failed to create database pool")
        
        # Initialize schemas
        settings = get_settings()
        await init_v3_schema(settings)
        logger.info("V3 schema initialized successfully")
        
        await init_rsi_schema(settings)
        logger.info("RSI schema initialized successfully")
            
        logger.info("Database pool initialized successfully")
        return pool
        
    except Exception as e:
        logger.error(f"Error initializing database pool: {e}")
        raise

async def init_redis(redis_url: str) -> redis.Redis:
    """Initialize Redis connection with retry logic"""
    for attempt in range(CACHE_SETTINGS['REDIS_RETRY_COUNT']):
        try:
            # Create Redis connection with timeout settings
            redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,  # Automatically decode responses to strings
                socket_timeout=CACHE_SETTINGS['REDIS_TIMEOUT'],
                socket_connect_timeout=CACHE_SETTINGS['REDIS_TIMEOUT'],
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test the connection
            await redis_client.ping()
            
            logger.info("Redis connection initialized successfully")
            return redis_client
            
        except redis.TimeoutError:
            logger.warning(f"Redis connection timeout (attempt {attempt + 1}/{CACHE_SETTINGS['REDIS_RETRY_COUNT']})")
            if attempt < CACHE_SETTINGS['REDIS_RETRY_COUNT'] - 1:
                await asyncio.sleep(CACHE_SETTINGS['REDIS_RETRY_DELAY'])
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error (attempt {attempt + 1}): {e}")
            if attempt < CACHE_SETTINGS['REDIS_RETRY_COUNT'] - 1:
                await asyncio.sleep(CACHE_SETTINGS['REDIS_RETRY_DELAY'])
        except Exception as e:
            logger.error(f"Unexpected Redis error: {e}")
            raise
    
    raise Exception("Failed to establish Redis connection after retries")

def create_sqlalchemy_engine(database_url: str):
    """Create SQLAlchemy async engine"""
    return create_async_engine(
        database_url,
        echo=DB_SETTINGS['ECHO'],
        pool_size=DB_SETTINGS['POOL_SIZE'],
        max_overflow=DB_SETTINGS['MAX_OVERFLOW'],
        pool_timeout=DB_SETTINGS['POOL_TIMEOUT'],
        pool_recycle=DB_SETTINGS['POOL_RECYCLE']
    )
