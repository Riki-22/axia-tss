# src/presentation/cli/run_data_collector.py
#!/usr/bin/env python
"""Data Collector のエントリーポイント"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.settings import settings
from src.infrastructure.di.container import container
from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.persistence.s3.market_data_repository import S3MarketDataRepository
from src.application.use_cases.data_collection.collect_market_data import CollectMarketDataUseCase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """メインエントリーポイント"""
    mt5_connected = False
    
    try:
        logger.info("=" * 60)
        logger.info("Data Collector 起動中...")
        logger.info("=" * 60)
        
        # MT5接続
        mt5_connection = container.get_mt5_connection()
        credentials = settings.get_mt5_credentials()
        
        if not credentials:
            logger.error("MT5認証情報を取得できませんでした")
            return 1
        
        if not mt5_connection.connect():
            logger.error("MT5接続に失敗しました")
            return 1
        
        mt5_connected = True
        
        # データ収集器作成
        mt5_data_collector = MT5DataCollector(
            connection=mt5_connection,
            timeframe_map=settings.timeframe_map
        )
        
        # S3リポジトリ作成
        s3_repository = S3MarketDataRepository(
            bucket_name=settings.s3_raw_data_bucket,
            s3_client=settings.s3_client_dc
        )
        
        # ユースケース実行
        use_case = CollectMarketDataUseCase(
            mt5_data_collector=mt5_data_collector,
            s3_repository=s3_repository,
            symbols=settings.data_collection_symbols,
            timeframes=settings.data_collection_timeframes,
            fetch_counts=settings.data_fetch_counts
        )
        
        success = use_case.execute()
        
        logger.info("Data Collector 処理完了")
        return 0 if success else 1
        
    except Exception as e:
        logger.critical(f"実行中にエラー: {e}", exc_info=True)
        return 1
    finally:
        if mt5_connected:
            mt5_connection.disconnect()

if __name__ == "__main__":
    sys.exit(main())