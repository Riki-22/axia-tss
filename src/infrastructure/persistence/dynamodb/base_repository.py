# src/infrastructure/persistence/dynamodb/base_repository.py
import boto3
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class BaseDynamoDBRepository:
    """DynamoDBリポジトリの基底クラス"""
    
    def __init__(self, table_name: str, dynamodb_client=None):
        self.table_name = table_name
        self.client = dynamodb_client or boto3.client('dynamodb')
        self.resource = boto3.resource('dynamodb')
        self.table = self.resource.Table(table_name)
    
    def put_item(self, item: Dict[str, Any]) -> bool:
        """アイテムを保存"""
        try:
            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"DynamoDB put_item error: {e}")
            return False
    
    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """アイテムを取得"""
        try:
            response = self.table.get_item(Key=key)
            return response.get('Item')
        except ClientError as e:
            logger.error(f"DynamoDB get_item error: {e}")
            return None