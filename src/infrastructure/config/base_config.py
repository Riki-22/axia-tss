# src/infrastructure/config/base_config.py
"""設定の基底クラス"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class BaseConfig:
    """設定クラスの基底クラス"""
    
    def __init__(self, env_path: Optional[Path] = None):
        """
        Args:
            env_path: .envファイルのパス（Noneの場合は自動検索）
        """
        self._load_env(env_path)
        self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-1')
    
    def _load_env(self, env_path: Optional[Path] = None):
        """環境変数ファイルを読み込む"""
        if env_path is None:
            # 複数の場所から.envを探す
            possible_paths = [
                Path(__file__).parent / '.env',
                Path(__file__).parent.parent.parent.parent / '.env',  # プロジェクトルート
                Path.cwd() / '.env'
            ]
            for path in possible_paths:
                if path.exists():
                    env_path = path
                    break
        
        if env_path and env_path.exists():
            load_dotenv(env_path)
            logger.info(f".env ファイル ({env_path}) を読み込みました。")
        else:
            logger.warning(".env ファイルが見つかりません。環境変数から設定を読み取ります。")
    
    def validate_required(self, fields: List[str]) -> List[str]:
        """必須フィールドの検証"""
        missing = []
        for field in fields:
            if not getattr(self, field, None):
                missing.append(field)
        return missing
    
    def get_env_bool(self, key: str, default: bool = False) -> bool:
        """環境変数をboolとして取得"""
        return os.getenv(key, str(default)).lower() in ('true', '1', 'yes')
    
    def get_env_int(self, key: str, default: int) -> int:
        """環境変数をintとして取得"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            logger.warning(f"{key}の値が不正です。デフォルト値{default}を使用します。")
            return default