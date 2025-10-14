# src/presentation/ui/streamlit/controllers/system_controller.py
import streamlit as st
from typing import Optional, Dict
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.di.container import container
from src.infrastructure.monitoring.connection_checkers import DynamoDBConnectionChecker

class SystemController:
    """システム管理コントローラー"""
    
    def __init__(self):
        try:
            # DIコンテナから取得
            self.kill_switch_repo = container.get_kill_switch_repository()
            
            # 接続チェッカー初期化
            settings = container.settings
            self.db_checker = DynamoDBConnectionChecker(
                table_name=settings.dynamodb_table_name,
                dynamodb_resource=settings.dynamodb_resource
            )
        except Exception as e:
            st.error(f"初期化エラー: {e}")
            # フォールバック用のダミー実装
            self.kill_switch_repo = None
            self.db_checker = None
    
    def test_connection(self) -> Dict:
        """DB接続テスト"""
        if not self.db_checker:
            return {
                'status': 'ERROR',
                'message': '接続チェッカー未初期化',
                'error': 'Initialization failed'
            }
            
        conn_status = self.db_checker.check_connection()
        
        if conn_status.connected:
            return {
                'status': 'SUCCESS',
                'message': 'DynamoDB接続成功',
                'table': conn_status.metadata.get('table_name') if conn_status.metadata else None
            }
        else:
            return {
                'status': 'ERROR',
                'message': 'テーブルアクセス失敗',
                'error': conn_status.error
            }
    
    def get_kill_switch_status(self) -> Dict:
        """Kill Switch状態取得"""
        if not self.kill_switch_repo:
            return {
                'active': False,
                'status': 'UNKNOWN',
                'last_updated': 'N/A',
                'error': 'Repository not initialized'
            }
        return self.kill_switch_repo.get_status_detail()
    
    def set_kill_switch(self, status: str) -> Dict:
        """Kill Switch更新"""
        if not self.kill_switch_repo:
            return {'success': False, 'error': 'Repository not initialized'}
            
        try:
            success = self.kill_switch_repo.set_with_details(
                status=status.upper(),
                updated_by='streamlit_ui'
            )
            
            if success:
                st.cache_data.clear()
                return {'success': True, 'status': status}
            else:
                return {'success': False, 'error': 'Update failed'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

# シングルトン
@st.cache_resource
def get_system_controller() -> SystemController:
    return SystemController()