# src/infrastructure/config/data_collector_config.py
"""Data Collector関連設定

このモジュールは、データ収集に関連する設定を提供します。

設定項目:
    - データ収集対象の通貨ペア
    - データ収集対象のタイムフレーム（文字列）
    - タイムフレーム別の取得件数

環境変数:
    DATA_COLLECTION_SYMBOLS: カンマ区切りの通貨ペアリスト
        例: "USDJPY,EURUSD,GBPJPY"
    DATA_COLLECTION_TIMEFRAMES: カンマ区切りのタイムフレームリスト
        例: "H1,D1"
    DATA_FETCH_COUNTS_JSON: タイムフレーム別取得件数（JSON形式）
        例: '{"H1": 24, "D1": 30, "DEFAULT": 1000}'

使用例:
    >>> from src.infrastructure.config.data_collector_config import DataCollectorConfig
    >>> 
    >>> config = DataCollectorConfig(timeframe_map={'H1': 16385, 'D1': 16408})
    >>> print(config.data_collection_symbols)  # ['USDJPY', 'EURUSD']
    >>> print(config.data_collection_timeframes)  # ['H1', 'D1']
"""

import os
import json
import logging
from typing import List, Dict
from .base_config import BaseConfig

logger = logging.getLogger(__name__)


class DataCollectorConfig(BaseConfig):
    """
    Data Collector関連設定クラス
    
    データ収集処理に必要な設定を環境変数から読み込み、
    適切な型に変換して保持します。
    
    Attributes:
        timeframe_map (Dict[str, int]): タイムフレームマッピング（MT5Configから受け取る）
        data_collection_symbols (List[str]): 収集対象の通貨ペアリスト
        data_collection_timeframes (List[str]): 収集対象のタイムフレームリスト（文字列）
        data_fetch_counts (Dict[str, int]): タイムフレーム別取得件数
    
    Note:
        - タイムフレームは文字列で管理（"H1", "D1"等）
        - MT5固有のint値は内部的に使用（MT5DataCollectorで変換）
        - 無効なタイムフレームは自動的にフィルタリングされる
    """
    
    def __init__(self, timeframe_map: Dict[str, int]):
        """
        コンストラクタ
        
        Args:
            timeframe_map: タイムフレーム文字列→int値マッピング
                MT5Configから受け取る
        
        Raises:
            ValueError: timeframe_mapが空の場合
        
        Example:
            >>> config = DataCollectorConfig(
            ...     timeframe_map={'H1': 16385, 'D1': 16408}
            ... )
        """
        super().__init__()
        
        if not timeframe_map:
            raise ValueError("timeframe_map must not be empty")
        
        self.timeframe_map = timeframe_map
        
        # 環境変数から設定を読み込み
        self._load_symbols()
        self._load_timeframes()
        self._load_fetch_counts()
        
        logger.info(
            f"データ収集設定: {len(self.data_collection_symbols)} symbols, "
            f"{len(self.data_collection_timeframes)} timeframes"
        )
    
    def _load_symbols(self):
        """
        収集対象の通貨ペアを環境変数から読み込み
        
        環境変数 DATA_COLLECTION_SYMBOLS からカンマ区切りの文字列を読み込み、
        リストに変換します。空白はトリミングされ、大文字に正規化されます。
        
        デフォルト: ['USDJPY', 'EURUSD']
        """
        symbols_str = os.getenv('DATA_COLLECTION_SYMBOLS', 'USDJPY,EURUSD')
        self.data_collection_symbols = [
            symbol.strip().upper() 
            for symbol in symbols_str.split(',') 
            if symbol.strip()
        ]
        
        if not self.data_collection_symbols:
            logger.warning(
                "No symbols configured, using defaults: USDJPY, EURUSD"
            )
            self.data_collection_symbols = ['USDJPY', 'EURUSD']
        
        logger.debug(
            f"Configured symbols: {', '.join(self.data_collection_symbols)}"
        )
    
    def _load_timeframes(self):
        """
        収集対象のタイムフレームを環境変数から読み込み
        
        環境変数 DATA_COLLECTION_TIMEFRAMES からカンマ区切りの文字列を読み込み、
        文字列リストに変換します。timeframe_mapに存在しないタイムフレームは
        自動的にフィルタリングされます。
        
        デフォルト: ['H1', 'D1']
        
        Note:
            - 以前は List[int] でしたが、文字列に統一
            - Application層での扱いが直感的になる
            - MT5DataCollectorが内部で変換を担当
        """
        timeframes_str = os.getenv('DATA_COLLECTION_TIMEFRAMES', 'H1,D1')
        
        # カンマ区切りで分割して正規化
        requested_timeframes = [
            tf.strip().upper()
            for tf in timeframes_str.split(',')
            if tf.strip()
        ]
        
        # timeframe_mapに存在するもののみフィルタリング
        self.data_collection_timeframes = [
            tf for tf in requested_timeframes
            if tf in self.timeframe_map
        ]
        
        # 無効なタイムフレームがあればログ出力
        invalid_tfs = set(requested_timeframes) - set(self.data_collection_timeframes)
        if invalid_tfs:
            logger.warning(
                f"Invalid timeframes ignored: {', '.join(invalid_tfs)}. "
                f"Valid: {', '.join(self.timeframe_map.keys())}"
            )
        
        # デフォルトフォールバック
        if not self.data_collection_timeframes:
            logger.warning(
                "No valid timeframes configured, using default: H1"
            )
            self.data_collection_timeframes = ['H1']
        
        logger.debug(
            f"Configured timeframes: {', '.join(self.data_collection_timeframes)}"
        )
    
    def _load_fetch_counts(self):
        """
        タイムフレーム別の取得件数を環境変数から読み込み
        
        環境変数 DATA_FETCH_COUNTS_JSON からJSON形式の設定を読み込みます。
        
        フォーマット:
            {"H1": 24, "D1": 30, "DEFAULT": 1000}
        
        DEFAULTキーは、指定されていないタイムフレームに使用されます。
        
        デフォルト: {"DEFAULT": 1000}
        """
        fetch_counts_json = os.getenv('DATA_FETCH_COUNTS_JSON')
        
        if fetch_counts_json:
            try:
                self.data_fetch_counts = json.loads(fetch_counts_json)
                logger.debug(
                    f"Loaded fetch counts: {self.data_fetch_counts}"
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"DATA_FETCH_COUNTS_JSON が無効なJSON形式です: {e}. "
                    f"デフォルト値を使用します。"
                )
                self.data_fetch_counts = {"DEFAULT": 1000}
        else:
            self.data_fetch_counts = {"DEFAULT": 1000}
            logger.debug("Using default fetch counts: {DEFAULT: 1000}")