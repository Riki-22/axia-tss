# src/infrastructure/config/settings.py
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import boto3
from dotenv import load_dotenv

# ロガー設定
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s'
)
logger = logging.getLogger(__name__)

class Settings:
    """統合設定クラス"""
    
    def __init__(self, env_path: Optional[Path] = None):
        # .envファイルの読み込み
        if env_path is None:
            # 複数の場所から.envを探す
            possible_paths = [
                Path(__file__).parent / '.env',
                Path(__file__).parent.parent.parent.parent / '.env',  # プロジェクトルート
                Path.cwd() / '.env'
            ]
            for path in possible_paths:
                if path.exists():
                    env_path = path
                    break
        
        if env_path and env_path.exists():
            load_dotenv(env_path)
            logger.info(f".env ファイル ({env_path}) を読み込みました。")
        else:
            logger.warning(".env ファイルが見つかりません。環境変数から設定を読み取ります。")
        
        # AWS設定
        self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-1')
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.dynamodb_table_name = os.getenv('DYNAMODB_STATE_TABLE_NAME')
        self.mt5_secret_name = os.getenv('MT5_SECRET_NAME')
        
        # MT5設定
        self.mt5_terminal_path = os.getenv('MT5_TERMINAL_PATH')
        self.mt5_magic_number = int(os.getenv('MT5_MAGIC_NUMBER', '12345'))
        
        # ローカルMT5認証情報（開発用）
        self.mt5_login = os.getenv('MT5_LOGIN')
        self.mt5_password = os.getenv('MT5_PASSWORD')
        self.mt5_server = os.getenv('MT5_SERVER')
        
        # AWSクライアント初期化
        self._init_aws_clients()
        
        # 設定検証
        self._validate_settings()

        ###### Data Collector設定 ######
        self.s3_raw_data_bucket = os.getenv('S3_RAW_DATA_BUCKET')
        
        # シンボル設定
        symbols_str = os.getenv('DATA_COLLECTION_SYMBOLS', 'USDJPY,EURUSD')
        self.data_collection_symbols = [
            symbol.strip().upper() 
            for symbol in symbols_str.split(',') 
            if symbol.strip()
        ]
        
        # タイムフレーム設定
        self.timeframe_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, 
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, 
            "MN1": mt5.TIMEFRAME_MN1
        }
        
        timeframes_str = os.getenv('DATA_COLLECTION_TIMEFRAMES', 'H1,D1')
        self.data_collection_timeframes = [
            self.timeframe_map[tf.strip().upper()]
            for tf in timeframes_str.split(',')
            if tf.strip().upper() in self.timeframe_map
        ]
        
        # 取得件数設定
        fetch_counts_json = os.getenv('DATA_FETCH_COUNTS_JSON')
        if fetch_counts_json:
            try:
                self.data_fetch_counts = json.loads(fetch_counts_json)
            except json.JSONDecodeError:
                logger.error("DATA_FETCH_COUNTS_JSON が無効なJSON形式です")
                self.data_fetch_counts = {"DEFAULT": 1000}
        else:
            self.data_fetch_counts = {"DEFAULT": 1000}
        ################################
    
    def _init_aws_clients(self):
        """AWSクライアント初期化"""
        try:
            logger.info(f"AWSクライアントをリージョン '{self.aws_region}' で初期化します...")
            self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
            self.secretsmanager_client = boto3.client('secretsmanager', region_name=self.aws_region)
            self.dynamodb_resource = boto3.resource('dynamodb', region_name=self.aws_region)
            logger.info("AWSクライアントの初期化成功。")
        except Exception as e:
            logger.critical(f"AWSクライアントの初期化に失敗: {e}", exc_info=True)
            self.sqs_client = None
            self.secretsmanager_client = None
            self.dynamodb_resource = None
    
    def _validate_settings(self):
        """必須設定値の検証"""
        missing_configs = []
        if not self.queue_url: 
            missing_configs.append("SQS_QUEUE_URL")
        if not self.mt5_secret_name and not self.mt5_login: 
            missing_configs.append("MT5_SECRET_NAME or MT5_LOGIN")
        if not self.dynamodb_table_name: 
            missing_configs.append("DYNAMODB_STATE_TABLE_NAME")
        if not self.mt5_terminal_path: 
            missing_configs.append("MT5_TERMINAL_PATH")
        
        if missing_configs:
            logger.warning(f"設定値が不足しています: {', '.join(missing_configs)}")
    
# src/infrastructure/config/settings.py の get_mt5_credentials() メソッドを修正

def get_mt5_credentials(self) -> Dict[str, Any]:
    """MT5認証情報を取得"""
    
    # Secrets Manager優先
    if self.mt5_secret_name and self.secretsmanager_client:
        try:
            logger.info(f"Secrets Manager からシークレット '{self.mt5_secret_name}' を取得します...")
            
            get_secret_value_response = self.secretsmanager_client.get_secret_value(
                SecretId=self.mt5_secret_name
            )
            
            if 'SecretString' in get_secret_value_response:
                import json
                secret = json.loads(get_secret_value_response['SecretString'])
                
                # 必須キーの確認
                if 'mt5_login' in secret and 'mt5_password' in secret and 'mt5_server' in secret:
                    logger.info("MT5認証情報の取得成功。")
                    logger.info(f"  Login: {secret.get('mt5_login')}")
                    logger.info(f"  Server: {secret.get('mt5_server')}")
                    return secret
                else:
                    logger.error("シークレット内に必要なキー (mt5_login, mt5_password, mt5_server) が見つかりません。")
            else:
                logger.error("取得したシークレットは SecretString ではありません。")
                
        except Exception as e:
            logger.error(f"Secrets Managerからのシークレット取得中にエラー: {e}", exc_info=True)
    else:
        if not self.mt5_secret_name:
            logger.warning("MT5_SECRET_NAME が設定されていません。")
        if not self.secretsmanager_client:
            logger.error("SecretsManagerクライアントが初期化されていません。")
    
    # フォールバック：環境変数から取得
    if self.mt5_login and self.mt5_password and self.mt5_server:
        logger.info("環境変数からMT5認証情報を使用します（Secrets Manager取得失敗のため）")
        return {
            'mt5_login': self.mt5_login,
            'mt5_password': self.mt5_password,
            'mt5_server': self.mt5_server
        }
    
    logger.error("MT5認証情報が Secrets Manager にも環境変数にも見つかりません")
    return {}

# シングルトンインスタンス
settings = Settings()