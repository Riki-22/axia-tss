# src/infrastructure/gateways/brokers/mt5/mt5_data_collector.py
import logging
import time
import pandas as pd
import MetaTrader5 as mt5
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class MT5DataCollector:
    """MT5からのデータ収集クラス"""
    
    def __init__(self, connection: 'MT5Connection', timeframe_map: Dict[str, int]):
        self.connection = connection
        self.timeframe_map = timeframe_map
        self.timeframe_reverse_map = {v: k for k, v in timeframe_map.items()}
    
    def fetch_ohlcv_data(self, symbol: str, timeframe_int: int, count: int) -> Optional[pd.DataFrame]:
        """
        指定されたシンボルとタイムフレームのOHLCVデータを取得
        既存のfetch_ohlcv_data関数のロジックを保持
        """
        timeframe_str = self.timeframe_reverse_map.get(timeframe_int, "UNKNOWN")
        logger.info(f"MT5から {symbol} ({timeframe_str}) のOHLCVデータを {count} 件取得します。")
        
        try:
            # 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # シンボル確認
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.warning(f"シンボル {symbol} はMT5で見つかりません。スキップします。")
                return None
            
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logger.warning(f"シンボル {symbol} を選択できませんでした。スキップします。")
                    return None
                time.sleep(1)
            
            # データ取得
            rates = mt5.copy_rates_from_pos(symbol, timeframe_int, 0, count)
            if rates is None or len(rates) == 0:
                logger.warning(f"{symbol} ({timeframe_str}) のOHLCVデータを取得できませんでした。")
                return None
            
            # standard_ohlcv_formatへの変換
            df = pd.DataFrame(rates)
            df['timestamp_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            golden_schema_cols = ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
            df_golden = df[golden_schema_cols].copy()
            
            df_golden = df_golden.astype({
                'open': 'float64',
                'high': 'float64',
                'low': 'float64',
                'close': 'float64',
                'volume': 'int64'
            })
            
            logger.info(f"{symbol} ({timeframe_str}) のOHLCVデータ {len(df_golden)} 件を取得しました。")
            return df_golden
            
        except Exception as e:
            logger.error(f"{symbol} ({timeframe_str}) のOHLCVデータ取得中にエラー: {e}", exc_info=True)
            return None