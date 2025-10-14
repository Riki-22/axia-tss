# src/infrastructure/config/settings.py
"""統合設定クラス - 後方互換性を維持"""

import logging
from pathlib import Path
from typing import Optional

from .aws_config import AWSConfig
from .mt5_config import MT5Config
from .redis_config import RedisConfig
from .data_collector_config import DataCollectorConfig

logger = logging.getLogger(__name__)

class Settings:
    """統合設定クラス"""
    
    def __init__(self, env_path: Optional[Path] = None):
        """
        Args:
            env_path: .envファイルのパス
        """
        logger.info("設定を初期化中...")
        
        # AWS設定
        self.aws = AWSConfig()
        
        # MT5設定（AWSのSecretsManagerクライアントを渡す）
        self.mt5 = MT5Config(secretsmanager_client=self.aws.secretsmanager_client)
        
        # Redis設定
        self.redis = RedisConfig()
        
        # Data Collector設定（MT5のtimeframe_mapを渡す）
        self.data_collector = DataCollectorConfig(timeframe_map=self.mt5.timeframe_map)
        
        # 後方互換性のため、全ての属性をフラットにコピー
        self._flatten_configs()
        
        logger.info("設定の初期化が完了しました")
    
    def _flatten_configs(self):
        """後方互換性のため、全ての設定を直接アクセス可能にする"""
        # AWS
        self.aws_region = self.aws.aws_region
        self.queue_url = self.aws.queue_url
        self.dynamodb_table_name = self.aws.dynamodb_table_name
        self.s3_raw_data_bucket = self.aws.s3_raw_data_bucket
        self.dynamodb_resource = self.aws.dynamodb_resource
        self.sqs_client = self.aws.sqs_client
        self.secretsmanager_client = self.aws.secretsmanager_client
        self.s3_client = self.aws.s3_client
        
        # MT5
        self.mt5_terminal_path = self.mt5.mt5_terminal_path
        self.mt5_magic_number = self.mt5.mt5_magic_number
        self.mt5_secret_name = self.mt5.mt5_secret_name
        self.mt5_login = self.mt5.mt5_login
        self.mt5_password = self.mt5.mt5_password
        self.mt5_server = self.mt5.mt5_server
        self.timeframe_map = self.mt5.timeframe_map
        
        # Redis
        self.redis_endpoint = self.redis.redis_endpoint
        self.redis_port = self.redis.redis_port
        self.redis_db = self.redis.redis_db
        self.redis_ttl_hours = self.redis.redis_ttl_hours
        self.redis_max_memory_mb = self.redis.redis_max_memory_mb
        self.redis_socket_timeout = self.redis.redis_socket_timeout  
        self.redis_socket_connect_timeout = self.redis.redis_socket_connect_timeout  
        self.redis_retry_on_timeout = self.redis.redis_retry_on_timeout  
        self.redis_decode_responses = self.redis.redis_decode_responses  
        self.redis_max_connections = self.redis.redis_max_connections  
        self.redis_client = self.redis.redis_client
        
        # Data Collector
        self.data_collection_symbols = self.data_collector.data_collection_symbols
        self.data_collection_timeframes = self.data_collector.data_collection_timeframes
        self.data_fetch_counts = self.data_collector.data_fetch_counts
    
    def get_mt5_credentials(self):
        """MT5認証情報を取得（後方互換性）"""
        return self.mt5.get_mt5_credentials()

# シングルトンインスタンス
settings = Settings()