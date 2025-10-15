# src/infrastructure/persistence/s3/market_data_repository.py
import io
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import pytz

logger = logging.getLogger(__name__)


class S3MarketDataRepository:
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
    # テスト用ヘルパー（後で削除可能）
    # ========================================
    
    def _test_partition_keys(self):
        """パーティションキー生成のテスト"""
        import pytz
        
        # テストケース1: 1日分
        start = datetime(2025, 10, 15, 10, 30, 0, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, 18, 45, 0, tzinfo=pytz.UTC)
        keys = self._generate_partition_keys('USDJPY', 'H1', start, end)
        print(f"Test 1 (same day): {len(keys)} keys")
        for key in keys:
            print(f"  {key}")
        
        # テストケース2: 3日分
        start = datetime(2025, 10, 13, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, tzinfo=pytz.UTC)
        keys = self._generate_partition_keys('EURUSD', 'M15', start, end)
        print(f"\nTest 2 (3 days): {len(keys)} keys")
        for key in keys:
            print(f"  {key}")
        
        # テストケース3: 月跨ぎ
        start = datetime(2025, 9, 29, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 2, tzinfo=pytz.UTC)
        keys = self._generate_partition_keys('GBPJPY', 'D1', start, end)
        print(f"\nTest 3 (month boundary): {len(keys)} keys")
        for key in keys:
            print(f"  {key}")


# 動作確認スクリプト
if __name__ == "__main__":
    import boto3
    from src.infrastructure.config.settings import settings
    
    # S3クライアント作成
    s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    # リポジトリ作成
    repo = S3MarketDataRepository(
        bucket_name=settings.s3_raw_data_bucket,
        s3_client=s3_client
    )
    
    # テスト実行
    print("=" * 60)
    print("S3 Partition Key Generation Test")
    print("=" * 60)
    repo._test_partition_keys()