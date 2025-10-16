# src/application/use_cases/data_collection/collect_ohlcv_data.py
"""マーケットデータ収集ユースケース

このモジュールは、MT5から市場データを取得し、S3への長期保存と
Redisへのキャッシュを実行するユースケースを提供します。

特徴:
- MT5から最新の市場データを取得
- S3に永続化（Parquet形式、日付パーティション）
- Redisにキャッシュ（24時間保持、NYクローズ基準TTL）
- ロバストなエラーハンドリング（部分的な成功を許容）

実行タイミング:
    - NYクローズ後（夏時間: JST 06:30, 冬時間: JST 07:30）
    - cronで日次自動実行

データフロー:
    MT5 → Application層 → S3保存 → Redis保存 → 完了

使用例:
    >>> from src.application.use_cases.data_collection.collect_ohlcv_data import CollectOhlcvDataUseCase
    >>> 
    >>> use_case = CollectOhlcvDataUseCase(
    ...     mt5_data_collector=mt5_collector,
    ...     s3_repository=s3_repo,
    ...     ohlcv_cache=redis_cache,
    ...     symbols=['USDJPY', 'EURUSD'],
    ...     timeframes=['H1', 'D1'],
    ...     fetch_counts={'H1': 24, 'D1': 30, 'DEFAULT': 1000}
    ... )
    >>> 
    >>> success = use_case.execute()
"""

import logging
from typing import List, Dict

from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository
from src.infrastructure.persistence.redis.redis_ohlcv_data_repository import RedisOhlcvDataRepository

logger = logging.getLogger(__name__)


class CollectOhlcvDataUseCase:
    """
    マーケットデータ収集ユースケース
    
    MT5から市場データを取得し、S3とRedisに保存するユースケース。
    部分的な失敗（一部の通貨ペアやタイムフレームの失敗）を許容し、
    可能な限り多くのデータを収集します。
    
    責務:
        - MT5から市場データを取得
        - S3に長期保存（Parquet形式）
        - Redisにキャッシュ（24時間保持）
        - 処理統計のログ出力
    
    Attributes:
        mt5_data_collector (MT5DataCollector): MT5データ収集器
        s3_repository (S3OhlcvDataRepository): S3永続化リポジトリ
        ohlcv_cache (RedisOhlcvDataRepository): Redisキャッシュリポジトリ
        symbols (List[str]): 収集対象の通貨ペアリスト
        timeframes (List[str]): 収集対象のタイムフレームリスト
        fetch_counts (Dict[str, int]): タイムフレーム別取得件数
    
    Note:
        - Redis保存失敗は警告のみ（成功扱い）
        - 1つ以上のデータ収集に成功すればTrue
        - 全て失敗した場合のみFalse
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
        コンストラクタ
        
        Args:
            mt5_data_collector: MT5データ収集器
            s3_repository: S3リポジトリ
            ohlcv_cache: Redisキャッシュリポジトリ
            symbols: 収集対象の通貨ペアリスト（例: ['USDJPY', 'EURUSD']）
            timeframes: 収集対象のタイムフレームリスト（例: ['H1', 'D1']）
            fetch_counts: タイムフレーム別取得件数
                例: {'H1': 24, 'D1': 30, 'DEFAULT': 1000}
                DEFAULTキーは、指定されていないタイムフレームに使用
        
        Raises:
            ValueError: symbolsまたはtimeframesが空の場合
        
        Example:
            >>> use_case = CollectOhlcvDataUseCase(
            ...     mt5_data_collector=collector,
            ...     s3_repository=s3_repo,
            ...     ohlcv_cache=cache,
            ...     symbols=['USDJPY'],
            ...     timeframes=['H1'],
            ...     fetch_counts={'DEFAULT': 1000}
            ... )
        """
        if not symbols:
            raise ValueError("symbols must not be empty")
        if not timeframes:
            raise ValueError("timeframes must not be empty")
        
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
        
        全ての通貨ペア・タイムフレームの組み合わせに対して、
        MT5からデータを取得し、S3とRedisに保存します。
        個別の失敗は記録されますが、処理は継続されます。
        
        Returns:
            bool: 1つ以上のデータ収集に成功した場合True、全て失敗した場合False
        
        処理フロー:
            1. 各通貨ペア・タイムフレームの組み合わせをループ
            2. MT5からデータ取得
                - 失敗: ログ記録して次へ
                - 成功: 次のステップへ
            3. S3に保存（長期保存）
                - 失敗: エラーログ記録して次へ
                - 成功: 次のステップへ
            4. Redisに保存（キャッシュ）
                - 失敗: 警告ログのみ（S3保存成功なら成功扱い）
                - 成功: ログ記録
            5. 統計情報をログ出力
            6. Redis統計情報をログ出力
        
        Example:
            >>> use_case = CollectOhlcvDataUseCase(...)
            >>> success = use_case.execute()
            >>> if success:
            ...     print("データ収集成功")
            ... else:
            ...     print("データ収集失敗（全てのタスクが失敗）")
        
        Note:
            - 個別のエラーは継続的に処理される（ロバスト性重視）
            - Redis失敗はS3成功なら成功扱い（キャッシュはベストエフォート）
            - 処理統計は常にログ出力される
        
        Raises:
            なし: 全てのエラーは内部でハンドリングされる
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
                        timeframe=timeframe,
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
    
    # RedisOhlcvDataRepository取得
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