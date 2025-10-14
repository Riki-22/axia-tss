# src/infrastructure/config/data_collector_config.py
"""Data Collector関連設定"""

import os
import json
import logging
from typing import List, Dict, Any
from .base_config import BaseConfig

logger = logging.getLogger(__name__)

class DataCollectorConfig(BaseConfig):
    """Data Collector関連設定クラス"""
    
    def __init__(self, timeframe_map: Dict[str, int]):
        super().__init__()
        
        self.timeframe_map = timeframe_map
        
        # シンボル設定
        symbols_str = os.getenv('DATA_COLLECTION_SYMBOLS', 'USDJPY,EURUSD')
        self.data_collection_symbols = [
            symbol.strip().upper() 
            for symbol in symbols_str.split(',') 
            if symbol.strip()
        ]
        
        # タイムフレーム設定
        timeframes_str = os.getenv('DATA_COLLECTION_TIMEFRAMES', 'H1,D1')
        self.data_collection_timeframes = [
            self.timeframe_map[tf.strip().upper()]
            for tf in timeframes_str.split(',')
            if tf.strip().upper() in self.timeframe_map
        ]
        
        # 取得件数設定
        fetch_counts_json = os.getenv('DATA_FETCH_COUNTS_JSON')
        if fetch_counts_json:
            try:
                self.data_fetch_counts = json.loads(fetch_counts_json)
            except json.JSONDecodeError:
                logger.error("DATA_FETCH_COUNTS_JSON が無効なJSON形式です")
                self.data_fetch_counts = {"DEFAULT": 1000}
        else:
            self.data_fetch_counts = {"DEFAULT": 1000}
        
        logger.info(f"データ収集設定: {len(self.data_collection_symbols)} symbols, "
                   f"{len(self.data_collection_timeframes)} timeframes")