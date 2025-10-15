# src/infrastructure/config/redis_config.py
"""Redis関連設定"""
import os
import logging
from .base_config import BaseConfig

logger = logging.getLogger(__name__)


class RedisConfig(BaseConfig):
    """Redis関連設定クラス"""
   
    def __init__(self):
        super().__init__()
       
        # ========================================
        # Redis接続情報
        # ========================================
        self.redis_endpoint = os.getenv('REDIS_ENDPOINT', 'localhost')
        self.redis_port = self.get_env_int('REDIS_PORT', 6379)
        self.redis_db = self.get_env_int('REDIS_DB', 0)
       
        # ========================================
        # Redis接続設定
        # ========================================
        self.redis_socket_timeout = self.get_env_int('REDIS_SOCKET_TIMEOUT', 5)
        self.redis_socket_connect_timeout = self.get_env_int('REDIS_SOCKET_CONNECT_TIMEOUT', 5)
        self.redis_retry_on_timeout = self.get_env_bool('REDIS_RETRY_ON_TIMEOUT', True)
        self.redis_decode_responses = self.get_env_bool('REDIS_DECODE_RESPONSES', False)
       
        # ========================================
        # Redis接続プール設定
        # ========================================
        self.redis_max_connections = self.get_env_int('REDIS_MAX_CONNECTIONS', 10)
       
        # ========================================
        # キャッシュ動作設定
        # ========================================
        # メモリ監視閾値
        self.redis_memory_warning_mb = self.get_env_int('REDIS_MEMORY_WARNING_MB', 40)
        self.redis_memory_critical_mb = self.get_env_int('REDIS_MEMORY_CRITICAL_MB', 50)
        
        # NYクローズ時刻設定（FX市場サイクル）
        self.ny_close_hour_edt = self.get_env_int('NY_CLOSE_HOUR_EDT', 6)  # 夏時間: JST 06:00
        self.ny_close_hour_est = self.get_env_int('NY_CLOSE_HOUR_EST', 7)  # 冬時間: JST 07:00
        
        # 週末データ保持期間
        self.weekend_retention_hours = self.get_env_int('WEEKEND_RETENTION_HOURS', 40)
        
        # キャッシュクリーンアップ時刻
        self.cache_cleanup_hour = self.get_env_int('CACHE_CLEANUP_HOUR', 8)  # 毎朝8時JST
        
        # ========================================
        # MessagePack設定
        # ========================================
        self.msgpack_use_bin_type = self.get_env_bool('MSGPACK_USE_BIN_TYPE', True)
       
        logger.info(
            f"Redis設定初期化完了: "
            f"{self.redis_endpoint}:{self.redis_port} (DB:{self.redis_db})"
        )