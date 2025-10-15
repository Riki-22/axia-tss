# src/presentation/cli/run_data_collector.py
#!/usr/bin/env python
"""Data Collector のエントリーポイント"""

import sys
import logging
from pathlib import Path
import boto3

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.settings import settings
from src.infrastructure.di.container import container
from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository
from application.use_cases.data_collection.collect_ohlcv_data import CollectOhlcvDataUseCase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """
    メインエントリーポイント
    
    実行タイミング:
        - NYクローズ後（夏時間 JST 06:30 / 冬時間 JST 07:30）
        - cronで日次実行
    
    処理内容:
        1. MT5接続
        2. データ収集（MT5 → S3 → Redis）
        3. 統計情報出力
        4. 接続クローズ
    
    cron設定例:
        # 夏時間（3月第2日曜～11月第1日曜）
        30 6 * 3-11 * /usr/bin/python3 /path/to/run_data_collector.py
        
        # 冬時間（11月第1日曜～3月第2日曜）
        30 7 * 11-2 * /usr/bin/python3 /path/to/run_data_collector.py
    """
    mt5_connected = False
    
    try:
        logger.info("=" * 60)
        logger.info("Data Collector 起動中...")
        logger.info("=" * 60)
        
        # 1. MT5接続
        logger.info("MT5接続を試行中...")
        mt5_connection = container.get_mt5_connection()
        credentials = settings.get_mt5_credentials()
        
        if not credentials:
            logger.error("MT5認証情報を取得できませんでした")
            return 1
        
        if not mt5_connection.connect():
            logger.error("MT5接続に失敗しました")
            return 1
        
        mt5_connected = True
        logger.info("MT5接続成功")
        
        # 2. データ収集器作成
        logger.info("データ収集器を初期化中...")
        mt5_data_collector = MT5DataCollector(
            connection=mt5_connection,
            timeframe_map=settings.timeframe_map
        )
        
        # 3. S3リポジトリ作成
        logger.info("S3リポジトリを初期化中...")
        s3_repository = S3OhlcvDataRepository(
            bucket_name=settings.s3_raw_data_bucket,
            s3_client=boto3.client('s3', region_name=settings.aws_region)
        )
        
        # 4. PriceCache取得
        logger.info("Redisキャッシュを初期化中...")
        ohlcv_cache = container.get_ohlcv_cache()
        
        # Redis接続確認
        if not ohlcv_cache.redis_client.ping():
            logger.error("Redis接続に失敗しました")
            return 1
        
        logger.info("Redis接続成功")
        
        # 5. ユースケース実行
        logger.info("データ収集を開始します...")
        use_case = CollectOhlcvDataUseCase(
            mt5_data_collector=mt5_data_collector,
            s3_repository=s3_repository,
            ohlcv_cache=ohlcv_cache,
            symbols=settings.data_collection_symbols,
            timeframes=settings.data_collection_timeframes,
            fetch_counts=settings.data_fetch_counts
        )
        
        success = use_case.execute()
        
        if success:
            logger.info("Data Collector 処理完了（成功）")
            return 0
        else:
            logger.error("Data Collector 処理完了（一部失敗）")
            return 1
        
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断を検知しました")
        return 130  # SIGINT exit code
        
    except Exception as e:
        logger.critical(
            f"実行中に予期しないエラーが発生しました: {e}",
            exc_info=True
        )
        return 1
        
    finally:
        # 6. MT5接続クローズ
        if mt5_connected:
            logger.info("MT5接続をクローズ中...")
            mt5_connection.disconnect()
            logger.info("MT5接続をクローズしました")


if __name__ == "__main__":
    sys.exit(main())