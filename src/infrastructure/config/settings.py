# src/infrastructure/config/settings.py
"""統合設定クラス"""

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
                
        logger.info("設定の初期化が完了しました")
    
# シングルトンインスタンス
settings = Settings()