# src/infrastructure/gateways/brokers/mt5/mt5_data_collector.py
"""MT5データ収集器

このモジュールは、MetaTrader 5プラットフォームからOHLCVデータを取得する
データ収集器を提供します。

特徴:
- タイムフレーム文字列（"H1", "D1"等）をMT5内部のint値に自動変換
- シンボルの可視性確認と自動選択
- 接続状態の自動確認
- standard_ohlcv_format への自動変換

依存関係:
    - MetaTrader5: MT5 Pythonライブラリ
    - MT5Connection: MT5接続管理クラス

使用例:
    >>> from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
    >>> 
    >>> collector = MT5DataCollector(
    ...     connection=mt5_connection,
    ...     timeframe_map={'H1': 16385, 'D1': 16408}
    ... )
    >>> 
    >>> # データ取得（文字列で指定）
    >>> df = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)
"""

import logging
import time
import pandas as pd
import MetaTrader5 as mt5
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class MT5DataCollector:
    """
    MT5データ収集クラス
    
    MetaTrader 5プラットフォームから市場データ（OHLCV）を取得し、
    標準フォーマットに変換するクラス。
    
    Application層からは文字列のタイムフレーム（"H1", "D1"等）を受け取り、
    内部でMT5固有のint値に変換します。これにより、上位層をMT5の
    技術的詳細から分離します。
    
    Attributes:
        connection (MT5Connection): MT5接続管理インスタンス
        timeframe_map (Dict[str, int]): タイムフレーム文字列→int値マッピング
            例: {'H1': 16385, 'D1': 16408}
        timeframe_reverse_map (Dict[int, str]): 逆マッピング（ログ用）
    
    Note:
        - クリーンアーキテクチャに準拠（Infrastructure層）
        - Application層はMT5のint値を意識不要
        - エラーはログ記録してNoneを返す（上位層で判断）
    """
    
    def __init__(self, connection: 'MT5Connection', timeframe_map: Dict[str, int]):
        """
        コンストラクタ
        
        Args:
            connection: MT5接続管理インスタンス
            timeframe_map: タイムフレーム文字列→int値マッピング
                例: {'M1': 1, 'M5': 5, 'H1': 16385, 'D1': 16408}
        
        Raises:
            ValueError: timeframe_mapが空の場合
        
        Example:
            >>> from src.infrastructure.config.settings import settings
            >>> collector = MT5DataCollector(
            ...     connection=mt5_connection,
            ...     timeframe_map=settings.timeframe_map
            ... )
        """
        if not timeframe_map:
            raise ValueError("timeframe_map must not be empty")
        
        self.connection = connection
        self.timeframe_map = timeframe_map
        self.timeframe_reverse_map = {v: k for k, v in timeframe_map.items()}
        
        logger.info(
            f"MT5DataCollector initialized with {len(timeframe_map)} timeframes"
        )
    
    def fetch_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        count: int
    ) -> Optional[pd.DataFrame]:
        """
        指定されたシンボルとタイムフレームのOHLCVデータを取得
        
        MT5からローソク足データを取得し、標準OHLCV形式に変換します。
        タイムフレームは文字列（"H1", "D1"等）で受け取り、内部で
        MT5固有のint値に変換します。
        
        Args:
            symbol: 通貨ペアシンボル（例: "USDJPY", "EURUSD"）
            timeframe: タイムフレーム文字列（例: "H1", "M15", "D1"）
                対応する値は timeframe_map で定義
            count: 取得するローソク足の本数（現在から過去へ）
        
        Returns:
            pd.DataFrame: 標準OHLCV形式のDataFrame
                カラム: ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
                データ型:
                    - timestamp_utc: datetime64[ns, UTC]
                    - open, high, low, close: float64
                    - volume: int64
            None: データ取得失敗時
        
        処理フロー:
            1. タイムフレーム文字列 → int値に変換
            2. MT5接続状態確認
            3. シンボル存在確認
            4. シンボル可視性確認（必要に応じて選択）
            5. MT5 APIでデータ取得
            6. standard_ohlcv_format に変換
        
        Example:
            >>> # 24時間分のH1データを取得
            >>> df = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)
            >>> if df is not None:
            ...     print(f"取得: {len(df)}本")
            
            >>> # 30日分のD1データを取得
            >>> df = collector.fetch_ohlcv_data('EURUSD', 'D1', 30)
        
        Note:
            - エラー時はログ記録してNoneを返す
            - シンボルが非表示の場合、自動的に選択を試みる
            - volume は tick_volume から変換される
        
        Raises:
            なし: 全てのエラーはログ記録してNoneを返す
        """
        # 1. タイムフレーム文字列 → int値に変換
        timeframe_int = self.timeframe_map.get(timeframe)
        if timeframe_int is None:
            logger.error(
                f"Unknown timeframe: {timeframe}. "
                f"Available: {list(self.timeframe_map.keys())}"
            )
            return None
        
        logger.info(
            f"MT5から {symbol} ({timeframe}) のOHLCVデータを {count} 件取得します。"
        )
        
        try:
            # 2. 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # 3. シンボル確認
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.warning(
                    f"シンボル {symbol} はMT5で見つかりません。スキップします。"
                )
                return None
            
            # 4. シンボル可視性確認
            if not symbol_info.visible:
                logger.debug(
                    f"シンボル {symbol} が非表示のため、選択を試みます..."
                )
                if not mt5.symbol_select(symbol, True):
                    logger.warning(
                        f"シンボル {symbol} を選択できませんでした。スキップします。"
                    )
                    return None
                # 選択後の待機（MT5側の処理完了を待つ）
                time.sleep(1)
            
            # 5. データ取得（MT5 API呼び出し）
            rates = mt5.copy_rates_from_pos(symbol, timeframe_int, 0, count)
            if rates is None or len(rates) == 0:
                logger.warning(
                    f"{symbol} ({timeframe}) のOHLCVデータを取得できませんでした。"
                )
                return None
            
            # 6. standard_ohlcv_formatへの変換
            df = pd.DataFrame(rates)
            
            # タイムスタンプをUTC datetimeに変換
            df['timestamp_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
            
            # tick_volume → volume に変換
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            # 標準スキーマのカラムのみ選択
            golden_schema_cols = [
                'timestamp_utc', 'open', 'high', 'low', 'close', 'volume'
            ]
            df_golden = df[golden_schema_cols].copy()
            
            # データ型を明示的に設定
            df_golden = df_golden.astype({
                'open': 'float64',
                'high': 'float64',
                'low': 'float64',
                'close': 'float64',
                'volume': 'int64'
            })
            
            logger.info(
                f"{symbol} ({timeframe}) のOHLCVデータ {len(df_golden)} 件を取得しました。"
            )
            
            return df_golden
            
        except Exception as e:
            logger.error(
                f"{symbol} ({timeframe}) のOHLCVデータ取得中にエラー: {e}",
                exc_info=True
            )
            return None