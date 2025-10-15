# src/infrastructure/di/container.py
import logging
from typing import Optional
from src.infrastructure.config.settings import settings
from src.infrastructure.persistence.dynamodb.kill_switch_repository import DynamoDBKillSwitchRepository
from src.infrastructure.persistence.dynamodb.order_repository import DynamoDBOrderRepository
from src.infrastructure.gateways.brokers.mt5.mt5_connection import MT5Connection
from src.infrastructure.gateways.brokers.mt5.mt5_order_executor import MT5OrderExecutor
from src.infrastructure.persistence.redis import RedisClient, RedisOhlcvDataRepository
from src.domain.services.order_validation import OrderValidationService

logger = logging.getLogger(__name__)

class DIContainer:
    """依存性注入コンテナ"""
    
    def __init__(self):
        self.settings = settings
        self._mt5_connection: Optional[MT5Connection] = None
        self._order_repository: Optional[DynamoDBOrderRepository] = None
        self._kill_switch_repository: Optional[DynamoDBKillSwitchRepository] = None
        self._redis_client: Optional[RedisClient] = None
        self._ohlcv_cache: Optional[RedisOhlcvDataRepository] = None
    
    def get_kill_switch_repository(self) -> DynamoDBKillSwitchRepository:
        """Kill Switchリポジトリを取得（シングルトン）"""
        if not self._kill_switch_repository:
            self._kill_switch_repository = DynamoDBKillSwitchRepository(
                table_name=self.settings.dynamodb_table_name,
                dynamodb_resource=self.settings.dynamodb_resource
            )
        return self._kill_switch_repository
    
    def get_order_repository(self) -> DynamoDBOrderRepository:
        """Orderリポジトリを取得（シングルトン）"""
        if not self._order_repository:
            self._order_repository = DynamoDBOrderRepository(
                table_name=self.settings.dynamodb_table_name,
                dynamodb_resource=self.settings.dynamodb_resource
            )
        return self._order_repository
    
    def get_mt5_connection(self) -> MT5Connection:
        """MT5接続を取得（シングルトン）"""
        if not self._mt5_connection:
            credentials = self.settings.get_mt5_credentials()
            self._mt5_connection = MT5Connection(
                credentials=credentials,
                terminal_path=self.settings.mt5_terminal_path
            )
        return self._mt5_connection
    
    def get_mt5_order_executor(self) -> MT5OrderExecutor:
        """MT5注文実行クラスを取得"""
        return MT5OrderExecutor(
            connection=self.get_mt5_connection(),
            validation_service=self.get_order_validation_service(),
            order_repository=self.get_order_repository(),
            magic_number=self.settings.mt5_magic_number
        )
    
    def get_order_validation_service(self) -> OrderValidationService:
        """注文検証サービスを取得"""
        return OrderValidationService()

    def get_redis_client(self) -> RedisClient:
        """
        RedisClientを取得（シングルトン）
        
        Returns:
            RedisClient: Redis接続管理クライアント
        
        Note:
            内部でシングルトンパターンを使用しているため、
            複数回呼び出しても同一インスタンスが返される
        """
        if not self._redis_client:
            self._redis_client = RedisClient.get_instance(
                host=self.settings.redis.redis_endpoint,
                port=self.settings.redis.redis_port,
                db=self.settings.redis.redis_db,
                socket_timeout=self.settings.redis.redis_socket_timeout,
                socket_connect_timeout=self.settings.redis.redis_socket_connect_timeout,
                retry_on_timeout=self.settings.redis.redis_retry_on_timeout,
                max_connections=self.settings.redis.redis_max_connections,
                decode_responses=self.settings.redis.redis_decode_responses
            )
            logger.info("RedisClient initialized via DIContainer")
        return self._redis_client
    
    def get_ohlcv_cache(self) -> RedisOhlcvDataRepository:
        """
        RedisOhlcvDataRepositoryを取得（シングルトン）
        
        Returns:
            RedisOhlcvDataRepository: OHLCV専用キャッシュ
        
        Note:
            内部でRedisClientを利用
        """
        if not self._ohlcv_cache:
            self._ohlcv_cache = RedisOhlcvDataRepository(
                redis_client=self.get_redis_client()
            )
            logger.info("RedisOhlcvDataRepository initialized via DIContainer")
        return self._ohlcv_cache

# シングルトンインスタンス
container = DIContainer()