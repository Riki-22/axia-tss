# src/infrastructure/persistence/redis/redis_ohlcv_data_repository.py
"""OHLCVデータ専用キャッシュ（NYクローズ基準TTL）"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import pandas as pd
import numpy as np
import msgpack
import pytz

from src.domain.repositories.ohlcv_data_repository import IOhlcvDataRepository
from .redis_client import RedisClient

logger = logging.getLogger(__name__)


class RedisOhlcvDataRepository(IOhlcvDataRepository):
    """
    OHLCVデータ専用キャッシュクラス
    
    特徴:
    - NYクローズ基準のTTL管理（FX市場サイクルと整合）
    - MessagePackによる高速シリアライズ
    - 24時間データ保持（週末は約40時間）
    - メモリ使用量監視
    
    キーフォーマット:
        データ: ohlcv:{symbol}:{timeframe}
        メタデータ: ohlcv:{symbol}:{timeframe}:meta
    """
    
    # NYクローズ時刻（日本時間）
    NY_CLOSE_HOUR_EDT = 6  # 夏時間: JST 06:00
    NY_CLOSE_HOUR_EST = 7  # 冬時間: JST 07:00
    
    # メモリ監視閾値
    MEMORY_WARNING_MB = 40
    MEMORY_CRITICAL_MB = 50
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Args:
            redis_client: RedisClientインスタンス（Noneの場合は自動取得）
        """
        self.redis_client = redis_client or RedisClient.get_instance()
        self._cache_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("RedisOhlcvDataRepository initialized")
    
    # ========================================
    # キー管理
    # ========================================
    
    def _generate_key(self, symbol: str, timeframe: str) -> str:
        """
        キーを生成
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            str: Redis キー
        """
        return f"ohlcv:{symbol.upper()}:{timeframe.upper()}"
    
    def _generate_meta_key(self, symbol: str, timeframe: str) -> str:
        """
        メタデータキーを生成
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            str: メタデータキー
        """
        return f"{self._generate_key(symbol, timeframe)}:meta"
    
    # ========================================
    # TTL管理（NYクローズ基準）
    # ========================================
    
    def _is_dst(self, dt: datetime) -> bool:
        """
        米国夏時間（DST）判定
        
        Args:
            dt: 判定する日時
        
        Returns:
            bool: 夏時間の場合True
        
        Note:
            米国夏時間: 3月第2日曜 - 11月第1日曜
        """
        # 米国東部時間帯
        eastern = pytz.timezone('US/Eastern')
        dt_eastern = dt.astimezone(eastern)
        return bool(dt_eastern.dst())
    
    def _get_next_ny_close(self, current_time: datetime) -> datetime:
        """
        次のNYクローズ時刻を取得
        
        Args:
            current_time: 現在時刻（UTC）
        
        Returns:
            datetime: 次のNYクローズ時刻（JST）
        """
        # JST変換
        jst = pytz.timezone('Asia/Tokyo')
        current_jst = current_time.astimezone(jst)
        
        # 夏時間判定
        is_dst = self._is_dst(current_time)
        ny_close_hour = self.NY_CLOSE_HOUR_EDT if is_dst else self.NY_CLOSE_HOUR_EST
        
        # 次のNYクローズ時刻を計算
        next_close = current_jst.replace(
            hour=ny_close_hour,
            minute=0,
            second=0,
            microsecond=0
        )
        
        # 既に過ぎている場合は翌日
        if current_jst >= next_close:
            next_close += timedelta(days=1)
        
        # 週末処理
        weekday = next_close.weekday()
        if weekday == 5:  # 土曜 → 月曜まで
            next_close += timedelta(days=2)
        elif weekday == 6:  # 日曜 → 月曜まで
            next_close += timedelta(days=1)
        
        return next_close
    
    def _calculate_ttl_until_ny_close(self, current_time: Optional[datetime] = None) -> int:
        """
        次のNYクローズまでのTTLを計算
        
        Args:
            current_time: 現在時刻（UTC）。Noneの場合は現在時刻を使用
        
        Returns:
            int: TTL（秒）。最低3600秒（1時間）
        
        Examples:
            - 火曜 10:00 JST → 水曜 06:00 JST = 20時間
            - 金曜 20:00 JST → 土曜 06:00 JST = 10時間
            - 土曜 10:00 JST → 月曜 06:00 JST = 44時間（週末）
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
        
        next_close = self._get_next_ny_close(current_time)
        
        # TTL秒数を計算
        ttl_seconds = int((next_close - current_time).total_seconds())
        
        # 最低1時間は保持
        return max(ttl_seconds, 3600)
    
    # ========================================
    # シリアライズ（MessagePack）
    # ========================================
    
    def _serialize_dataframe(self, df: pd.DataFrame) -> bytes:
        """
        DataFrameをシリアライズ（msgpack形式）
        
        pandas Timestamp を msgpack でシリアライズできないため、
        ISO形式の文字列に変換してからシリアライズします。
        
        Args:
            df: シリアライズするDataFrame
        
        Returns:
            bytes: msgpackバイナリデータ
        
        処理フロー:
            1. DataFrameをコピー（元データを変更しない）
            2. インデックス情報を保存
            3. インデックスをカラムに変換
            4. 全datetime列をISO文字列に変換
            5. to_dict('records') で辞書に変換
            6. msgpack でシリアライズ
        
        Note:
            - タイムゾーン情報も保持される
            - インデックス名も保存される
        
        Raises:
            TypeError: シリアライズ失敗時
        """
        try:
            # DataFrameをコピー
            df_copy = df.copy()
            
            # インデックス情報を保存
            index_name = df_copy.index.name
            is_datetime_index = isinstance(df_copy.index, pd.DatetimeIndex)
            
            # インデックスをカラムに変換
            if isinstance(df_copy.index, pd.DatetimeIndex):
                df_copy = df_copy.reset_index()
            
            # 全datetime型カラムを文字列に変換
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].apply(
                        lambda x: x.isoformat() if pd.notna(x) else None
                    )
            
            # DataFrameを辞書に変換（records形式）
            data_dict = {
                'columns': df_copy.columns.tolist(),
                'data': df_copy.to_dict('records'),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'index_name': index_name,  # インデックス名を保存
                'is_datetime_index': is_datetime_index  # インデックス型を保存
            }
            
            # msgpackでシリアライズ
            serialized = msgpack.packb(data_dict, use_bin_type=True)
            
            logger.debug(
                f"Serialized DataFrame: {len(df)} rows, "
                f"{len(serialized)} bytes"
            )
            
            return serialized
            
        except Exception as e:
            logger.error(f"DataFrame serialization failed: {e}", exc_info=True)
            raise

    def _deserialize_dataframe(self, data: bytes) -> pd.DataFrame:
        """
        バイナリデータをDataFrameにデシリアライズ
        
        msgpackでシリアライズされたデータをDataFrameに復元します。
        ISO文字列として保存された timestamp_utc を datetime に変換します。
        
        Args:
            data: msgpackバイナリデータ
        
        Returns:
            pd.DataFrame: 復元されたDataFrame
        
        処理フロー:
            1. msgpack でデシリアライズ
            2. DataFrameに変換
            3. datetime型カラムを復元
            4. データ型を復元
            5. インデックスを復元
        
        Note:
            - タイムゾーン情報（UTC）も復元される
            - カラムの順序も保持される
            - インデックス情報も復元される
        
        Raises:
            ValueError: デシリアライズ失敗時
        """
        try:
            # msgpackでデシリアライズ
            data_dict = msgpack.unpackb(data, raw=False)
            
            # DataFrameに変換
            df = pd.DataFrame(data_dict['data'])
            
            # カラム順序を保持
            if 'columns' in data_dict:
                df = df[data_dict['columns']]
            
            # datetime型カラムを復元
            if 'dtypes' in data_dict:
                for col, dtype_str in data_dict['dtypes'].items():
                    if col not in df.columns:
                        continue
                    
                    # datetime型の復元
                    if 'datetime' in dtype_str:
                        df[col] = pd.to_datetime(df[col], utc=True)
                    # 数値型の復元
                    elif dtype_str.startswith('int'):
                        df[col] = df[col].astype('int64')
                    elif dtype_str.startswith('float'):
                        df[col] = df[col].astype('float64')
            
            # インデックスを復元
            is_datetime_index = data_dict.get('is_datetime_index', False)
            index_name = data_dict.get('index_name')
            
            if is_datetime_index and index_name in df.columns:
                # DatetimeIndexとして復元
                df = df.set_index(index_name)
                # インデックスをdatetime型に変換（念のため）
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, utc=True)
            
            logger.debug(
                f"Deserialized DataFrame: {len(df)} rows"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"DataFrame deserialization failed: {e}", exc_info=True)
            raise ValueError(f"Failed to deserialize DataFrame: {e}")
    
    # ========================================
    # IOhlcvDataRepository 実装
    # ========================================
    
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> bool:
        """
        OHLCVデータを保存（NYクローズ基準のTTL）
        
        Args:
            df: OHLCV DataFrame
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            bool: 保存成功時True
        """
        try:
            # データキー
            key = self._generate_key(symbol, timeframe)
            meta_key = self._generate_meta_key(symbol, timeframe)
            
            # シリアライズ
            serialized_data = self._serialize_dataframe(df)
            
            # TTL計算
            ttl = self._calculate_ttl_until_ny_close()
            
            # インデックスから開始・終了日時を取得
            if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
                data_start = df.index[0].isoformat()
                data_end = df.index[-1].isoformat()
            else:
                data_start = None
                data_end = None
            
            # メタデータ作成
            metadata = {
                'symbol': symbol,
                'timeframe': timeframe,
                'cached_at': datetime.now(pytz.UTC).isoformat(),
                'data_start': data_start,
                'data_end': data_end,
                'row_count': len(df),
                'ttl_expires_at': (datetime.now(pytz.UTC) + timedelta(seconds=ttl)).isoformat()
            }
            
            # Redis保存（データ + メタデータ）
            success = self.redis_client.set(key, serialized_data, ex=ttl)
            if success:
                self.redis_client.set(
                    meta_key,
                    json.dumps(metadata).encode('utf-8'),
                    ex=ttl
                )
                logger.info(
                    f"Cached OHLCV: {symbol} {timeframe} "
                    f"({len(df)} rows, TTL: {ttl}s)"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to save OHLCV to cache: {e}", exc_info=True)
            return False
    
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        OHLCVデータを読み込み
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 取得日数
        
        Returns:
            Optional[pd.DataFrame]: OHLCVデータ（存在しない場合はNone）
        """
        self._cache_stats['total_requests'] += 1
        
        try:
            key = self._generate_key(symbol, timeframe)
            
            # データ取得
            data = self.redis_client.get(key)
            if data is None:
                self._cache_stats['cache_misses'] += 1
                logger.debug(f"Cache miss: {symbol} {timeframe}")
                return None
            
            self._cache_stats['cache_hits'] += 1
            
            # デシリアライズ
            df = self._deserialize_dataframe(data)
            
            # インデックスがDatetimeIndexであることを確認
            if not isinstance(df.index, pd.DatetimeIndex):
                logger.warning(
                    f"Index is not DatetimeIndex for {symbol} {timeframe}, "
                    f"attempting to convert..."
                )
                # timestamp_utc カラムをインデックスに設定
                if 'timestamp_utc' in df.columns:
                    df = df.set_index('timestamp_utc')
                    df.index = pd.to_datetime(df.index, utc=True)
                else:
                    logger.error(f"Cannot find timestamp_utc column in {symbol} {timeframe}")
                    return None
            
            # 期間フィルタリング
            if start_date is not None:
                df = df[df.index >= start_date]
            if end_date is not None:
                df = df[df.index <= end_date]
            if days is not None and end_date is None:
                cutoff = datetime.now(pytz.UTC) - timedelta(days=days)
                df = df[df.index >= cutoff]
            
            logger.debug(f"Cache hit: {symbol} {timeframe} ({len(df)} rows)")
            return df if len(df) > 0 else None
            
        except Exception as e:
            logger.error(f"Failed to load OHLCV from cache: {e}", exc_info=True)
            self._cache_stats['cache_misses'] += 1
            return None
    
    def exists(
        self,
        symbol: str,
        timeframe: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        データの存在確認
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
            date: 確認する日時（未使用）
        
        Returns:
            bool: データが存在する場合True
        """
        key = self._generate_key(symbol, timeframe)
        return self.redis_client.exists(key) > 0
    
    def get_available_range(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        利用可能なデータの期間を取得
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            Optional[Tuple[datetime, datetime]]: (開始日時, 終了日時)
        """
        try:
            meta_key = self._generate_meta_key(symbol, timeframe)
            meta_data = self.redis_client.get(meta_key)
            
            if meta_data is None:
                return None
            
            metadata = json.loads(meta_data.decode('utf-8'))
            start = datetime.fromisoformat(metadata['data_start'])
            end = datetime.fromisoformat(metadata['data_end'])
            
            return (start, end)
            
        except Exception as e:
            logger.error(f"Failed to get available range: {e}")
            return None
    
    # ========================================
    # ユーティリティメソッド
    # ========================================
    
    def delete(self, symbol: str, timeframe: str) -> bool:
        """
        キャッシュを削除
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            bool: 削除成功時True
        """
        key = self._generate_key(symbol, timeframe)
        meta_key = self._generate_meta_key(symbol, timeframe)
        
        deleted = self.redis_client.delete(key, meta_key)
        if deleted > 0:
            logger.info(f"Deleted cache: {symbol} {timeframe}")
        
        return deleted > 0
    
    def clear_symbol(self, symbol: str) -> int:
        """
        特定通貨ペアの全タイムフレームを削除
        
        Args:
            symbol: 通貨ペアシンボル
        
        Returns:
            int: 削除されたキーの数
        """
        pattern = f"ohlcv:{symbol.upper()}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            deleted = self.redis_client.delete(*keys)
            logger.info(f"Cleared {deleted} cache entries for {symbol}")
            return deleted
        
        return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        メモリ使用量を取得
        
        Returns:
            Dict: メモリ情報
        """
        try:
            info = self.redis_client.info('memory')
            used_memory_mb = info.get('used_memory', 0) / (1024 * 1024)
            
            return {
                'used_memory_mb': round(used_memory_mb, 2),
                'warning_threshold_mb': self.MEMORY_WARNING_MB,
                'critical_threshold_mb': self.MEMORY_CRITICAL_MB,
                'status': self._get_memory_status(used_memory_mb)
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {}
    
    def _get_memory_status(self, used_mb: float) -> str:
        """メモリステータスを判定"""
        if used_mb >= self.MEMORY_CRITICAL_MB:
            return 'CRITICAL'
        elif used_mb >= self.MEMORY_WARNING_MB:
            return 'WARNING'
        return 'OK'
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        キャッシュ統計情報を取得
        
        Returns:
            Dict: 統計情報
        """
        try:
            keys = self.redis_client.keys("ohlcv:*")
            # メタデータキーを除外
            data_keys = [k for k in keys if not k.endswith(':meta')]
            
            # シンボルとタイムフレームを集計
            symbols = set()
            timeframes = set()
            for key in data_keys:
                parts = key.split(':')
                if len(parts) >= 3:
                    symbols.add(parts[1])
                    timeframes.add(parts[2])
            
            # ヒット率計算
            total_requests = self._cache_stats['total_requests']
            cache_hits = self._cache_stats['cache_hits']
            hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0
            
            memory_info = self.get_memory_usage()
            
            return {
                'total_keys': len(data_keys),
                'symbols': sorted(list(symbols)),
                'timeframes': sorted(list(timeframes)),
                'memory_used_mb': memory_info.get('used_memory_mb', 0),
                'memory_status': memory_info.get('status', 'UNKNOWN'),
                'cache_hit_rate': round(hit_rate, 3),
                'total_requests': total_requests,
                'cache_hits': cache_hits,
                'cache_misses': self._cache_stats['cache_misses']
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}