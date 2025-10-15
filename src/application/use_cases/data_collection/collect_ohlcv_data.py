# src/application/use_cases/data_collection/collect_ohlcv_data.py
"""マーケットデータ収集ユースケース"""

import logging
from typing import List, Dict

from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository
from src.infrastructure.persistence.redis.redis_ohlcv_data_repository import RedisOhlcvDataRepository

logger = logging.getLogger(__name__)


class CollectOhlcvDataUseCase:
    """
    マーケットデータ収集ユースケース
    
    責務:
        - MT5から市場データを取得
        - S3に長期保存（Parquet形式）
        - Redisにキャッシュ（24時間保持）
    
    実行タイミング:
        - NYクローズ後（夏時間 JST 06:30 / 冬時間 JST 07:30）
        - cronで日次実行
    
    データフロー:
        MT5 → S3保存 → Redis保存 → 完了
    """
    
    def __init__(
        self,
        mt5_data_collector: MT5DataCollector,
        s3_repository: S3OhlcvDataRepository,
        ohlcv_cache: RedisOhlcvDataRepository,
        symbols: List[str],
        timeframes: List[str],
        fetch_counts: Dict[str, int]
    ):
        """
        Args:
            mt5_data_collector: MT5データ収集器
            s3_repository: S3リポジトリ
            ohlcv_cache: Redisキャッシュリポジトリ
            symbols: 収集対象の通貨ペアリスト
            timeframes: 収集対象のタイムフレームリスト
            fetch_counts: タイムフレーム別取得件数
        """
        self.mt5_data_collector = mt5_data_collector
        self.s3_repository = s3_repository
        self.ohlcv_cache = ohlcv_cache
        self.symbols = symbols
        self.timeframes = timeframes
        self.fetch_counts = fetch_counts
        
        logger.info(
            f"CollectOhlcvDataUseCase initialized: "
            f"{len(symbols)} symbols, {len(timeframes)} timeframes"
        )
    
    def execute(self) -> bool:
        """
        マーケットデータ収集を実行
        
        Returns:
            bool: 1つ以上のデータ収集に成功した場合True
        
        処理フロー:
            1. 各通貨ペア・タイムフレームの組み合わせをループ
            2. MT5からデータ取得
            3. S3に保存（長期保存）
            4. Redisに保存（キャッシュ）
            5. 統計情報をログ出力
        """
        logger.info("=" * 60)
        logger.info("Starting market data collection...")
        logger.info("=" * 60)
        
        success_count = 0
        failure_count = 0
        total_tasks = len(self.symbols) * len(self.timeframes)
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                try:
                    logger.info(
                        f"Processing {symbol} {timeframe}..."
                    )
                    
                    # 1. MT5からデータ取得
                    fetch_count = self.fetch_counts.get(
                        timeframe, 
                        self.fetch_counts.get('DEFAULT', 1000)
                    )
                    
                    df = self.mt5_data_collector.fetch_ohlcv_data(
                        symbol=symbol,
                        timeframe_int=timeframe,
                        count=fetch_count
                    )
                    
                    if df is None or df.empty:
                        logger.warning(
                            f"No data retrieved for {symbol} {timeframe}"
                        )
                        failure_count += 1
                        continue
                    
                    logger.info(
                        f"Retrieved {len(df)} rows for {symbol} {timeframe}"
                    )
                    
                    # 2. S3保存（長期保存）
                    s3_success = self.s3_repository.save_ohlcv(
                        df, symbol, timeframe
                    )
                    
                    if not s3_success:
                        logger.error(
                            f"Failed to save {symbol} {timeframe} to S3"
                        )
                        failure_count += 1
                        continue
                    
                    logger.info(
                        f"Saved to S3: {symbol} {timeframe}"
                    )
                    
                    # 3. Redis保存（キャッシュ）
                    cache_success = self.ohlcv_cache.save_ohlcv(
                        df, symbol, timeframe
                    )
                    
                    if cache_success:
                        logger.info(
                            f"Cached to Redis: {symbol} {timeframe} "
                            f"(TTL: NYクローズまで)"
                        )
                    else:
                        logger.warning(
                            f"Failed to cache {symbol} {timeframe} to Redis "
                            f"(S3 save was successful)"
                        )
                        # Redisキャッシュ失敗は警告のみ（成功扱い）
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(
                        f"Failed to collect {symbol} {timeframe}: {e}",
                        exc_info=True
                    )
                    failure_count += 1
                    continue
        
        # 4. 統計情報ログ出力
        logger.info("=" * 60)
        logger.info("Market data collection completed")
        logger.info(f"Total tasks: {total_tasks}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failure: {failure_count}")
        logger.info(f"Success rate: {success_count/total_tasks*100:.1f}%")
        logger.info("=" * 60)
        
        # 5. Redis統計情報も出力
        try:
            cache_stats = self.ohlcv_cache.get_cache_stats()
            logger.info("Redis Cache Statistics:")
            logger.info(f"  Total keys: {cache_stats.get('total_keys', 0)}")
            logger.info(f"  Memory used: {cache_stats.get('memory_used_mb', 0):.2f} MB")
            logger.info(f"  Memory status: {cache_stats.get('memory_status', 'UNKNOWN')}")
            logger.info(f"  Symbols: {cache_stats.get('symbols', [])}")
            logger.info(f"  Timeframes: {cache_stats.get('timeframes', [])}")
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
        
        return success_count > 0


# テスト用エントリーポイント
if __name__ == "__main__":
    import sys
    from pathlib import Path
    import boto3
    
    # プロジェクトルートをパスに追加
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    from src.infrastructure.config.settings import settings
    from src.infrastructure.di.container import container
    from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
    
    # ロギング設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    )
    
    # MT5接続
    mt5_connection = container.get_mt5_connection()
    if not mt5_connection.connect():
        logger.error("Failed to connect to MT5")
        sys.exit(1)
    
    # データ収集器作成
    mt5_collector = MT5DataCollector(
        connection=mt5_connection,
        timeframe_map=settings.timeframe_map
    )
    
    # S3リポジトリ作成
    s3_repo = S3OhlcvDataRepository(
        bucket_name=settings.s3_raw_data_bucket,
        s3_client=boto3.client('s3', region_name=settings.aws_region)
    )
    
    # PriceCache取得
    ohlcv_cache = container.get_ohlcv_cache()
    
    # ユースケース実行
    use_case = CollectOhlcvDataUseCase(
        mt5_data_collector=mt5_collector,
        s3_repository=s3_repo,
        ohlcv_cache=ohlcv_cache,
        symbols=settings.data_collection_symbols,
        timeframes=settings.data_collection_timeframes,
        fetch_counts=settings.data_fetch_counts
    )
    
    success = use_case.execute()
    
    # 接続クローズ
    mt5_connection.disconnect()
    
    sys.exit(0 if success else 1)