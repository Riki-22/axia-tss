# src/infrastructure/persistence/s3/s3_ohlcv_data_repository.py
"""S3永続化リポジトリ - IOhlcvDataRepository実装

このモジュールは、S3をコールドストレージとして使用し、
過去データの長期保存を担当するリポジトリ実装を提供します。

特徴:
- Parquet形式での効率的な保存
- 日付ベースパーティショニング (Hive形式)
- 期間指定読み込み対応
- 重複排除・ソート機能

パーティション構造:
    symbol={symbol}/timeframe={timeframe}/source=mt5/year={year}/month={month}/day={day}/
    └─ {symbol}_{timeframe}_{timestamp}.parquet

使用例:
    >>> from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository
    >>> import boto3
    >>> 
    >>> s3_client = boto3.client('s3')
    >>> repo = S3OhlcvDataRepository('my-bucket', s3_client)
    >>> 
    >>> # データ保存
    >>> repo.save_ohlcv(df, 'USDJPY', 'H1')
    >>> 
    >>> # データ読み込み（30日分）
    >>> df = repo.load_ohlcv('USDJPY', 'H1', days=30)
"""

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
    - メモリ効率的な逐次処理
    
    Attributes:
        bucket_name (str): S3バケット名
        s3_client: boto3 S3クライアント
    
    Note:
        - Phase 2: 逐次処理（シンプルで安定）
        - Phase 3計画: 並列処理での最適化を検討
    """
    
    def __init__(self, bucket_name: str, s3_client):
        """
        Args:
            bucket_name: S3バケット名
            s3_client: boto3 S3クライアント (boto3.client('s3'))
        
        Raises:
            ValueError: bucket_nameが空の場合
        """
        if not bucket_name:
            raise ValueError("bucket_name must not be empty")
        
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
        - パス: symbol={symbol}/timeframe={timeframe}/source=mt5/
                year={year}/month={month}/day={day}/
        
        Args:
            df: OHLCVデータ
                必須カラム: ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
        
        Returns:
            bool: 保存成功時True、失敗時False
        
        Example:
            >>> df = pd.DataFrame({
            ...     'timestamp_utc': [datetime(2025, 10, 15, 12, 0, tzinfo=pytz.UTC)],
            ...     'open': [150.0], 'high': [150.5], 'low': [149.5],
            ...     'close': [150.2], 'volume': [1000]
            ... })
            >>> success = repo.save_ohlcv(df, 'USDJPY', 'H1')
        
        Note:
            - 空のDataFrameはスキップされる
            - 既存ファイルがあっても上書きされる（タイムスタンプで区別）
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
                f"s3://{self.bucket_name}/{s3_full_key} "
                f"({len(df)} rows)"
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
        - 期間フィルタリング
        
        Args:
            symbol: 通貨ペアシンボル (例: "USDJPY")
            timeframe: タイムフレーム (例: "H1", "M15", "D1")
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 取得日数（end_dateからN日前まで）
        
        Returns:
            pd.DataFrame or None: OHLCVデータ（index=通番、timestamp_utcはカラム）
                データが存在しない場合はNone
        
        優先順位:
            1. start_date + end_date が指定されている場合: それを使用
            2. days のみ指定: end_date=現在、start_date=現在-days
            3. 何も指定なし: エラー（start_dateとend_dateの両方が必要）
        
        処理フロー:
            1. 期間の正規化（UTCへの変換）
            2. パーティションキーリスト生成
            3. 各パーティションを逐次読み込み
            4. DataFrame結合
            5. timestamp_utcをインデックスに設定
            6. ソート・重複排除
            7. 期間フィルタリング
            8. インデックスをリセットして返却
        
        Example:
            # 過去30日分
            >>> df = repo.load_ohlcv('USDJPY', 'H1', days=30)
            
            # 期間指定
            >>> df = repo.load_ohlcv(
            ...     'USDJPY', 'H1',
            ...     start_date=datetime(2025, 10, 1, tzinfo=pytz.UTC),
            ...     end_date=datetime(2025, 10, 15, tzinfo=pytz.UTC)
            ... )
        
        Note:
            - AsIs: シンプルな逐次処理
            - ToBe: 並列処理で最適化予定（Phase 3）
            - 重複データは自動的に排除される（keep='last'）
        
        Raises:
            ValueError: start_dateとend_dateの両方が指定されていない場合
        """
        # 1. 期間の正規化
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
        
        # 2. パーティションキー生成
        partition_keys = self._generate_partition_keys(
            symbol, timeframe, start_date, end_date
        )
        
        if not partition_keys:
            logger.warning(
                f"No partition keys generated for {symbol}/{timeframe}"
            )
            return None
        
        logger.info(
            f"Loading {len(partition_keys)} partition(s) sequentially"
        )
        
        # 3. 各パーティションを逐次読み込み
        dataframes = []
        loaded_count = 0
        skipped_count = 0
        
        for i, key in enumerate(partition_keys, 1):
            try:
                logger.debug(
                    f"Loading partition {i}/{len(partition_keys)}: {key}"
                )
                
                df_partition = self._load_partition(key)
                
                if df_partition is not None and not df_partition.empty:
                    dataframes.append(df_partition)
                    loaded_count += 1
                    logger.debug(
                        f"Loaded {len(df_partition)} rows from partition {i}"
                    )
                else:
                    skipped_count += 1
                    logger.debug(
                        f"Partition {i} is empty or does not exist"
                    )
                    
            except Exception as e:
                logger.error(
                    f"Failed to load partition {key}: {e}",
                    exc_info=True
                )
                # エラーがあっても他のパーティションは処理継続
                skipped_count += 1
                continue
        
        logger.info(
            f"Partition loading complete: "
            f"{loaded_count} loaded, {skipped_count} skipped"
        )
        
        # データが1つも取得できなかった場合
        if not dataframes:
            logger.warning(
                f"No valid data retrieved from S3 for {symbol}/{timeframe}"
            )
            return None
        
        # 4. DataFrame結合・後処理
        try:
            # 結合
            full_df = pd.concat(dataframes, ignore_index=True)
            logger.debug(
                f"Concatenated {len(dataframes)} dataframes, "
                f"total {len(full_df)} rows"
            )
            
            # メモリ解放
            del dataframes
            
            # 5. timestamp_utcカラムを確認・変換
            if 'timestamp_utc' not in full_df.columns:
                logger.error("timestamp_utc column not found in data")
                return None
            
            # datetime型に変換（必要に応じて）
            if not pd.api.types.is_datetime64_any_dtype(full_df['timestamp_utc']):
                full_df['timestamp_utc'] = pd.to_datetime(
                    full_df['timestamp_utc'], utc=True
                )
                logger.debug("Converted timestamp_utc to datetime type")
            
            # タイムゾーン設定（必要に応じて）
            if full_df['timestamp_utc'].dt.tz is None:
                full_df['timestamp_utc'] = full_df['timestamp_utc'].dt.tz_localize('UTC')
            
            # 6. ソート
            full_df = full_df.sort_values('timestamp_utc')
            
            # 7. 期間フィルタリング
            full_df = full_df[
                (full_df['timestamp_utc'] >= start_date) &
                (full_df['timestamp_utc'] <= end_date)
            ]
            
            # 8. 重複排除（最新データを保持）
            duplicates = full_df['timestamp_utc'].duplicated(keep='last')
            if duplicates.any():
                duplicate_count = duplicates.sum()
                logger.warning(
                    f"Found {duplicate_count} duplicate timestamps, removing..."
                )
                full_df = full_df[~duplicates]
            
            # 9. インデックス設定
            full_df = full_df.set_index('timestamp_utc')
            
            if full_df.empty:
                logger.warning(
                    f"No data found in specified date range "
                    f"{start_date.date()} to {end_date.date()}"
                )
                return None
            
            logger.info(
                f"Successfully loaded {len(full_df)} rows "
                f"for {symbol}/{timeframe}"
            )
            
            # timestamp_utcをインデックスとして保持（Redis互換性のため）
            return full_df
            
        except Exception as e:
            logger.error(
                f"Error during DataFrame processing: {e}",
                exc_info=True
            )
            return None
    
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
            bool: データが存在する場合True
        
        Example:
            # 特定日のデータ存在確認
            >>> exists = repo.exists(
            ...     'USDJPY', 'H1', 
            ...     datetime(2025, 10, 15, tzinfo=pytz.UTC)
            ... )
            
            # 最新データの存在確認
            >>> exists = repo.exists('USDJPY', 'H1')
        
        Note:
            - パーティション内に1つでもParquetファイルがあればTrue
            - ファイルの内容は検証しない（高速化のため）
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
            
            # Parquetファイルの存在確認
            if 'Contents' in response and len(response['Contents']) > 0:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.parquet'):
                        logger.debug(
                            f"Existence check for {symbol}/{timeframe} "
                            f"on {date.date()}: True"
                        )
                        return True
            
            logger.debug(
                f"Existence check for {symbol}/{timeframe} "
                f"on {date.date()}: False"
            )
            return False
            
        except Exception as e:
            logger.error(
                f"Error checking existence for {symbol}/{timeframe} "
                f"on {date}: {e}"
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
        - 実際のParquetファイルは読み込まない（高速化のため）
        - 日付単位の精度（時刻は00:00:00）
        
        Args:
            symbol: 通貨ペアシンボル
            timeframe: タイムフレーム
        
        Returns:
            Tuple[datetime, datetime]: (最古日時, 最新日時)
            None: データが存在しない場合
        
        Example:
            >>> range_tuple = repo.get_available_range('USDJPY', 'H1')
            >>> if range_tuple:
            ...     start, end = range_tuple
            ...     print(f"Data available from {start} to {end}")
        
        Note:
            - パーティション構造から日付を抽出
            - 実際のデータ内容は確認しない
            - パフォーマンス重視の設計
        """
        try:
            # パーティションプレフィックス
            prefix = (
                f"symbol={symbol}/"
                f"timeframe={timeframe}/"
                f"source=mt5/"
            )
            
            logger.debug(f"Getting available range for prefix: {prefix}")
            
            # S3オブジェクト一覧取得
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                logger.info(
                    f"No data found for {symbol}/{timeframe}"
                )
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
                logger.info(
                    f"No valid dates found for {symbol}/{timeframe}"
                )
                return None
            
            # 最古と最新を取得
            min_date = min(dates)
            max_date = max(dates)
            
            logger.info(
                f"Data range for {symbol}/{timeframe}: "
                f"{min_date.date()} to {max_date.date()}"
            )
            
            return (min_date, max_date)
            
        except Exception as e:
            logger.error(
                f"Error getting available range for {symbol}/{timeframe}: {e}",
                exc_info=True
            )
            return None
    
    # ========================================
    # 内部メソッド（プライベート）
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
        
        日付を1日ずつ進めてパーティションプレフィックスを生成します。
        時刻情報は無視され、00:00:00で正規化されます。
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: タイムフレーム（例: 'H1'）
            start_date: 開始日時（UTC、時刻は無視される）
            end_date: 終了日時（UTC、時刻は無視される）
        
        Returns:
            List[str]: S3パーティションプレフィックスのリスト
        
        Example:
            start_date: 2025-10-01 12:00:00 UTC
            end_date: 2025-10-03 18:30:00 UTC
            
            結果:
            [
                'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=01/',
                'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=02/',
                'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=03/'
            ]
        
        Note:
            - 日付単位でパーティション分割
            - 時刻情報は00:00:00で正規化
            - start_date, end_dateともに含む（両端含む）
        """
        keys = []
        
        # 日付を正規化（時刻を00:00:00に）
        current_date = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date_normalized = end_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        logger.debug(
            f"Generating partition keys from {current_date.date()} "
            f"to {end_date_normalized.date()}"
        )
        
        # 日付範囲をループ
        while current_date <= end_date_normalized:
            # S3キー生成（save_ohlcvと同じ構造）
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
        
        logger.debug(
            f"Generated {len(keys)} partition keys for "
            f"{symbol}/{timeframe}"
        )
        
        return keys
    
    def _load_partition(self, partition_prefix: str) -> Optional[pd.DataFrame]:
        """
        単一パーティションからParquetファイルを読み込み
        
        パーティション内の全Parquetファイルを読み込み、結合して返します。
        複数ファイルがある場合は自動的にマージされます。
        
        Args:
            partition_prefix: S3パーティションプレフィックス
                例: 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        
        Returns:
            pd.DataFrame: OHLCVデータ（index=通番）
            None: ファイルが存在しない場合
        
        処理フロー:
            1. パーティション内のオブジェクト一覧を取得
            2. Parquetファイルのみフィルタリング
            3. 各ファイルを読み込み
            4. 複数ある場合はDataFrame結合
        
        Raises:
            ClientError: S3アクセスエラー（NoSuchKey以外）
            ValueError: Parquetフォーマットエラー
        
        Note:
            - NoSuchKeyの場合はNoneを返す（エラーではない）
            - 個別ファイルのエラーは続行（ロバスト性重視）
            - Document 2の堅牢なアプローチを採用（全ファイル読み込み）
        """
        try:
            # パーティション内のオブジェクト一覧を取得
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=partition_prefix
            )
            
            # ファイルが存在しない場合
            if 'Contents' not in response or len(response['Contents']) == 0:
                logger.debug(
                    f"No files found in partition: {partition_prefix}"
                )
                return None
            
            # Parquetファイルのみフィルタリング
            parquet_files = [
                obj['Key'] for obj in response['Contents']
                if obj['Key'].endswith('.parquet')
            ]
            
            if not parquet_files:
                logger.debug(
                    f"No parquet files in partition: {partition_prefix}"
                )
                return None
            
            logger.debug(
                f"Found {len(parquet_files)} parquet file(s) in {partition_prefix}"
            )
            
            # 各Parquetファイルを読み込み
            dataframes = []
            for key in parquet_files:
                try:
                    # S3からファイル取得
                    obj_response = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=key
                    )
                    
                    # Parquet読み込み
                    buffer = io.BytesIO(obj_response['Body'].read())
                    df = pd.read_parquet(buffer, engine='pyarrow')
                    
                    if df is not None and not df.empty:
                        dataframes.append(df)
                        logger.debug(
                            f"Loaded {len(df)} rows from {key}"
                        )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to load parquet file {key}: {e}"
                    )
                    # 個別ファイルのエラーは続行（ロバスト性重視）
                    continue
            
            # DataFrameが1つもない場合
            if not dataframes:
                logger.warning(
                    f"Failed to load any data from partition: {partition_prefix}"
                )
                return None
            
            # 複数ファイルがある場合は結合
            if len(dataframes) == 1:
                result_df = dataframes[0]
            else:
                result_df = pd.concat(dataframes, ignore_index=True)
                logger.debug(
                    f"Merged {len(dataframes)} dataframes, "
                    f"total {len(result_df)} rows"
                )
            
            return result_df
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # パーティションが存在しない（正常ケース）
                logger.debug(
                    f"Partition does not exist: {partition_prefix}"
                )
                return None
            else:
                # その他のS3エラー（権限エラー等）
                logger.error(
                    f"S3 ClientError accessing partition "
                    f"{partition_prefix}: {e}"
                )
                raise
        
        except Exception as e:
            # その他の予期しないエラー
            logger.error(
                f"Unexpected error loading partition {partition_prefix}: {e}",
                exc_info=True
            )
            raise