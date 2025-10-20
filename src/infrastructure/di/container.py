# src/infrastructure/di/container.py
import logging
from typing import Optional
from src.infrastructure.config.settings import settings
from src.infrastructure.persistence.dynamodb.dynamodb_kill_switch_repository import DynamoDBKillSwitchRepository
from src.infrastructure.persistence.dynamodb.dynamodb_order_repository import DynamoDBOrderRepository
from src.infrastructure.gateways.brokers.mt5.mt5_connection import MT5Connection
from src.infrastructure.gateways.brokers.mt5.mt5_order_executor import MT5OrderExecutor
from src.infrastructure.gateways.brokers.mt5.mt5_price_provider import MT5PriceProvider
from src.infrastructure.gateways.brokers.mt5.mt5_account_provider import MT5AccountProvider
from src.infrastructure.gateways.brokers.mt5.mt5_position_provider import MT5PositionProvider
from src.infrastructure.persistence.dynamodb.dynamodb_position_repository import DynamoDBPositionRepository
from src.infrastructure.persistence.redis import RedisClient, RedisOhlcvDataRepository
from src.domain.services.order_validation import OrderValidationService
from src.infrastructure.gateways.messaging.sqs.order_publisher import SQSOrderPublisher
from src.infrastructure.gateways.market_data.ohlcv_data_provider import OhlcvDataProvider

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
        self._sqs_order_publisher: Optional[SQSOrderPublisher] = None
        self._ohlcv_data_provider: Optional[OhlcvDataProvider] = None
        self._mt5_price_provider: Optional[MT5PriceProvider] = None
        self._mt5_account_provider: Optional[MT5AccountProvider] = None
        self._mt5_position_provider: Optional[MT5PositionProvider] = None
        self._position_repository: Optional[DynamoDBPositionRepository] = None
    
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

    def get_sqs_order_publisher(self) -> SQSOrderPublisher:
        """
        SQS注文送信クラスを取得（シングルトン）
        
        Returns:
            SQSOrderPublisher: SQS注文パブリッシャーインスタンス
        
        Usage:
            >>> container = DIContainer()
            >>> publisher = container.get_sqs_order_publisher()
            >>> success, msg_id = publisher.send_order(order_data)
        """
        if not self._sqs_order_publisher:
            self._sqs_order_publisher = SQSOrderPublisher(
                queue_url=self.settings.queue_url,
                sqs_client=self.settings.sqs_client
            )
            logger.info("SQSOrderPublisher initialized")
        return self._sqs_order_publisher

    def get_ohlcv_data_provider(self) -> OhlcvDataProvider:
        """
        OhlcvDataProviderを取得（シングルトン）
        
        統合データプロバイダー:
        - Redis（キャッシュ）- オプショナル
        - MT5（リアルタイム）- オプショナル
        - S3（ヒストリカル）- オプショナル
        - yfinance（フォールバック）- 必須
        
        Returns:
            OhlcvDataProvider: 統合データプロバイダー
        
        Usage:
            >>> container = DIContainer()
            >>> provider = container.get_ohlcv_data_provider()
            >>> df, meta = provider.get_data_with_freshness('USDJPY', 'H1')
        """
        if not self._ohlcv_data_provider:
            # オプション: Redis（キャッシュ）
            try:
                ohlcv_cache = self.get_ohlcv_cache()
                logger.info("Redis cache available")
            except Exception as e:
                logger.warning(f"Redis not available, continuing without cache: {e}")
                ohlcv_cache = None
            
            # オプション: MT5（リアルタイム）
            try:
                mt5_connection = self.get_mt5_connection()
                from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
                mt5_collector = MT5DataCollector(
                    connection=mt5_connection,
                    timeframe_map=self.settings.data_collector.timeframe_map
                )
                logger.info("MT5 collector available")
            except Exception as e:
                logger.warning(f"MT5 not available: {e}")
                mt5_collector = None
            
            # オプション: S3（ヒストリカル）
            try:
                from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository
                import boto3
                s3_repository = S3OhlcvDataRepository(
                    bucket_name=self.settings.s3_raw_data_bucket,
                    s3_client=boto3.client('s3', region_name=self.settings.aws_region)
                )
                logger.info("S3 repository available")
            except Exception as e:
                logger.warning(f"S3 not available: {e}")
                s3_repository = None
            
            # 必須: yfinance（フォールバック）
            try:
                from src.infrastructure.gateways.market_data.yfinance_gateway import YFinanceGateway
                yfinance_client = YFinanceGateway(cache_duration=300)
                logger.info("yfinance client available")
            except Exception as e:
                logger.error(f"yfinance not available: {e}")
                yfinance_client = None
            
            # 少なくとも1つのデータソースが必要
            if not any([ohlcv_cache, mt5_collector, s3_repository, yfinance_client]):
                raise RuntimeError(
                    "No data sources available. "
                    "At least yfinance should be accessible."
                )
            
            # プロバイダー作成
            self._ohlcv_data_provider = OhlcvDataProvider(
                ohlcv_cache=ohlcv_cache,
                mt5_data_collector=mt5_collector,
                s3_repository=s3_repository,
                yfinance_client=yfinance_client
            )
            
            logger.info(
                f"OhlcvDataProvider initialized "
                f"(cache={'✓' if ohlcv_cache else '✗'}, "
                f"mt5={'✓' if mt5_collector else '✗'}, "
                f"s3={'✓' if s3_repository else '✗'}, "
                f"yfinance={'✓' if yfinance_client else '✗'})"
            )
        
        return self._ohlcv_data_provider

    def get_mt5_price_provider(self) -> MT5PriceProvider:
        """
        MT5価格プロバイダーを取得（シングルトン）
        
        リアルタイム価格情報（Bid/Ask/スプレッド）を提供する
        
        Returns:
            MT5PriceProvider: MT5価格情報プロバイダー
        
        Usage:
            >>> container = DIContainer()
            >>> price_provider = container.get_mt5_price_provider()
            >>> price_info = price_provider.get_current_price('USDJPY')
        
        Note:
            - 命名規則: Provider suffix（データ提供の責務）
            - パターン: OhlcvDataProviderと一貫性
            - Day 3午後実装（2025-10-19）
        """
        if not self._mt5_price_provider:
            self._mt5_price_provider = MT5PriceProvider(
                connection=self.get_mt5_connection()
            )
            logger.info("MT5PriceProvider initialized")
        return self._mt5_price_provider
    
    def get_mt5_account_provider(self) -> MT5AccountProvider:
        """
        MT5口座情報プロバイダーを取得（シングルトン）
        
        口座残高、証拠金、本日損益（NYクローズ基準）を提供する
        
        Returns:
            MT5AccountProvider: MT5口座情報プロバイダー
        
        Usage:
            >>> container = DIContainer()
            >>> account_provider = container.get_mt5_account_provider()
            >>> account_info = account_provider.get_account_info()
            >>> today_pl = account_provider.calculate_today_pl()
        
        Note:
            - 命名規則: Provider suffix（データ提供の責務）
            - NYクローズ基準の損益計算を提供
            - Day 3午後実装（2025-10-19）
        """
        if not self._mt5_account_provider:
            self._mt5_account_provider = MT5AccountProvider(
                connection=self.get_mt5_connection()
            )
            logger.info("MT5AccountProvider initialized")
        return self._mt5_account_provider
    
    def get_mt5_position_provider(self) -> MT5PositionProvider:
        """
        MT5ポジション管理プロバイダーを取得（シングルトン）
        
        リアルタイムポジション情報（一覧/決済/損益計算）を提供する
        
        Returns:
            MT5PositionProvider: MT5ポジション情報プロバイダー
        
        Usage:
            >>> container = DIContainer()
            >>> position_provider = container.get_mt5_position_provider()
            >>> positions = position_provider.get_all_positions()
            >>> success, error = position_provider.close_position(12345678)
        
        Note:
            - 命名規則: Provider suffix（データ提供の責務）
            - MT5をSingle Source of Truthとする
            - DynamoDB記録は Phase 2で実装
            - Day 4実装（2025-10-19）
        """
        if not self._mt5_position_provider:
            self._mt5_position_provider = MT5PositionProvider(
                connection=self.get_mt5_connection()
            )
            logger.info("MT5PositionProvider initialized")
        return self._mt5_position_provider
    
    def get_position_repository(self) -> DynamoDBPositionRepository:
        """
        ポジションリポジトリを取得（シングルトン）
        
        Position Entity の永続化・検索を担当
        
        Returns:
            DynamoDBPositionRepository: ポジションリポジトリ
        
        Usage:
            >>> container = DIContainer()
            >>> repo = container.get_position_repository()
            >>> open_positions = repo.find_open_positions()
            >>> success = repo.save(position_entity)
        
        Note:
            - GSI1（OPEN_POSITIONS）を活用
            - 楽観的ロック対応（version管理）
            - MT5Ticket逆引き対応
            - Order ↔ Position関連付け基盤
        """
        if not self._position_repository:
            self._position_repository = DynamoDBPositionRepository(
                table_name=self.settings.dynamodb_table_name,
                dynamodb_resource=self.settings.dynamodb_resource
            )
            logger.info("DynamoDBPositionRepository initialized")
        return self._position_repository

# シングルトンインスタンス
container = DIContainer()