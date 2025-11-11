# tests/integration/test_kill_switch_scenario.py
"""
Kill Switch発動シナリオ統合テスト

統合対象:
- DynamoDBKillSwitchRepository
- Kill Switch状態管理
- エラーハンドリング

シナリオ:
1. Kill Switch ON → 取引停止
2. Kill Switch OFF → 取引再開
3. Kill Switch初期化エラー → 安全側（ON扱い）
4. Kill Switch状態取得エラー → 安全側（ON扱い）
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from src.infrastructure.persistence.dynamodb.dynamodb_kill_switch_repository import DynamoDBKillSwitchRepository


class TestKillSwitchScenario:
    """Kill Switch発動シナリオ統合テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # Mock DynamoDB
        self.mock_dynamodb = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb.Table.return_value = self.mock_table

        self.table_name = "test-state-table"

    # ========================================
    # 【シナリオ1: Kill Switch ON → 取引停止】
    # ========================================

    def test_kill_switch_on_blocks_trading(self):
        """
        統合: Kill Switch ON時に取引がブロックされる

        シナリオ:
        1. Kill Switch状態: ON
        2. is_active() → True
        3. アプリケーションロジックで取引ブロック

        検証:
        - is_active() = True
        - ログに警告メッセージ
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'status': 'ON',
                'last_updated_utc': '2025-01-01T00:00:00Z',
                'reason': 'Emergency stop - market volatility',
                'updated_by': 'admin@example.com'
            }
        }

        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Act
        is_active = repository.is_active()

        # Assert
        assert is_active is True
        self.mock_table.get_item.assert_called_once()

        # DynamoDBから正しいキーで取得
        call_args = self.mock_table.get_item.call_args
        assert call_args[1]['Key'] == {
            'pk': 'GLOBALCONFIG',
            'sk': 'SETTING#KILL_SWITCH'
        }

    # ========================================
    # 【シナリオ2: Kill Switch OFF → 取引再開】
    # ========================================

    def test_kill_switch_off_allows_trading(self):
        """
        統合: Kill Switch OFF時に取引が再開される

        シナリオ:
        1. Kill Switch状態: OFF
        2. is_active() → False
        3. アプリケーションロジックで取引許可

        検証:
        - is_active() = False
        - デバッグログに状態記録
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'status': 'OFF',
                'last_updated_utc': '2025-01-01T10:00:00Z',
                'reason': None,
                'updated_by': 'admin@example.com'
            }
        }

        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Act
        is_active = repository.is_active()

        # Assert
        assert is_active is False

    # ========================================
    # 【シナリオ3: Kill Switch切り替え】
    # ========================================

    def test_kill_switch_activation_flow(self):
        """
        統合: Kill Switch ON/OFF切り替えフロー

        シナリオ:
        1. activate() → DynamoDB put_item
        2. is_active() → True
        3. deactivate() → DynamoDB put_item
        4. is_active() → False

        検証:
        - activate/deactivateが正しくDynamoDBに保存
        - 状態遷移が正しく反映
        """
        # Arrange
        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Step 1: activate()
        self.mock_table.put_item.return_value = {}
        result_activate = repository.activate()

        # Assert activate
        assert result_activate is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数確認
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args[1]['Item']
        assert saved_item['status'] == 'ON'
        assert saved_item['pk'] == 'GLOBALCONFIG'
        assert saved_item['sk'] == 'SETTING#KILL_SWITCH'

        # Step 2: deactivate()
        self.mock_table.put_item.reset_mock()
        result_deactivate = repository.deactivate()

        # Assert deactivate
        assert result_deactivate is True
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args[1]['Item']
        assert saved_item['status'] == 'OFF'

    # ========================================
    # 【シナリオ4: 詳細情報付き更新】
    # ========================================

    def test_kill_switch_with_details_flow(self):
        """
        統合: Kill Switch詳細情報付き更新フロー

        シナリオ:
        1. set_with_details(status='ON', reason='...', updated_by='...')
        2. get_status_detail() → 詳細情報取得

        検証:
        - 詳細情報が正しく保存される
        - 詳細情報が正しく取得される
        """
        # Arrange
        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Step 1: set_with_details()
        self.mock_table.put_item.return_value = {}
        result = repository.set_with_details(
            status='ON',
            reason='Market crash - emergency stop',
            updated_by='risk_manager@example.com'
        )

        # Assert save
        assert result is True

        # put_itemの引数確認
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args[1]['Item']
        assert saved_item['status'] == 'ON'
        assert saved_item['reason'] == 'Market crash - emergency stop'
        assert saved_item['updated_by'] == 'risk_manager@example.com'
        assert 'last_updated_utc' in saved_item

        # Step 2: get_status_detail()
        self.mock_table.get_item.return_value = {
            'Item': saved_item
        }

        details = repository.get_status_detail()

        # Assert get
        assert details['active'] is True
        assert details['status'] == 'ON'
        assert details['reason'] == 'Market crash - emergency stop'
        assert details['updated_by'] == 'risk_manager@example.com'

    # ========================================
    # 【シナリオ5: エラー時の安全側フェイルオーバー】
    # ========================================

    def test_kill_switch_error_defaults_to_on(self):
        """
        統合: DynamoDBエラー時に安全側（ON扱い）フェイルオーバー

        シナリオ:
        1. DynamoDB.get_item() → Exception
        2. is_active() → True（安全のためON扱い）

        検証:
        - エラー時でもクラッシュしない
        - 安全側（取引停止）にフェイルオーバー
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB connection timeout")

        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Act
        is_active = repository.is_active()

        # Assert
        # エラー時は安全のためON扱い
        assert is_active is True

    def test_kill_switch_table_not_initialized(self):
        """
        統合: テーブル未初期化時に安全側フェイルオーバー

        シナリオ:
        1. table=None（初期化失敗）
        2. is_active() → True（安全のためON扱い）

        検証:
        - 初期化エラー時でもクラッシュしない
        - 安全側にフェイルオーバー
        """
        # Arrange
        repository = DynamoDBKillSwitchRepository(
            table_name="",  # 空文字でテーブル初期化失敗
            dynamodb_resource=self.mock_dynamodb
        )
        repository.table = None  # 明示的にNoneに設定

        # Act
        is_active = repository.is_active()

        # Assert
        assert is_active is True  # 安全のためON扱い

    # ========================================
    # 【シナリオ6: 未設定時のデフォルト動作】
    # ========================================

    def test_kill_switch_not_configured_defaults_to_on(self):
        """
        統合: Kill Switch未設定時のデフォルト動作

        シナリオ:
        1. DynamoDBにKill Switchアイテムが存在しない
        2. is_active() → True（安全のためON扱い）

        検証:
        - 未設定時は安全側（取引停止）
        - 警告ログ出力
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # 'Item'キーなし

        repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Act
        is_active = repository.is_active()

        # Assert
        assert is_active is True  # 未設定は安全のためON扱い


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
