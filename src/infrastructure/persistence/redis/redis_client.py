# src/infrastructure/persistence/redis/redis_client.py
"""Redis接続管理クラス（シングルトンパターン）"""

import logging
import time
from typing import Optional, List, Any
import redis
from redis.connection import ConnectionPool
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    RedisError
)

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis接続管理クラス（シングルトン）
    
    機能:
    - シングルトンパターンで接続を1つだけ維持
    - 接続プールによる効率的な接続再利用
    - 自動リトライロジック（指数バックオフ）
    - ヘルスチェック機能
    
    使用例:
        client = RedisClient.get_instance()
        client.set("key", b"value", ex=3600)
        value = client.get("key")
    """
    
    _instance: Optional['RedisClient'] = None
    _initialized: bool = False
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        retry_on_timeout: bool = True,
        max_connections: int = 10,
        decode_responses: bool = False
    ):
        """
        Args:
            host: Redisホスト
            port: Redisポート
            db: データベース番号
            socket_timeout: ソケットタイムアウト（秒）
            socket_connect_timeout: 接続タイムアウト（秒）
            retry_on_timeout: タイムアウト時のリトライ有効化
            max_connections: 最大接続数
            decode_responses: レスポンスのデコード（Falseでbytes返却）
        """
        # シングルトンの2重初期化を防止
        if RedisClient._initialized:
            return
        
        self.host = host
        self.port = port
        self.db = db
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        
        # 接続確立
        self._create_connection()
        
        RedisClient._initialized = True
        logger.info(f"RedisClient initialized: {host}:{port}")
    
    @classmethod
    def get_instance(
        cls,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        **kwargs
    ) -> 'RedisClient':
        """
        シングルトンインスタンスを取得
        
        Args:
            host: Redisホスト
            port: Redisポート
            db: データベース番号
            **kwargs: その他の設定
        
        Returns:
            RedisClient: シングルトンインスタンス
        
        Note:
            初回呼び出し時のみ引数が有効
            2回目以降は既存インスタンスを返す
        """
        if cls._instance is None:
            cls._instance = cls(host=host, port=port, db=db, **kwargs)
        return cls._instance
    
    def _create_connection(self) -> None:
        """
        Redis接続を確立
        
        Raises:
            RedisConnectionError: 接続失敗時
        """
        try:
            # 接続プール作成
            self._pool = ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_connect_timeout,
                retry_on_timeout=self.retry_on_timeout,
                max_connections=self.max_connections,
                decode_responses=self.decode_responses
            )
            
            # Redisクライアント作成
            self._client = redis.Redis(connection_pool=self._pool)
            
            # 接続確認
            self._client.ping()
            
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Redis connection: {e}")
            raise RedisConnectionError(f"Redis connection failed: {e}")
    
    def _retry_operation(
        self,
        operation,
        max_retries: int = 3,
        backoff_factor: float = 1.0
    ) -> Any:
        """
        リトライロジック付きで操作を実行
        
        Args:
            operation: 実行する操作（callable）
            max_retries: 最大リトライ回数
            backoff_factor: バックオフ係数（秒）
        
        Returns:
            Any: 操作の結果
        
        Raises:
            RedisError: 全てのリトライ失敗時
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return operation()
            
            except (RedisConnectionError, RedisTimeoutError) as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.warning(
                        f"Redis operation failed (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... Error: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Redis operation failed after {max_retries} attempts")
        
        raise last_exception
    
    def ping(self) -> bool:
        """
        ヘルスチェック
        
        Returns:
            bool: 接続が正常な場合True
        """
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    def get(self, key: str) -> Optional[bytes]:
        """
        値を取得
        
        Args:
            key: キー
        
        Returns:
            Optional[bytes]: 値（存在しない場合はNone）
        """
        try:
            return self._retry_operation(lambda: self._client.get(key))
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
            return None
    
    def set(
        self,
        key: str,
        value: bytes,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        値を設定
        
        Args:
            key: キー
            value: 値（bytes）
            ex: 有効期限（秒）
            px: 有効期限（ミリ秒）
            nx: キーが存在しない場合のみ設定
            xx: キーが存在する場合のみ設定
        
        Returns:
            bool: 成功時True
        """
        try:
            result = self._retry_operation(
                lambda: self._client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
            )
            return result is not None
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False
    
    def delete(self, *keys: str) -> int:
        """
        キーを削除
        
        Args:
            *keys: 削除するキー（複数指定可能）
        
        Returns:
            int: 削除されたキーの数
        """
        try:
            return self._retry_operation(lambda: self._client.delete(*keys))
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    def exists(self, *keys: str) -> int:
        """
        キーの存在確認
        
        Args:
            *keys: 確認するキー（複数指定可能）
        
        Returns:
            int: 存在するキーの数
        """
        try:
            return self._retry_operation(lambda: self._client.exists(*keys))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for keys {keys}: {e}")
            return 0
    
    def keys(self, pattern: str = "*") -> List[str]:
        """
        パターンマッチでキーを取得
        
        Args:
            pattern: パターン（例: "ohlcv:*"）
        
        Returns:
            List[str]: マッチしたキーのリスト
        
        Warning:
            大量のキーが存在する場合はパフォーマンスに注意
            本番環境ではSCANの使用を検討
        """
        try:
            result = self._retry_operation(lambda: self._client.keys(pattern))
            # bytesをstrに変換
            if self.decode_responses:
                return result
            return [key.decode('utf-8') for key in result]
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern '{pattern}': {e}")
            return []
    
    def ttl(self, key: str) -> int:
        """
        キーの残りTTLを取得
        
        Args:
            key: キー
        
        Returns:
            int: 残りTTL（秒）
                 -1: TTL未設定
                 -2: キーが存在しない
        """
        try:
            return self._retry_operation(lambda: self._client.ttl(key))
        except Exception as e:
            logger.error(f"Redis TTL failed for key '{key}': {e}")
            return -2
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        キーにTTLを設定
        
        Args:
            key: キー
            seconds: TTL（秒）
        
        Returns:
            bool: 成功時True
        """
        try:
            return self._retry_operation(lambda: self._client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
            return False
    
    def info(self, section: str = "all") -> dict:
        """
        Redis情報を取得
        
        Args:
            section: 取得するセクション（"memory", "stats"等）
        
        Returns:
            dict: Redis情報
        """
        try:
            return self._retry_operation(lambda: self._client.info(section))
        except Exception as e:
            logger.error(f"Redis INFO failed: {e}")
            return {}
    
    def close(self) -> None:
        """接続をクリーンアップ"""
        if self._pool:
            self._pool.disconnect()
            logger.info("Redis connection closed")
    
    def __del__(self):
        """デストラクタ"""
        self.close()
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        シングルトンインスタンスをリセット
        
        Note:
            主にテスト用
        """
        if cls._instance:
            cls._instance.close()
        cls._instance = None
        cls._initialized = False