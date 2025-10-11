# src/application/use_cases/data_collection/collect_market_data.py
import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class CollectMarketDataUseCase:
    """マーケットデータ収集ユースケース"""
    
    def __init__(
        self,
        mt5_data_collector,
        s3_repository,
        symbols: List[str],
        timeframes: List[int],
        fetch_counts: Dict[str, int]
    ):
        self.mt5_data_collector = mt5_data_collector
        self.s3_repository = s3_repository
        self.symbols = symbols
        self.timeframes = timeframes
        self.fetch_counts = fetch_counts
    
    def execute(self) -> bool:
        """データ収集を実行"""
        logger.info("マーケットデータ収集開始...")
        
        try:
            success_count = 0
            total_count = len(self.symbols) * len(self.timeframes)
            
            for symbol in self.symbols:
                for timeframe_int in self.timeframes:
                    # タイムフレーム文字列取得
                    timeframe_str = self.mt5_data_collector.timeframe_reverse_map.get(
                        timeframe_int, "UNKNOWN"
                    )
                    
                    # 取得件数決定
                    fetch_count = self.fetch_counts.get(
                        timeframe_str, 
                        self.fetch_counts.get('DEFAULT', 1000)
                    )
                    
                    # データ取得
                    df = self.mt5_data_collector.fetch_ohlcv_data(
                        symbol, timeframe_int, fetch_count
                    )
                    
                    # S3保存
                    if df is not None and not df.empty:
                        if self.s3_repository.save_ohlcv_data(df, symbol, timeframe_str):
                            success_count += 1
                    
                    # API負荷軽減
                    time.sleep(2)
                
                # シンボル間の待機
                time.sleep(5)
            
            logger.info(f"データ収集完了: {success_count}/{total_count} 成功")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"データ収集中にエラー: {e}", exc_info=True)
            return False