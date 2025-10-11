# src/infrastructure/persistence/dynamodb/kill_switch_repository.py
import logging
from typing import Optional
from src.domain.repositories.kill_switch_repository import IKillSwitchRepository

logger = logging.getLogger(__name__)

class DynamoDBKillSwitchRepository(IKillSwitchRepository):
    """Kill Switch管理のDynamoDBリポジトリ実装"""
    
    def __init__(self, table_name: str, dynamodb_resource):
        self.table_name = table_name
        self.dynamodb_resource = dynamodb_resource
        self.table = dynamodb_resource.Table(table_name) if dynamodb_resource else None
    
    def is_active(self) -> bool:
        """DynamoDBからKill Switchの状態を確認する"""
        if not self.table_name:
            logger.error("DYNAMODB_STATE_TABLE_NAME 環境変数が設定されていません。安全のためキルスイッチONとして扱います。")
            return True
        
        if not self.table:
            logger.error("DynamoDBクライアントが初期化されていません。安全のためキルスイッチONとして扱います。")
            return True
        
        try:
            key = {'pk': 'GLOBALCONFIG', 'sk': 'SETTING#KILL_SWITCH'}
            logger.info(f"DynamoDBテーブル '{self.table_name}' からキルスイッチの状態を取得します... Key: {key}")
            
            response = self.table.get_item(Key=key)
            
            if 'Item' in response:
                item = response['Item']
                logger.info(f"キルスイッチアイテムが見つかりました: {item}")
                item_status = item.get('status')
                
                if item_status == 'ON':
                    logger.warning("グローバルキルスイッチがONです。注文関連処理をスキップします。")
                    return True
                elif item_status == 'OFF':
                    logger.info("グローバルキルスイッチはOFFです。処理を継続します。")
                    return False
                else:
                    logger.warning(f"'kill_switch' アイテムの 'status' 属性が無効な値('{item_status}')です。")
                    return True
            else:
                logger.warning(f"'kill_switch' アイテムが見つかりません。安全のため注文処理をスキップします。")
                return True
                
        except Exception as e:
            logger.error(f"DynamoDBからのキルスイッチ状態取得中にエラー: {e}", exc_info=True)
            return True
    
    def activate(self) -> bool:
        """Kill Switchを有効化"""
        try:
            self.table.put_item(Item={
                'pk': 'GLOBALCONFIG',
                'sk': 'SETTING#KILL_SWITCH',
                'status': 'ON'
            })
            return True
        except Exception as e:
            logger.error(f"Kill Switch有効化エラー: {e}")
            return False
    
    def deactivate(self) -> bool:
        """Kill Switchを無効化"""
        try:
            self.table.put_item(Item={
                'pk': 'GLOBALCONFIG',
                'sk': 'SETTING#KILL_SWITCH', 
                'status': 'OFF'
            })
            return True
        except Exception as e:
            logger.error(f"Kill Switch無効化エラー: {e}")
            return False