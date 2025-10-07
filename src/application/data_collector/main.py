# src/ec2/data_collector/main.py
import logging
import time
import json
import io
import os
import pandas as pd
import MetaTrader5 as mt5
from decimal import Decimal

# DataCollector用設定ローダーとAWSクライアントをインポート
from config_loader_dc import (
    validate_config,
    MT5_SECRET_NAME_DC, MT5_TERMINAL_PATH_DC, S3_RAW_DATA_BUCKET,
    TIMEFRAME_REVERSE_MAP,
    DATA_COLLECTION_SYMBOLS, DATA_COLLECTION_TIMEFRAMES,
    DATA_FETCH_COUNTS_BY_TIMEFRAME, # ← DATA_FETCH_COUNT から変更
    secretsmanager_client_dc, s3_client_dc
)

# --- ロガー設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("data_collector_main")

# --- 関数スタブ (後で実装する) ---

def get_mt5_credentials_dc():
    """Secrets ManagerからMT5認証情報を取得する"""
    if not MT5_SECRET_NAME_DC:
        logger.error("MT5_SECRET_NAME_DC が設定されていません。")
        return None
    if not secretsmanager_client_dc:
        logger.error("SecretsManagerクライアントが初期化されていません。")
        return None
    try:
        logger.info(f"Secrets Manager からシークレット '{MT5_SECRET_NAME_DC}' を取得します...")
        get_secret_value_response = secretsmanager_client_dc.get_secret_value(
            SecretId=MT5_SECRET_NAME_DC
        )
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            required_keys = ['mt5_login', 'mt5_password', 'mt5_server']
            if all(key in secret for key in required_keys):
                logger.info("MT5認証情報の取得成功。")
                return secret
            else:
                missing = [key for key in required_keys if key not in secret]
                logger.error(f"シークレット内に必要なキーが見つかりません: {', '.join(missing)}")
                return None
        else:
            logger.error("取得したシークレットは SecretString ではありません。")
            return None
    except Exception as e:
        logger.error(f"Secrets Managerからのシークレット取得中にエラー: {e}", exc_info=True)
        return None

def connect_to_mt5_dc(credentials):
    """取得した認証情報でMT5に接続する"""
    if not credentials:
        logger.error("MT5接続試行前に認証情報がありません。")
        return False
        
    try:
        login_id = int(credentials.get('mt5_login'))
        password = credentials.get('mt5_password')
        server = credentials.get('mt5_server')
    except (ValueError, TypeError) as e:
        logger.error(f"SecretsManagerから取得したmt5_loginが有効な数値ではありません: {credentials.get('mt5_login')}, Error: {e}")
        return False

    if not all([login_id, password, server, MT5_TERMINAL_PATH_DC]):
        logger.error("MT5接続に必要な情報 (Login, Password, Server, Path) が不足しています。")
        return False

    logger.info(f"MT5に接続試行... Path: {MT5_TERMINAL_PATH_DC}")
    if not mt5.initialize(login=login_id, password=password, server=server, path=MT5_TERMINAL_PATH_DC, timeout=20000):
        error_code = mt5.last_error()
        logger.error(f"MT5 initialize() 失敗: code={error_code[0]}, 説明={error_code[1]}")
        mt5.shutdown()
        return False
    
    logger.info("MT5 initialize() 成功。")
    terminal_info = mt5.terminal_info()
    if terminal_info:
        logger.info(f"  接続先ターミナル: {terminal_info.name}, Build: {terminal_info.build}")
    account_info = mt5.account_info()
    if account_info:
        logger.info(f"  口座情報: Login={account_info.login}, Name={account_info.name}, Currency={account_info.currency}")
    return True

def fetch_ohlcv_data(symbol, timeframe_int, count):
    """
    指定されたシンボルとタイムフレームのOHLCVデータをMT5から取得し、
    "standard_ohlcv_format"に準拠したDataFrameに変換する。
    """
    timeframe_str = TIMEFRAME_REVERSE_MAP.get(timeframe_int, "UNKNOWN")
    logger.info(f"MT5から {symbol} ({timeframe_str}) のOHLCVデータを {count} 件取得します。")
    try:
        # ターミナルでシンボルが非表示の場合、選択する
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.warning(f"シンボル {symbol} はMT5で見つかりません。スキップします。")
            return None
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"シンボル {symbol} を選択できませんでした。スキップします。")
                return None
            time.sleep(1) # 選択が反映されるまで少し待つ

        rates = mt5.copy_rates_from_pos(symbol, timeframe_int, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning(f"{symbol} ({timeframe_str}) のOHLCVデータを取得できませんでした。")
            return None
        
        # --- ここからがstandard_ohlcv_formatへの変換処理 ---
        df = pd.DataFrame(rates)
        
        # 1. 'time' (Unix時間) を 'timestamp_utc' に変換
        df['timestamp_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # 2. 'tick_volume' を 'volume' にリネーム
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        
        # 3. 必要な列を選択し、standard_ohlcv_formatの順序に並べる
        golden_schema_cols = ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
        df_golden = df[golden_schema_cols].copy()
        
        # 4. データ型を最終定義
        df_golden = df_golden.astype({
            'open': 'float64',
            'high': 'float64',
            'low': 'float64',
            'close': 'float64',
            'volume': 'int64'
        })
        
        logger.info(f"{symbol} ({timeframe_str}) のOHLCVデータ {len(df_golden)} 件をstandard_ohlcv_formatに準拠したDataFrameに変換しました。")
        return df_golden

    except Exception as e:
        logger.error(f"{symbol} ({timeframe_str}) のOHLCVデータ取得中にエラー: {e}", exc_info=True)
        return None

def upload_df_to_s3_dc(df, symbol, timeframe_str):
    """DataFrameをParquet形式でS3にアップロードする (DataCollector用)"""
    if df is None or df.empty:
        logger.info(f"{symbol} ({timeframe_str}) のデータが空のため、S3へのアップロードをスキップします。")
        return False
    
    # S3のルートプレフィックス
    # s3_key_prefix = "mt5/ohlcv/"

    # ファイル名は最新データのタイムスタンプから生成
    latest_timestamp = df['timestamp_utc'].iloc[-1]
    filename = f"{symbol}_{timeframe_str}_{latest_timestamp.strftime('%Y%m%d%H%M%S')}.parquet"
    
    # S3キー（パス）の構築
    s3_full_key = os.path.join(
        f"symbol={symbol}",
        f"timeframe={timeframe_str}",
        "source=mt5",  # sourceパーティションを追加
        f"year={latest_timestamp.year}",
        f"month={latest_timestamp.month:02d}",
        f"day={latest_timestamp.day:02d}",
        filename
    ).replace("\\", "/")

    try:
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
        parquet_buffer.seek(0)
        
        logger.info(f"ParquetデータをS3にアップロード中: s3://{S3_RAW_DATA_BUCKET}/{s3_full_key}")
        s3_client_dc.put_object(Bucket=S3_RAW_DATA_BUCKET, Key=s3_full_key, Body=parquet_buffer.getvalue())
        logger.info(f"S3へのアップロード成功: s3://{S3_RAW_DATA_BUCKET}/{s3_full_key}")
        return True
    except Exception as e:
        logger.error(f"S3へのParquetファイルアップロード中にエラー (Key: {s3_full_key}): {e}", exc_info=True)
        return False

# --- メイン実行ロジック ---
def run_data_collection():
    """データ収集のメインループ"""
    logger.info("DataCollector処理開始...")
    
    if not validate_config() or not s3_client_dc or not secretsmanager_client_dc:
        logger.critical("設定またはAWSクライアントが不完全なため、処理を中断します。")
        return

    mt5_connected = False
    credentials = get_mt5_credentials_dc()
    if not credentials:
        logger.error("MT5認証情報を取得できませんでした。処理を中断します。")
        return
        
    try:
        if not connect_to_mt5_dc(credentials):
            logger.error("MT5に接続できませんでした。処理を中断します。")
            return
        mt5_connected = True

        for symbol in DATA_COLLECTION_SYMBOLS:
            for timeframe_int in DATA_COLLECTION_TIMEFRAMES:
                timeframe_str = TIMEFRAME_REVERSE_MAP.get(timeframe_int, "UNKNOWN")

                # 【変更後】時間足に応じた取得件数を辞書から取得
                fetch_count = DATA_FETCH_COUNTS_BY_TIMEFRAME.get(timeframe_str, 1000) # デフォルト値として1000を指定
                
                # 取得件数を指定してデータ取得関数を呼び出す
                df = fetch_ohlcv_data(symbol, timeframe_int, fetch_count)
                
                if df is not None and not df.empty:
                    upload_df_to_s3_dc(df, symbol, timeframe_str)
                
                time.sleep(2) # API負荷軽減のため、リクエスト間に短い待機時間を入れる
            time.sleep(5) # シンボル間の待機

    except Exception as e:
        logger.critical(f"データ収集中に予期せぬクリティカルなエラーが発生: {e}", exc_info=True)
    finally:
        if mt5_connected:
            mt5.shutdown()
            logger.info("MT5接続を切断しました。")
    
    logger.info("DataCollector処理終了。")


if __name__ == "__main__":
    # このスクリプトは、EC2上でcronジョブやタスクスケジューラによって
    # 定期的に実行されることを想定しています。
    run_data_collection()