# src/infrastructure/persistence/s3/market_data_repository.py
import io
import os
import logging
from typing import Optional
import pandas as pd

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