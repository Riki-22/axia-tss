# src/infrastructure/persistence/dynamodb/dynamodb_kill_switch_repository.py
import logging
from typing import Optional, Dict
from datetime import datetime
from domain.repositories.kill_switch_repository import IKillSwitchRepository

logger = logging.getLogger(__name__)

class DynamoDBKillSwitchRepository(IKillSwitchRepository):
    """Kill Switch管理のDynamoDBリポジトリ実装"""
    
    def __init__(self, table_name: str, dynamodb_resource):
        self.table_name = table_name
        self.dynamodb_resource = dynamodb_resource
        self.table = dynamodb_resource.Table(table_name) if dynamodb_resource else None
        self.key = {'pk': 'GLOBALCONFIG', 'sk': 'SETTING#KILL_SWITCH'}
    
    def is_active(self) -> bool:
        """Kill Switchの状態を確認"""
        if not self._is_initialized():
            return True  # 安全のためON扱い
        
        try:
            response = self.table.get_item(Key=self.key)
            if 'Item' not in response:
                logger.warning("Kill Switchが未設定。安全のためON扱い")
                return True
            
            status = response['Item'].get('status', 'ON')
            is_on = status == 'ON'
            
            if is_on:
                logger.warning("Kill Switch: ON - 取引停止中")
            else:
                logger.debug("Kill Switch: OFF")
                
            return is_on
            
        except Exception as e:
            logger.error(f"Kill Switch確認エラー: {e}")
            return True  # エラー時は安全のためON扱い
    
    def activate(self) -> bool:
        """Kill Switch有効化"""
        return self._update_status('ON')
    
    def deactivate(self) -> bool:
        """Kill Switch無効化"""
        return self._update_status('OFF')
    
    def get_status_detail(self) -> Dict:
        """詳細情報取得（UI用）"""
        if not self._is_initialized():
            return self._error_response('Table not initialized')
        
        try:
            response = self.table.get_item(Key=self.key)
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'active': item.get('status') == 'ON',
                    'status': item.get('status', 'OFF'),
                    'last_updated': item.get('last_updated_utc', 'N/A'),
                    'reason': item.get('reason'),
                    'updated_by': item.get('updated_by')
                }
            
            # デフォルト値
            return {
                'active': False,
                'status': 'OFF',
                'last_updated': 'N/A',
                'reason': None,
                'updated_by': None
            }
            
        except Exception as e:
            logger.error(f"詳細取得エラー: {e}")
            return self._error_response(str(e))
    
    def set_with_details(
        self, 
        status: str, 
        reason: Optional[str] = None, 
        updated_by: Optional[str] = None
    ) -> bool:
        """詳細情報付き更新"""
        if not self._is_initialized():
            return False
        
        try:
            self.table.put_item(Item={
                **self.key,
                'status': status.upper(),
                'last_updated_utc': datetime.utcnow().isoformat(),
                'reason': reason,
                'updated_by': updated_by or 'streamlit_ui',
                'item_type': 'GlobalSetting'
            })
            logger.info(f"Kill Switch更新: {status.upper()}")
            return True
            
        except Exception as e:
            logger.error(f"更新エラー: {e}")
            return False
    
    # プライベートメソッド
    def _is_initialized(self) -> bool:
        """初期化チェック"""
        if not self.table_name or not self.table:
            logger.error("DynamoDBテーブル未初期化")
            return False
        return True
    
    def _update_status(self, status: str) -> bool:
        """ステータス更新の共通処理"""
        return self.set_with_details(status)
    
    def _error_response(self, error: str) -> Dict:
        """エラー時のレスポンス"""
        return {
            'active': False,
            'status': 'ERROR',
            'last_updated': 'N/A',
            'error': error
        }