# src/infrastructure/config/mt5_config.py
"""MT5関連設定"""

import os
import json
import logging
from typing import Dict, Any, Optional
from .base_config import BaseConfig

# MT5は条件付きインポート
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

logger = logging.getLogger(__name__)

class MT5Config(BaseConfig):
    """MT5関連設定クラス"""
    
    def __init__(self, secretsmanager_client=None):
        super().__init__()
        
        self.secretsmanager_client = secretsmanager_client
        
        # MT5設定
        self.mt5_terminal_path = os.getenv('MT5_TERMINAL_PATH')
        self.mt5_magic_number = self.get_env_int('MT5_MAGIC_NUMBER', 12345)
        self.mt5_secret_name = os.getenv('MT5_SECRET_NAME')
        
        # ローカルMT5認証情報（開発用）
        self.mt5_login = os.getenv('MT5_LOGIN')
        self.mt5_password = os.getenv('MT5_PASSWORD')
        self.mt5_server = os.getenv('MT5_SERVER')
        
        # タイムフレームマッピング
        self.timeframe_map = self._init_timeframe_map()
        
        # 設定検証
        self._validate()
    
    def _init_timeframe_map(self) -> Dict[str, int]:
        """MT5タイムフレームマッピング初期化"""
        if MT5_AVAILABLE and mt5:
            return {
                "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
                "MN1": mt5.TIMEFRAME_MN1
            }
        else:
            # ダミー値（開発環境用）
            return {
                "M1": 1, "M5": 5, "M15": 15, "M30": 30,
                "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
                "MN1": 43200
            }
    
    def _validate(self):
        """設定検証"""
        missing = []
        if not self.mt5_secret_name and not self.mt5_login:
            missing.append("MT5_SECRET_NAME or MT5_LOGIN")
        if not self.mt5_terminal_path:
            missing.append("MT5_TERMINAL_PATH")
        
        if missing:
            logger.warning(f"MT5設定値が不足: {', '.join(missing)}")
    
    def get_mt5_credentials(self) -> Dict[str, Any]:
        """MT5認証情報を取得"""
        
        # Secrets Manager優先
        if self.mt5_secret_name and self.secretsmanager_client:
            try:
                logger.info(f"Secrets Manager からシークレット '{self.mt5_secret_name}' を取得します...")
                
                response = self.secretsmanager_client.get_secret_value(
                    SecretId=self.mt5_secret_name
                )
                
                if 'SecretString' in response:
                    secret = json.loads(response['SecretString'])
                    
                    # 必須キーの確認
                    if all(k in secret for k in ['mt5_login', 'mt5_password', 'mt5_server']):
                        logger.info("MT5認証情報の取得成功。")
                        return secret
                    else:
                        logger.error("シークレット内に必要なキーが見つかりません。")
                        
            except Exception as e:
                logger.error(f"Secrets Managerからのシークレット取得中にエラー: {e}")
        
        # フォールバック：環境変数から取得
        if self.mt5_login and self.mt5_password and self.mt5_server:
            logger.info("環境変数からMT5認証情報を使用します")
            return {
                'mt5_login': self.mt5_login,
                'mt5_password': self.mt5_password,
                'mt5_server': self.mt5_server
            }
        
        logger.error("MT5認証情報が見つかりません")
        return {}