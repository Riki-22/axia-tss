# src/domain/repositories/ohlcv_data_repository.py
"""マーケットデータリポジトリのインターフェース定義"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd


class IOhlcvDataRepository(ABC):
    """
    マーケットデータリポジトリの抽象基底クラス
    
    このインターフェースは市場データ（OHLCV）の保存・取得に関する
    ビジネスロジックレベルの操作を定義
    具体的なデータストア（Redis, S3, DynamoDB等）へ依存しない
    """
    
    @abstractmethod
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> bool:
        """
        OHLCVデータを保存する
        
        Args:
            df: OHLCV DataFrame
                必須カラム: ['time', 'open', 'high', 'low', 'close', 'volume']
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
        
        Returns:
            bool: 保存成功時True、失敗時False
        
        Raises:
            ValueError: DataFrameが必須カラムを含まない場合
            ConnectionError: データストアへの接続エラー
        """
        pass
    
    @abstractmethod
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        OHLCVデータを読み込む
        
        期間指定は以下の2つの方法をサポート:
        1. start_date/end_dateによる明示的な期間指定
        2. daysによる相対的な期間指定（現在からN日前）
        
        Args:
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 取得日数（end_dateからN日前まで）
        
        Returns:
            Optional[pd.DataFrame]: OHLCVデータ。データが存在しない場合はNone
                カラム: ['time', 'open', 'high', 'low', 'close', 'volume']
        
        Raises:
            ValueError: 期間指定が不正な場合
            ConnectionError: データストアへの接続エラー
        
        Note:
            - start_dateとdaysの両方を指定した場合はstart_dateが優先される
            - 指定期間にデータが存在しない場合はNoneを返す
        """
        pass
    
    @abstractmethod
    def exists(
        self,
        symbol: str,
        timeframe: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        指定されたデータが存在するか確認
        
        Args:
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
            date: 確認する日時（Noneの場合は最新データの存在確認）
        
        Returns:
            bool: データが存在する場合True
        
        Raises:
            ConnectionError: データストアへの接続エラー
        """
        pass
    
    @abstractmethod
    def get_available_range(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        利用可能なデータの期間を取得
        
        Args:
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
        
        Returns:
            Optional[Tuple[datetime, datetime]]: (開始日時, 終了日時)のタプル
                データが存在しない場合はNone
        
        Raises:
            ConnectionError: データストアへの接続エラー
        
        Note:
            - 返される日時はすべてUTC
            - データに欠損がある場合でも、最古と最新の日時を返す
        """
        pass