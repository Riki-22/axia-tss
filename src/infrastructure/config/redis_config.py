# src/infrastructure/config/redis_config.py
"""Redis関連設定"""

import os
import logging
from typing import Optional
from .base_config import BaseConfig

logger = logging.getLogger(__name__)

class RedisConfig(BaseConfig):
    """Redis関連設定クラス"""
    
    def __init__(self):
        super().__init__()
        
        # Redis接続情報
        self.redis_endpoint = os.getenv('REDIS_ENDPOINT', 'localhost')
        self.redis_port = self.get_env_int('REDIS_PORT', 6379)
        self.redis_db = self.get_env_int('REDIS_DB', 0)
        
        # Redis動作設定
        self.redis_ttl_hours = self.get_env_int('REDIS_TTL_HOURS', 25)
        self.redis_max_memory_mb = self.get_env_int('REDIS_MAX_MEMORY_MB', 256)
        
        # Redis接続設定
        self.redis_socket_timeout = self.get_env_int('REDIS_SOCKET_TIMEOUT', 5)
        self.redis_socket_connect_timeout = self.get_env_int('REDIS_SOCKET_CONNECT_TIMEOUT', 5)
        self.redis_retry_on_timeout = self.get_env_bool('REDIS_RETRY_ON_TIMEOUT', True)
        self.redis_decode_responses = self.get_env_bool('REDIS_DECODE_RESPONSES', True)
        
        # Redis接続プール設定
        self.redis_max_connections = self.get_env_int('REDIS_MAX_CONNECTIONS', 10)
        
        # Redisクライアント
        self.redis_client = None
        if self.redis_endpoint and self.redis_endpoint != 'localhost':
            self._init_redis_client()
        
        logger.info(f"Redis設定: {self.redis_endpoint}:{self.redis_port} (DB:{self.redis_db})")
    
    def _init_redis_client(self):
        """Redis クライアント初期化"""
        try:
            import redis
            from redis.connection import ConnectionPool
            
            # 接続プール作成
            pool = ConnectionPool(
                host=self.redis_endpoint,
                port=self.redis_port,
                db=self.redis_db,
                max_connections=self.redis_max_connections,
                socket_timeout=self.redis_socket_timeout,
                socket_connect_timeout=self.redis_socket_connect_timeout,
                retry_on_timeout=self.redis_retry_on_timeout,
                decode_responses=self.redis_decode_responses
            )
            
            # Redisクライアント作成
            self.redis_client = redis.Redis(connection_pool=pool)
            
            # 接続テスト
            self.redis_client.ping()
            logger.info("Redis client initialized successfully")
            
        except ImportError:
            logger.warning("redis-py not installed. Redis features will be disabled.")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Redis client initialization failed: {e}")
            self.redis_client = None