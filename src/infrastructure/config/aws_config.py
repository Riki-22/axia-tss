# src/infrastructure/config/aws_config.py
"""AWS関連設定"""

import os
import logging
import boto3
from typing import Optional
from .base_config import BaseConfig

logger = logging.getLogger(__name__)

class AWSConfig(BaseConfig):
    """AWS関連設定クラス"""
    
    def __init__(self):
        super().__init__()
        
        # AWS設定
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.dynamodb_table_name = os.getenv('DYNAMODB_STATE_TABLE_NAME')
        self.s3_raw_data_bucket = os.getenv('S3_RAW_DATA_BUCKET')
        
        # AWSクライアント
        self.dynamodb_resource = None
        self.sqs_client = None
        self.secretsmanager_client = None
        self.s3_client = None
        
        # クライアント初期化
        self._init_aws_clients()
        
        # 設定検証
        self._validate()
    
    def _init_aws_clients(self):
        """AWS クライアント初期化"""
        try:
            # 環境判定
            if os.getenv('ENV') == 'ec2':
                # EC2環境 - IAMロール使用
                logger.info("Using EC2 IAM Role for AWS authentication")
                self.dynamodb_resource = boto3.resource('dynamodb', region_name=self.aws_region)
                self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
                self.secretsmanager_client = boto3.client('secretsmanager', region_name=self.aws_region)
                self.s3_client = boto3.client('s3', region_name=self.aws_region)
                
            elif os.getenv('AWS_PROFILE'):
                # ローカル開発 - プロファイル使用
                profile_name = os.getenv('AWS_PROFILE')
                logger.info(f"Using AWS Profile: {profile_name}")
                session = boto3.Session(profile_name=profile_name)
                self.dynamodb_resource = session.resource('dynamodb', region_name=self.aws_region)
                self.sqs_client = session.client('sqs', region_name=self.aws_region)
                self.secretsmanager_client = session.client('secretsmanager', region_name=self.aws_region)
                self.s3_client = session.client('s3', region_name=self.aws_region)
                
            else:
                # デフォルト認証チェーン
                logger.info("Using default AWS credential chain")
                self.dynamodb_resource = boto3.resource('dynamodb', region_name=self.aws_region)
                self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
                self.secretsmanager_client = boto3.client('secretsmanager', region_name=self.aws_region)
                self.s3_client = boto3.client('s3', region_name=self.aws_region)
            
            # 接続テスト
            self.dynamodb_resource.meta.client.list_tables(Limit=1)
            logger.info("AWS clients initialized successfully")
        
        except Exception as e:
            logger.error(f"AWS client initialization failed: {e}")
            # エラー時はNoneを設定
            self.dynamodb_resource = None
            self.sqs_client = None
            self.secretsmanager_client = None
            self.s3_client = None
    
    def _validate(self):
        """設定検証"""
        missing = []
        if not self.queue_url:
            missing.append("SQS_QUEUE_URL")
        if not self.dynamodb_table_name:
            missing.append("DYNAMODB_STATE_TABLE_NAME")
        
        if missing:
            logger.warning(f"AWS設定値が不足: {', '.join(missing)}")