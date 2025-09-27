# scripts/forex_tester_importer/main.py
import logging
import os
import io
import boto3
from dotenv import load_dotenv

# 更新されたパーサーをインポート
from forex_tester_parser import parse_forex_tester_csv_to_golden_schema

# --- ロガー設定 ---
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s')
logger = logging.getLogger(f"forex_tester_importer.{__name__}")

# --- 設定の読み込み ---
def load_configuration():
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    config = {
        "aws_profile": os.getenv("AWS_PROFILE"),
        "s3_bucket_name": os.getenv("S3_BUCKET_NAME"),
        "forex_tester_data_dir": os.getenv("FOREX_TESTER_DATA_DIR"),
    }
    if not all([config["s3_bucket_name"], config["forex_tester_data_dir"]]):
        logger.error("必要な設定 (S3_BUCKET_NAME, FOREX_TESTER_DATA_DIR) が .env に設定されていません。")
        return None
    return config

# --- S3アップロード関数 ---
def upload_df_to_s3(df, s3_client, bucket_name, s3_key):
    try:
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=parquet_buffer.getvalue())
        logger.info(f"S3へのアップロード成功: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        logger.error(f"S3へのParquetファイルアップロード中にエラー (Key: {s3_key}): {e}", exc_info=True)

# --- メイン処理 ---
def main():
    logger.info("ForexTester6 データ取り込みスクリプト開始")
    config = load_configuration()
    if not config:
        return

    try:
        session = boto3.Session(profile_name=config["aws_profile"])
        s3_client = session.client('s3')
    except Exception as e:
        logger.error(f"AWSセッションの初期化に失敗: {e}", exc_info=True)
        return

    data_dir = config["forex_tester_data_dir"]
    s3_bucket = config["s3_bucket_name"]

    for filename in os.listdir(data_dir):
        if not (filename.lower().endswith('.csv') or filename.lower().endswith('.txt')):
            continue

        file_path = os.path.join(data_dir, filename)
        logger.info(f"処理対象ファイルを発見: {file_path}")

        parts = filename.split('.')[0].split('_')
        if len(parts) < 2:
            logger.warning(f"ファイル名 '{filename}' からシンボルと時間軸を特定できませんでした。スキップします。")
            continue
        symbol_from_filename = parts[0].upper()
        timeframe_from_filename = parts[1].upper()

        # 新しいパーサーを呼び出す
        df_golden = parse_forex_tester_csv_to_golden_schema(file_path, timeframe_from_filename)
        
        if df_golden is not None and not df_golden.empty:
            latest_timestamp = df_golden['timestamp_utc'].iloc[-1]
            s3_object_key = (
                f"symbol={symbol_from_filename}/"
                f"timeframe={timeframe_from_filename}/"
                f"source=forextester/"
                f"year={latest_timestamp.year}/"
                f"month={latest_timestamp.month:02d}/"
                f"day={latest_timestamp.day:02d}/"
                f"{symbol_from_filename}_{timeframe_from_filename}_{latest_timestamp.strftime('%Y%m%d%H%M%S')}.parquet"
            )
            upload_df_to_s3(df_golden, s3_client, s3_bucket, s3_object_key)

if __name__ == '__main__':
    main()