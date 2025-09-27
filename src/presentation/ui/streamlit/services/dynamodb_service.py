# src/presentation/ui/streamlit/services/dynamodb_service.py

import boto3
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List, Optional

# 親ディレクトリの.envを読み込み
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class DynamoDBService:
    def __init__(self):
        try:
            # 環境変数で判定
            if os.getenv('ENV') == 'ec2':
                # EC2環境 - IAMロールを使用
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
                )
                print("認証方法: EC2 IAMロール")
            elif os.getenv('AWS_PROFILE'):
                # ローカル開発 - プロファイル使用
                session = boto3.Session(profile_name=os.getenv('AWS_PROFILE'))
                self.dynamodb = session.resource(
                    'dynamodb',
                    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
                )
                print(f"認証方法: AWS Profile ({os.getenv('AWS_PROFILE')})")
            else:
                # デフォルト
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
                )
                print("認証方法: デフォルト")
            
            self.table_name = os.getenv('DYNAMODB_STATE_TABLE_NAME')
            self.table = self.dynamodb.Table(self.table_name) if self.table_name else None
            self.connected = True
            self.error = None
        except Exception as e:
            self.connected = False
            self.error = str(e)
    
    def test_connection(self) -> Dict:
        """接続テスト"""
        if not self.connected:
            return {'status': 'ERROR', 'message': 'DynamoDB接続失敗', 'error': self.error}
        
        try:
            self.table.table_status
            return {'status': 'SUCCESS', 'message': 'DynamoDB接続成功', 'table': self.table_name}
        except Exception as e:
            return {'status': 'ERROR', 'message': 'テーブルアクセス失敗', 'error': str(e)}
    
    def get_kill_switch_status(self) -> Dict:
        """Kill Switch状態を取得"""
        if not self.connected or not self.table:
            return {'status': 'UNKNOWN', 'error': 'DynamoDB未接続', 'active': False}
        
        try:
            response = self.table.get_item(
                Key={
                    'pk': 'GLOBALCONFIG',
                    'sk': 'SETTING#KILL_SWITCH'
                }
            )
            
            if 'Item' in response:
                status = response['Item'].get('status', 'OFF')
                updated = response['Item'].get('last_updated_utc', 'N/A')
                return {
                    'status': status,
                    'last_updated': updated,
                    'active': status == 'ON'
                }
            
            return {'status': 'OFF', 'active': False, 'message': 'Kill Switch未設定'}
            
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e), 'active': False}
    
    def set_kill_switch(self, status: str) -> Dict:
        """Kill Switch状態を更新"""
        if not self.connected or not self.table:
            return {'success': False, 'error': 'DynamoDB未接続'}
        
        try:
            response = self.table.put_item(
                Item={
                    'pk': 'GLOBALCONFIG',
                    'sk': 'SETTING#KILL_SWITCH',
                    'status': status.upper(),
                    'last_updated_utc': datetime.utcnow().isoformat(),
                    'item_type': 'GlobalSetting'
                }
            )
            return {'success': True, 'status': status}
        except Exception as e:
            return {'success': False, 'error': str(e)}
