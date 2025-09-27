# src/ec2/data_collector/config_loader_dc.py
import os
import json # JSONをパースするためにインポート
from dotenv import load_dotenv
import logging
import boto3
import MetaTrader5 as mt5

# --- ロガー設定 ---
logger = logging.getLogger(f"data_collector.{__name__}")

# --- 環境変数の読み込み ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    logger.info(f".env ファイル ({dotenv_path}) を読み込みました。")
else:
    logger.warning(f".env ファイル ({dotenv_path}) が見つかりません。環境変数から設定を読み取ります。")

# --- 基本設定値 ---
AWS_REGION_DC = os.getenv('AWS_REGION_DC', "ap-northeast-1")
MT5_SECRET_NAME_DC = os.getenv('MT5_SECRET_NAME_DC')
MT5_TERMINAL_PATH_DC = os.getenv('MT5_TERMINAL_PATH_DC')
S3_RAW_DATA_BUCKET = os.getenv('S3_RAW_DATA_BUCKET')

# (不要になったため削除) DATA_FETCH_COUNT = int(os.getenv('DATA_FETCH_COUNT', '1000'))

# 【変更点】時間足ごとの取得件数をJSONから読み込む
DATA_FETCH_COUNTS_BY_TIMEFRAME = {}
_fetch_counts_json = os.getenv('DATA_FETCH_COUNTS_JSON')
if _fetch_counts_json:
    try:
        DATA_FETCH_COUNTS_BY_TIMEFRAME = json.loads(_fetch_counts_json)
        logger.info(f"時間足ごとの取得件数を .env から読み込みました: {DATA_FETCH_COUNTS_BY_TIMEFRAME}")
    except json.JSONDecodeError:
        logger.critical("DATA_FETCH_COUNTS_JSON の値が有効なJSON形式ではありません。処理を続行できません。")
        # エラーが発生した場合は空の辞書のままにする
        DATA_FETCH_COUNTS_BY_TIMEFRAME = {}
else:
    logger.warning("DATA_FETCH_COUNTS_JSON が設定されていません。")


# カンマ区切りの文字列をリストに変換
_symbols_str = os.getenv('DATA_COLLECTION_SYMBOLS', "USDJPY,EURUSD")
DATA_COLLECTION_SYMBOLS = [symbol.strip().upper() for symbol in _symbols_str.split(',') if symbol.strip()]

_timeframes_str = os.getenv('DATA_COLLECTION_TIMEFRAMES', "H1,D1")
# MT5のTIMEFRAME定数にマッピング
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
}
DATA_COLLECTION_TIMEFRAMES = [TIMEFRAME_MAP[tf.strip().upper()] for tf in _timeframes_str.split(',') if tf.strip().upper() in TIMEFRAME_MAP]

# タイムフレーム定数から文字列への逆引きマップ (ログ出力やS3パス生成用)
TIMEFRAME_REVERSE_MAP = {v: k for k, v in TIMEFRAME_MAP.items()}

if not DATA_COLLECTION_TIMEFRAMES:
    logger.warning(f"設定されたタイムフレームが無効か空です。デフォルト (H1, D1) を使用します。設定値: '{_timeframes_str}'")
    DATA_COLLECTION_TIMEFRAMES = [mt5.TIMEFRAME_H1, mt5.TIMEFRAME_D1]

# --- AWSクライアント初期化 ---
s3_client_dc = None
secretsmanager_client_dc = None
try:
    logger.info(f"DataCollector用 AWSクライアントをリージョン '{AWS_REGION_DC}' で初期化します...")
    s3_client_dc = boto3.client('s3', region_name=AWS_REGION_DC)
    secretsmanager_client_dc = boto3.client('secretsmanager', region_name=AWS_REGION_DC)
    logger.info("DataCollector用 AWSクライアントの初期化成功。")
except Exception as e:
    logger.critical(f"DataCollector用 AWSクライアントの初期化に失敗: {e}", exc_info=True)

# --- 必須設定値の検証 ---
def validate_config():
    """ 必須設定値がロードされているか検証する """
    is_valid = True
    required_configs = {
        "MT5_SECRET_NAME_DC": MT5_SECRET_NAME_DC,
        "MT5_TERMINAL_PATH_DC": MT5_TERMINAL_PATH_DC,
        "S3_RAW_DATA_BUCKET": S3_RAW_DATA_BUCKET,
    }
    missing_configs = [name for name, value in required_configs.items() if not value]
    if missing_configs:
        logger.critical(f"必須の設定値が .env または環境変数に設定されていません: {', '.join(missing_configs)}")
        is_valid = False

    if not DATA_COLLECTION_SYMBOLS:
        logger.critical("収集対象のシンボルが設定されていません (DATA_COLLECTION_SYMBOLS)。")
        is_valid = False

    if not DATA_COLLECTION_TIMEFRAMES:
        logger.critical("収集対象の時間軸が設定されていません (DATA_COLLECTION_TIMEFRAMES)。")
        is_valid = False
    
    # 【変更点】新しい設定辞書の検証
    if not isinstance(DATA_FETCH_COUNTS_BY_TIMEFRAME, dict) or not DATA_FETCH_COUNTS_BY_TIMEFRAME:
        logger.critical("DATA_FETCH_COUNTS_BY_TIMEFRAME が正しく設定されていません。`DATA_FETCH_COUNTS_JSON` を確認してください。")
        is_valid = False
    elif "DEFAULT" not in DATA_FETCH_COUNTS_BY_TIMEFRAME:
        logger.warning("`DATA_FETCH_COUNTS_JSON` に 'DEFAULT' の設定がありません。未定義の時間足がある場合、エラーになる可能性があります。")

    return is_valid