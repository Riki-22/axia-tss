# src/ec2/order_manager/config_loader.py

import os
from dotenv import load_dotenv
import logging
import boto3

# --- ロガー設定 ---
# このモジュールが最初にインポートされることを想定して、ここに配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s')
logger = logging.getLogger(__name__) # モジュール固有のロガー

# --- 環境変数の読み込み ---
load_dotenv() # スクリプトと同じ場所の .env ファイルを読み込む

# --- 基本設定値 ---
AWS_REGION = os.getenv('AWS_REGION', "ap-northeast-1") # .env またはデフォルト
QUEUE_URL = os.getenv('SQS_QUEUE_URL')
MT5_SECRET_NAME = os.getenv('MT5_SECRET_NAME')
DYNAMODB_STATE_TABLE_NAME = os.getenv('DYNAMODB_STATE_TABLE_NAME')
MT5_TERMINAL_PATH = os.getenv('MT5_TERMINAL_PATH')
MT5_MAGIC_NUMBER = int(os.getenv('MT5_MAGIC_NUMBER', '12345')) # デフォルト値を文字列で指定し、intに変換

# --- AWSクライアント初期化 ---
try:
    logger.info(f"AWSクライアントをリージョン '{AWS_REGION}' で初期化します...")
    sqs_client = boto3.client('sqs', region_name=AWS_REGION)
    secretsmanager_client = boto3.client('secretsmanager', region_name=AWS_REGION)
    dynamodb_resource = boto3.resource('dynamodb', region_name=AWS_REGION)
    logger.info("AWSクライアントの初期化成功。")
except Exception as e:
    logger.critical(f"AWSクライアントの初期化に失敗: {e}", exc_info=True)
    # アプリケーションを終了させるか、エラーを伝播させるかは設計による
    # ここではエラーログを出力し、各クライアントが None になる可能性があることを意味する
    sqs_client = None
    secretsmanager_client = None
    dynamodb_resource = None
    # raise # またはここで例外を再送出する

# --- 必須設定値の検証 ---
if not all([QUEUE_URL, MT5_SECRET_NAME, DYNAMODB_STATE_TABLE_NAME, MT5_TERMINAL_PATH]):
    missing_configs = []
    if not QUEUE_URL: missing_configs.append("SQS_QUEUE_URL")
    if not MT5_SECRET_NAME: missing_configs.append("MT5_SECRET_NAME")
    if not DYNAMODB_STATE_TABLE_NAME: missing_configs.append("DYNAMODB_STATE_TABLE_NAME")
    if not MT5_TERMINAL_PATH: missing_configs.append("MT5_TERMINAL_PATH")
    logger.critical(f"必須の設定値が .env ファイルまたは環境変数に設定されていません: {', '.join(missing_configs)}")
    # ここで exit() するか、アプリケーション側でクライアントが None でないことを確認する