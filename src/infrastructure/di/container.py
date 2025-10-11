# src/infrastructure/di/container.py
import logging
from typing import Optional
from src.infrastructure.config.settings import settings
from src.infrastructure.persistence.dynamodb.kill_switch_repository import DynamoDBKillSwitchRepository
from src.infrastructure.persistence.dynamodb.order_repository import DynamoDBOrderRepository
from src.infrastructure.gateways.brokers.mt5.mt5_connection import MT5Connection
from src.infrastructure.gateways.brokers.mt5.mt5_order_executor import MT5OrderExecutor
from src.domain.services.order_validation import OrderValidationService

logger = logging.getLogger(__name__)

class DIContainer:
    """依存性注入コンテナ"""
    
    def __init__(self):
        self.settings = settings
        self._mt5_connection: Optional[MT5Connection] = None
        self._order_repository: Optional[DynamoDBOrderRepository] = None
        self._kill_switch_repository: Optional[DynamoDBKillSwitchRepository] = None
    
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

# シングルトンインスタンス
container = DIContainer()