# src/infrastructure/persistence/s3/s3_ohlcv_data_repository.py
"""S3永続化リポジトリ - IOhlcvDataRepository実装"""

import io
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import pandas as pd
import pytz
from botocore.exceptions import ClientError

from src.domain.repositories.ohlcv_data_repository import IOhlcvDataRepository

logger = logging.getLogger(__name__)


class S3OhlcvDataRepository(IOhlcvDataRepository):
    """
    S3永続化リポジトリ
    
    IOhlcvDataRepositoryインターフェースの実装。
    S3をコールドストレージとして使用し、過去データの長期保存を担当。
    
    特徴:
    - Parquet形式での効率的な保存
    - 日付ベースパーティショニング
    - 期間指定読み込み対応
    """
    
    def __init__(self, bucket_name: str, s3_client):
        """
        Args:
            bucket_name: S3バケット名
            s3_client: boto3 S3クライアント
        """
        self.bucket_name = bucket_name
        self.s3_client = s3_client
        logger.info(f"S3OhlcvDataRepository initialized: bucket={bucket_name}")
    
    # ========================================
    # IOhlcvDataRepository実装
    # ========================================
    
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> bool:
        """
        OHLCVデータをS3に保存
        
        実装詳細:
        - Parquet形式で保存
        - 日付ベースのパーティション構造
        - パス: symbol={symbol}/timeframe={timeframe}/year={year}/month={month}/day={day}/
        
        Args:
            df: OHLCVデータ
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            bool: 保存成功時True
        """
        if df is None or df.empty:
            logger.info(
                f"{symbol} ({timeframe}) のデータが空のため、"
                f"S3へのアップロードをスキップします。"
            )
            return False
        
        try:
            # 最新タイムスタンプを取得
            latest_timestamp = df['timestamp_utc'].iloc[-1]
            
            # ファイル名生成
            filename = (
                f"{symbol}_{timeframe}_"
                f"{latest_timestamp.strftime('%Y%m%d%H%M%S')}.parquet"
            )
            
            # S3キー構築（パーティション構造）
            s3_full_key = os.path.join(
                f"symbol={symbol}",
                f"timeframe={timeframe}",
                "source=mt5",
                f"year={latest_timestamp.year}",
                f"month={latest_timestamp.month:02d}",
                f"day={latest_timestamp.day:02d}",
                filename
            ).replace("\\", "/")
            
            # Parquet変換
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
            parquet_buffer.seek(0)
            
            # S3アップロード
            logger.info(
                f"ParquetデータをS3にアップロード中: "
                f"s3://{self.bucket_name}/{s3_full_key}"
            )
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_full_key,
                Body=parquet_buffer.getvalue()
            )
            
            logger.info(
                f"S3へのアップロード成功: "
                f"s3://{self.bucket_name}/{s3_full_key}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"S3へのParquetファイルアップロード中にエラー: {e}",
                exc_info=True
            )
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
        OHLCVデータをS3から読み込み
        
        実装詳細:
        - 日付範囲からパーティションキーを生成
        - 各パーティションを逐次読み込み
        - DataFrame結合・ソート・重複排除
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 取得日数
        
        Returns:
            pd.DataFrame or None
        """

        # 期間の正規化
        if days is not None and start_date is None:
            end_date = datetime.now(pytz.UTC)
            start_date = end_date - timedelta(days=days)
        
        if start_date is None or end_date is None:
            logger.error("start_dateとend_dateの両方が必要です")
            return None
        
        # UTCに変換
        if start_date.tzinfo is None:
            start_date = pytz.UTC.localize(start_date)
        if end_date.tzinfo is None:
            end_date = pytz.UTC.localize(end_date)
        
        logger.info(
            f"Loading OHLCV from S3: {symbol}/{timeframe}, "
            f"{start_date.date()} to {end_date.date()}"
        )
        
        # パーティションキー生成
        partition_keys = self._generate_partition_keys(
            symbol, timeframe, start_date, end_date
        )
        
        if not partition_keys:
            logger.warning(f"No partition keys generated for {symbol}/{timeframe}")
            return None
        
        logger.debug(f"Generated {len(partition_keys)} partition keys")
        
        # 各パーティションを読み込み
        dfs = []
        for key in partition_keys:
            df = self._load_partition(key)
            if df is not None and not df.empty:
                dfs.append(df)
        
        if not dfs:
            logger.warning(
                f"No valid data retrieved from S3 for {symbol}/{timeframe}"
            )
            return None
        
        # DataFrame結合
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # timestamp_utcカラムを確認・変換
        if 'timestamp_utc' not in combined_df.columns:
            logger.error("timestamp_utc column not found in data")
            return None
        
        # datetime型に変換（必要に応じて）
        if not pd.api.types.is_datetime64_any_dtype(combined_df['timestamp_utc']):
            combined_df['timestamp_utc'] = pd.to_datetime(combined_df['timestamp_utc'])
        
        # タイムゾーン設定
        if combined_df['timestamp_utc'].dt.tz is None:
            combined_df['timestamp_utc'] = combined_df['timestamp_utc'].dt.tz_localize('UTC')
        
        # ソート
        combined_df = combined_df.sort_values('timestamp_utc')
        
        # 期間フィルタリング
        combined_df = combined_df[
            (combined_df['timestamp_utc'] >= start_date) &
            (combined_df['timestamp_utc'] <= end_date)
        ]
        
        # 重複排除
        combined_df = combined_df.drop_duplicates(
            subset=['timestamp_utc'], keep='last'
        )
        
        # インデックス設定
        combined_df = combined_df.set_index('timestamp_utc')
        
        logger.info(f"Loaded {len(combined_df)} rows from S3")
        
        return combined_df if not combined_df.empty else None
    
    def exists(
        self,
        symbol: str,
        timeframe: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        データ存在確認
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
            date: 確認する日付（Noneの場合は最新データ）
        
        Returns:
            bool: データが存在するか
        """

        try:
            if date is None:
                date = datetime.now(pytz.UTC)
            
            if date.tzinfo is None:
                date = pytz.UTC.localize(date)
            
            # パーティションプレフィックス生成
            prefix = (
                f"symbol={symbol}/"
                f"timeframe={timeframe}/"
                f"source=mt5/"
                f"year={date.year}/"
                f"month={date.month:02d}/"
                f"day={date.day:02d}/"
            )
            
            logger.debug(f"Checking existence with prefix: {prefix}")
            
            # S3オブジェクト一覧取得
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1  # 1つでもあればOK
            )
            
            exists = 'Contents' in response and len(response['Contents']) > 0
            
            logger.debug(
                f"Existence check for {symbol}/{timeframe} on {date.date()}: {exists}"
            )
            
            return exists
            
        except Exception as e:
            logger.error(
                f"Error checking existence for {symbol}/{timeframe} on {date}: {e}"
            )
            return False
    
    def get_available_range(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        利用可能なデータ範囲を取得
        
        実装詳細:
        - S3のパーティション一覧から判定
        - 実際のParquetファイルは読み込まない
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            Tuple[datetime, datetime]: (最古日時, 最新日時)
            None: データが存在しない場合
        """
        try:
            # パーティションプレフィックス
            prefix = f"symbol={symbol}/timeframe={timeframe}/"
            
            # S3オブジェクト一覧取得
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return None
            
            # パーティションから日付を抽出
            dates = []
            for obj in response['Contents']:
                key = obj['Key']
                # year=YYYY/month=MM/day=DD/ から日付抽出
                parts = key.split('/')
                year = month = day = None
                
                for part in parts:
                    if part.startswith('year='):
                        year = int(part.split('=')[1])
                    elif part.startswith('month='):
                        month = int(part.split('=')[1])
                    elif part.startswith('day='):
                        day = int(part.split('=')[1])
                
                if year and month and day:
                    date = datetime(year, month, day, tzinfo=pytz.UTC)
                    dates.append(date)
            
            if not dates:
                return None
            
            return (min(dates), max(dates))
            
        except Exception as e:
            logger.error(f"データ範囲取得エラー: {e}", exc_info=True)
            return None
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _generate_partition_keys(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        日付範囲からS3パーティションキーリストを生成
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
            start_date: 開始日
            end_date: 終了日
        
        Returns:
            List[str]: S3キーのリスト
        """
        keys = []
        
        # 日付を正規化（時刻を00:00:00に）
        current_date = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date_normalized = end_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # 日付範囲をループ
        while current_date <= end_date_normalized:
            # S3キー生成
            key = (
                f"symbol={symbol}/"
                f"timeframe={timeframe}/"
                f"source=mt5/"
                f"year={current_date.year}/"
                f"month={current_date.month:02d}/"
                f"day={current_date.day:02d}/"
            )
            
            keys.append(key)
            
            # 次の日へ
            current_date += timedelta(days=1)
        
        return keys
    
    def _load_partition(self, key: str) -> Optional[pd.DataFrame]:
        """
        単一パーティションからParquetファイルを読み込み
        
        Args:
            key: S3キープレフィックス
        
        Returns:
            pd.DataFrame or None
        """
        try:
            # パーティション内のファイル一覧を取得
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=key
            )
            
            if 'Contents' not in response:
                logger.debug(f"パーティションが存在しません: {key}")
                return None
            
            # 最新のファイルを取得
            files = [obj['Key'] for obj in response['Contents']]
            if not files:
                return None
            
            # 最新のファイル（アルファベット順で最後）
            latest_file = sorted(files)[-1]
            
            logger.debug(f"パーティション読み込み: {latest_file}")
            
            # S3からParquet読み込み
            obj = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=latest_file
            )
            
            df = pd.read_parquet(io.BytesIO(obj['Body'].read()))
            
            return df
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.debug(f"ファイルが存在しません: {key}")
                return None
            else:
                logger.error(f"S3読み込みエラー: {e}", exc_info=True)
                return None
        
        except Exception as e:
            logger.error(f"パーティション読み込みエラー: {e}", exc_info=True)
            return None