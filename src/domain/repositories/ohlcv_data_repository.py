# src/domain/repositories/ohlcv_data_repository.py
"""マーケットデータリポジトリのインターフェース定義"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import pytz
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

    # ========================================
    # メタデータ付き保存
    # ========================================
    
    def save_ohlcv_with_metadata(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> bool:
        """
        OHLCVデータをメタデータ付きでRedisに保存
        
        保存内容:
        - {key}:data - シリアライズされたDataFrame
        - {key}:meta - メタデータ（更新時刻、行数、通貨ペア、時間足）
        
        Args:
            df: OHLCVデータ
            symbol: 通貨ペア
            timeframe: 時間足
        
        Returns:
            bool: 保存成功時True
        
        Example:
            >>> repo = RedisOhlcvDataRepository()
            >>> df = pd.DataFrame(...)
            >>> repo.save_ohlcv_with_metadata(df, 'USDJPY', 'H1')
            True
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            
            # データシリアライズ（既存メソッド使用）
            data = self._serialize_dataframe(df)
            
            # メタデータ作成
            metadata = {
                'updated_at': datetime.now(pytz.UTC).isoformat(),
                'row_count': len(df),
                'symbol': symbol,
                'timeframe': timeframe,
                'start_time': df.index[0].isoformat() if len(df) > 0 else None,
                'end_time': df.index[-1].isoformat() if len(df) > 0 else None
            }
            
            # TTL計算（既存メソッド使用）
            ttl = self._calculate_ttl_until_ny_close()
            
            # パイプラインで一括保存
            pipeline = self.redis_client.pipeline()
            pipeline.set(f"{key}:data", data)
            pipeline.set(f"{key}:meta", json.dumps(metadata))
            pipeline.expire(f"{key}:data", ttl)
            pipeline.expire(f"{key}:meta", ttl)
            results = pipeline.execute()
            
            if all(results):
                logger.info(
                    f"Saved to Redis with metadata: {symbol} {timeframe} "
                    f"({len(df)} rows, TTL={ttl}s)"
                )
                return True
            else:
                logger.error(f"Failed to save to Redis: {symbol} {timeframe}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving to Redis with metadata: {e}", exc_info=True)
            return False
    
    # ========================================
    # メタデータ付き読み込み
    # ========================================
    
    def load_ohlcv_with_metadata(
        self,
        symbol: str,
        timeframe: str,
        days: int = 1
    ) -> tuple:
        """
        OHLCVデータとメタデータを取得
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
            days: 取得日数（期間フィルタリング用）
        
        Returns:
            tuple: (DataFrame, metadata_dict) or (None, None)
                DataFrame: OHLCVデータ
                metadata_dict: {
                    'updated_at': datetime,
                    'row_count': int,
                    'symbol': str,
                    'timeframe': str,
                    'start_time': datetime,
                    'end_time': datetime
                }
        
        Example:
            >>> repo = RedisOhlcvDataRepository()
            >>> df, meta = repo.load_ohlcv_with_metadata('USDJPY', 'H1')
            >>> if df is not None:
            ...     print(f"Updated: {meta['updated_at']}")
            ...     print(f"Rows: {meta['row_count']}")
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            
            # データとメタデータを取得
            data = self.redis_client.get(f"{key}:data")
            meta_json = self.redis_client.get(f"{key}:meta")
            
            if not data or not meta_json:
                logger.debug(f"Cache miss: {symbol} {timeframe}")
                return None, None
            
            # デシリアライズ
            df = self._deserialize_dataframe(data)
            metadata = json.loads(meta_json)
            
            # datetime型に変換
            metadata['updated_at'] = datetime.fromisoformat(
                metadata['updated_at']
            )
            if metadata.get('start_time'):
                metadata['start_time'] = datetime.fromisoformat(
                    metadata['start_time']
                )
            if metadata.get('end_time'):
                metadata['end_time'] = datetime.fromisoformat(
                    metadata['end_time']
                )
            
            # 期間フィルタリング
            if days and days > 0:
                cutoff = datetime.now(pytz.UTC) - timedelta(days=days)
                df = df[df.index >= cutoff]
            
            # データ鮮度計算
            age = datetime.now(pytz.UTC) - metadata['updated_at']
            
            logger.info(
                f"Cache hit: {symbol} {timeframe} "
                f"({len(df)} rows, age={age.total_seconds():.0f}s)"
            )
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"Error loading from Redis: {e}", exc_info=True)
            return None, None
    
    # ========================================
    # データエイジ取得
    # ========================================
    
    def get_data_age(
        self,
        symbol: str,
        timeframe: str
    ) -> timedelta | None:
        """
        キャッシュされたデータエイジを取得
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
        
        Returns:
            timedelta: データのエイジ（現在時刻 - 更新時刻）
            None: データが存在しない場合
        
        Example:
            >>> repo = RedisOhlcvDataRepository()
            >>> age = repo.get_data_age('USDJPY', 'H1')
            >>> if age and age < timedelta(hours=1):
            ...     print("データは新鮮です")
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}:meta"
            meta_json = self.redis_client.get(key)
            
            if not meta_json:
                return None
            
            metadata = json.loads(meta_json)
            updated_at = datetime.fromisoformat(metadata['updated_at'])
            
            age = datetime.now(pytz.UTC) - updated_at
            return age
            
        except Exception as e:
            logger.error(f"Error getting data age: {e}", exc_info=True)
            return None
    
    # ========================================
    # データ鮮度チェック
    # ========================================
    
    def is_fresh(
        self,
        symbol: str,
        timeframe: str,
        max_age: timedelta
    ) -> bool:
        """
        データが十分新鮮かチェック
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
            max_age: 許容される最大鮮度
        
        Returns:
            bool: データが新鮮な場合True
        
        Example:
            >>> repo = RedisOhlcvDataRepository()
            >>> if repo.is_fresh('USDJPY', 'H1', timedelta(hours=2)):
            ...     print("データは2時間以内で新鮮です")
        """
        age = self.get_data_age(symbol, timeframe)
        
        if age is None:
            return False
        
        return age < max_age