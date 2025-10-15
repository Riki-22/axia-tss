# src/infrastructure/persistence/s3/s3_ohlcv_data_repository.py
import io
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import pytz

logger = logging.getLogger(__name__)


class S3OhlcvDataRepository:
    """S3へのマーケットデータ保存リポジトリ"""
    
    def __init__(self, bucket_name: str, s3_client):
        self.bucket_name = bucket_name
        self.s3_client = s3_client
    
    def save_ohlcv_data(self, df: pd.DataFrame, symbol: str, timeframe_str: str) -> bool:
        """
        DataFrameをParquet形式でS3に保存
        既存のupload_df_to_s3_dc関数のロジックを保持
        """
        if df is None or df.empty:
            logger.info(f"{symbol} ({timeframe_str}) のデータが空のため、S3へのアップロードをスキップします。")
            return False
        
        # ファイル名生成
        latest_timestamp = df['timestamp_utc'].iloc[-1]
        filename = f"{symbol}_{timeframe_str}_{latest_timestamp.strftime('%Y%m%d%H%M%S')}.parquet"
        
        # S3キー構築（パーティション構造）
        s3_full_key = os.path.join(
            f"symbol={symbol}",
            f"timeframe={timeframe_str}",
            "source=mt5",
            f"year={latest_timestamp.year}",
            f"month={latest_timestamp.month:02d}",
            f"day={latest_timestamp.day:02d}",
            filename
        ).replace("\\", "/")
        
        try:
            # Parquet変換
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
            parquet_buffer.seek(0)
            
            # S3アップロード
            logger.info(f"ParquetデータをS3にアップロード中: s3://{self.bucket_name}/{s3_full_key}")
            self.s3_client.put_object(
                Bucket=self.bucket_name, 
                Key=s3_full_key, 
                Body=parquet_buffer.getvalue()
            )
            logger.info(f"S3へのアップロード成功: s3://{self.bucket_name}/{s3_full_key}")
            return True
            
        except Exception as e:
            logger.error(f"S3へのParquetファイルアップロード中にエラー: {e}", exc_info=True)
            return False
    
    # ========================================
    # パーティションキー生成
    # ========================================
    
    def _generate_partition_keys(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        日付範囲からS3パーティションキーのリストを生成
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: タイムフレーム（例: 'H1'）
            start_date: 開始日時（UTC、時刻は無視される）
            end_date: 終了日時（UTC、時刻は無視される）
        
        Returns:
            List[str]: S3キーのリスト
        
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
        partition_keys = []
        
        # 日付を正規化（時刻を00:00:00に設定）
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_normalized = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.debug(
            f"Generating partition keys from {current_date.date()} to {end_date_normalized.date()}"
        )
        
        # 日付を1日ずつ進めてキーを生成
        while current_date <= end_date_normalized:
            # S3キーフォーマット（save_ohlcv_dataと同じ構造）
            partition_prefix = (
                f"symbol={symbol}/"
                f"timeframe={timeframe}/"
                f"source=mt5/"
                f"year={current_date.year}/"
                f"month={current_date.month:02d}/"
                f"day={current_date.day:02d}/"
            )
            
            partition_keys.append(partition_prefix)
            
            # 次の日へ
            current_date += timedelta(days=1)
        
        logger.info(
            f"Generated {len(partition_keys)} partition keys for "
            f"{symbol}/{timeframe} from {start_date.date()} to {end_date.date()}"
        )
        
        return partition_keys
    
    # ========================================
    # 単一パーティション読み込み
    # ========================================
    
    def _load_partition(self, partition_prefix: str) -> Optional[pd.DataFrame]:
        """
        単一パーティションからParquetファイルを読み込み
        
        Args:
            partition_prefix: S3パーティションプレフィックス
                例: 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        
        Returns:
            pd.DataFrame: OHLCVデータ（index=通番）
            None: ファイルが存在しない場合
        
        Raises:
            ClientError: S3アクセスエラー（NoSuchKey以外）
            ValueError: Parquetフォーマットエラー
        
        Note:
            - パーティション内の全Parquetファイルを読み込み
            - 複数ファイルがある場合は結合
            - NoSuchKeyの場合はNoneを返す（エラーではない）
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
                    # 個別ファイルのエラーは続行
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
            
        except self.s3_client.exceptions.NoSuchKey:
            # パーティションが存在しない（正常ケース）
            logger.debug(
                f"Partition does not exist: {partition_prefix}"
            )
            return None
            
        except self.s3_client.exceptions.ClientError as e:
            # その他のS3エラー（権限エラー等）
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                f"S3 ClientError ({error_code}) accessing partition "
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
    
    # ========================================
    # メイン読み込みロジック
    # ========================================
    
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        S3からOHLCVデータを読み込み（逐次処理）
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: タイムフレーム（例: 'H1'）
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 過去N日分（start_date/end_dateより優先度低）
        
        Returns:
            pd.DataFrame: OHLCVデータ（index=timestamp_utc）
            None: データが存在しない、または読み込み失敗
        
        優先順位:
            1. start_date + end_date が指定されている場合: それを使用
            2. days のみ指定: end_date=現在、start_date=現在-days
            3. 何も指定なし: デフォルト30日分
        
        処理フロー:
            1. 期間の正規化
            2. パーティションキーリスト生成
            3. 各パーティションを逐次読み込み
            4. DataFrame結合
            5. timestamp_utcをインデックスに設定
            6. ソート・重複排除
            7. 期間フィルタリング
        
        Example:
            # 過去30日分
            df = repo.load_ohlcv('USDJPY', 'H1', days=30)
            
            # 期間指定
            df = repo.load_ohlcv(
                'USDJPY', 'H1',
                start_date=datetime(2025, 10, 1, tzinfo=pytz.UTC),
                end_date=datetime(2025, 10, 15, tzinfo=pytz.UTC)
            )
        
        Note:
            - AsIs: シンプルな逐次処理
            - ToBe: 並列処理で最適化予定
        """
        # 1. 期間の正規化
        if end_date is None:
            end_date = datetime.now(pytz.UTC)
        
        if start_date is None:
            if days is not None:
                start_date = end_date - timedelta(days=days)
            else:
                # デフォルト: 30日分
                start_date = end_date - timedelta(days=30)
                logger.info(
                    f"No date range specified, defaulting to 30 days"
                )
        
        logger.info(
            f"Loading OHLCV data for {symbol}/{timeframe} "
            f"from {start_date.date()} to {end_date.date()}"
        )
        
        # 2. パーティションキーリスト生成
        partition_keys = self._generate_partition_keys(
            symbol, timeframe, start_date, end_date
        )
        
        if not partition_keys:
            logger.warning(
                f"No partitions found for {symbol}/{timeframe} "
                f"in date range {start_date.date()} to {end_date.date()}"
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
            
            # 5. timestamp_utcをdatetime型に変換（まだなら）
            if 'timestamp_utc' not in full_df.columns:
                logger.error("timestamp_utc column not found in data")
                return None
            
            if not pd.api.types.is_datetime64_any_dtype(full_df['timestamp_utc']):
                full_df['timestamp_utc'] = pd.to_datetime(
                    full_df['timestamp_utc'], utc=True
                )
                logger.debug("Converted timestamp_utc to datetime type")
            
            # 6. インデックス設定・ソート・重複排除
            full_df = full_df.set_index('timestamp_utc').sort_index()
            
            # 重複排除（最初の行を保持）
            duplicates = full_df.index.duplicated(keep='first')
            if duplicates.any():
                duplicate_count = duplicates.sum()
                logger.warning(
                    f"Found {duplicate_count} duplicate timestamps, removing..."
                )
                full_df = full_df[~duplicates]
            
            # 7. 期間フィルタリング
            # インデックスがdatetimeなので、スライスで効率的にフィルタ
            filtered_df = full_df.loc[start_date:end_date]
            
            if filtered_df.empty:
                logger.warning(
                    f"No data found in specified date range "
                    f"{start_date} to {end_date}"
                )
                return None
            
            logger.info(
                f"Successfully loaded {len(filtered_df)} rows "
                f"for {symbol}/{timeframe}"
            )
            
            # インデックスをリセットしてカラムに戻す
            return filtered_df.reset_index()
            
        except Exception as e:
            logger.error(
                f"Error during DataFrame processing: {e}",
                exc_info=True
            )
            return None
    
    # ========================================
    #  補助メソッド
    # ========================================
    
    def exists(
        self,
        symbol: str,
        timeframe: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        S3にデータが存在するか確認
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            date: 確認する日付（Noneの場合は最新データを確認）
        
        Returns:
            bool: データが存在する場合True
        
        Example:
            # 特定日のデータ存在確認
            exists = repo.exists(
                'USDJPY', 'H1', 
                datetime(2025, 10, 15, tzinfo=pytz.UTC)
            )
            
            # 最新データの存在確認
            exists = repo.exists('USDJPY', 'H1')
        """
        if date is None:
            date = datetime.now(pytz.UTC)
        
        # パーティションプレフィックス生成
        partition_prefix = (
            f"symbol={symbol}/"
            f"timeframe={timeframe}/"
            f"source=mt5/"
            f"year={date.year}/"
            f"month={date.month:02d}/"
            f"day={date.day:02d}/"
        )
        
        try:
            # パーティション内のオブジェクトを確認
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=partition_prefix,
                MaxKeys=1  # 1件あれば十分
            )
            
            # Contentsがあり、ParquetファイルがあればTrue
            if 'Contents' in response and len(response['Contents']) > 0:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.parquet'):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"Error checking existence for {symbol}/{timeframe} "
                f"on {date.date()}: {e}"
            )
            return False
    
    def get_available_range(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[tuple]:
        """
        利用可能なデータの期間を取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
        
        Returns:
            Tuple[datetime, datetime]: (最古日時, 最新日時)
            None: データが存在しない場合
        
        Note:
            - S3のパーティション一覧から判定
            - 実際のParquetファイルは読み込まない
            - 日付単位の精度（時刻は00:00:00）
        
        Example:
            range_tuple = repo.get_available_range('USDJPY', 'H1')
            if range_tuple:
                start, end = range_tuple
                print(f"Data available from {start} to {end}")
        """
        try:
            # パーティションのプレフィックス
            prefix = f"symbol={symbol}/timeframe={timeframe}/source=mt5/"
            
            # 全パーティションを取得
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            
            dates = []
            for page in pages:
                # CommonPrefixesから日付を抽出
                if 'CommonPrefixes' in page:
                    for prefix_obj in page['CommonPrefixes']:
                        prefix_str = prefix_obj['Prefix']
                        # 例: symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/
                        try:
                            parts = prefix_str.split('/')
                            year = int(parts[3].split('=')[1])
                            month = int(parts[4].split('=')[1])
                            day = int(parts[5].split('=')[1])
                            
                            date = datetime(year, month, day, tzinfo=pytz.UTC)
                            dates.append(date)
                        except (IndexError, ValueError):
                            continue
            
            if not dates:
                logger.info(
                    f"No data found for {symbol}/{timeframe}"
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