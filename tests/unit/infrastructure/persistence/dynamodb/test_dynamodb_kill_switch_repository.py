# tests/unit/infrastructure/persistence/dynamodb/test_dynamodb_kill_switch_repository.py
"""
DynamoDB Kill Switch Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_kill_switch_repository.py
フォーカス: 例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from src.infrastructure.persistence.dynamodb.dynamodb_kill_switch_repository import DynamoDBKillSwitchRepository


class TestDynamoDBKillSwitchRepository:
    """DynamoDBKillSwitchRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # Mock DynamoDB resource and table
        self.mock_dynamodb = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb.Table.return_value = self.mock_table

        self.table_name = "test-state-table"
        self.repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

    # ========================================
    # 【正常系】3テスト
    # ========================================

    def test_is_active_returns_true_when_on(self):
        """
        Kill Switch ON時にis_active()がTrueを返す

        条件: DynamoDBにstatus='ON'のアイテムが存在
        期待: is_active()=True
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'status': 'ON',
                'last_updated_utc': '2025-01-01T00:00:00Z'
            }
        }

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True

    def test_is_active_returns_false_when_off(self):
        """
        Kill Switch OFF時にis_active()がFalseを返す

        条件: DynamoDBにstatus='OFF'のアイテムが存在
        期待: is_active()=False
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'status': 'OFF',
                'last_updated_utc': '2025-01-01T00:00:00Z'
            }
        }

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is False

    def test_set_with_details_success(self):
        """
        詳細情報付き更新成功

        条件: 有効なパラメータでset_with_details()呼び出し
        期待: set_with_details()=True、DynamoDB put_item呼び出し
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.set_with_details(
            status='ON',
            reason='System maintenance',
            updated_by='admin@example.com'
        )

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数確認
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args.kwargs['Item']
        assert saved_item['status'] == 'ON'
        assert saved_item['reason'] == 'System maintenance'
        assert saved_item['updated_by'] == 'admin@example.com'

    # ========================================
    # 【例外ハンドリング】6テスト
    # ========================================

    def test_is_active_table_not_initialized(self):
        """
        is_active()でテーブル未初期化

        条件: table=None
        期待: is_active()=True（安全のためON扱い）
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True  # 安全のためON扱い

    def test_is_active_dynamodb_exception(self):
        """
        is_active()でDynamoDB例外発生

        条件: table.get_item()でException発生
        期待: is_active()=True（安全のためON扱い）、エラーログ
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB connection timeout")

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True  # エラー時は安全のためON扱い

    def test_is_active_item_not_found(self):
        """
        is_active()でアイテム未設定

        条件: DynamoDBに該当アイテムが存在しない
        期待: is_active()=True（安全のためON扱い）、警告ログ
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # 'Item'キーなし

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True  # 未設定時は安全のためON扱い

    def test_get_status_detail_table_not_initialized(self):
        """
        get_status_detail()でテーブル未初期化

        条件: table=None
        期待: エラーレスポンス返却（status='ERROR'）
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.get_status_detail()

        # Assert
        assert result['status'] == 'ERROR'
        assert 'error' in result

    def test_get_status_detail_dynamodb_exception(self):
        """
        get_status_detail()でDynamoDB例外発生

        条件: table.get_item()でException発生
        期待: エラーレスポンス返却、エラーログ
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB read error")

        # Act
        result = self.repository.get_status_detail()

        # Assert
        assert result['status'] == 'ERROR'
        assert 'error' in result

    def test_set_with_details_table_not_initialized(self):
        """
        set_with_details()でテーブル未初期化

        条件: table=None
        期待: set_with_details()=False
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.set_with_details(status='ON')

        # Assert
        assert result is False

    def test_set_with_details_dynamodb_exception(self):
        """
        set_with_details()でDynamoDB例外発生

        条件: table.put_item()でException発生
        期待: set_with_details()=False、エラーログ
        """
        # Arrange
        self.mock_table.put_item.side_effect = Exception("DynamoDB write error")

        # Act
        result = self.repository.set_with_details(
            status='ON',
            reason='Test',
            updated_by='test@example.com'
        )

        # Assert
        assert result is False

    # ========================================
    # 【統合動作】2テスト
    # ========================================

    def test_activate_calls_update_status(self):
        """
        activate()がset_with_details()を呼び出す

        条件: activate()呼び出し
        期待: set_with_details(status='ON')が実行される
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.activate()

        # Assert
        assert result is True

        # put_itemが呼ばれたことを確認
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args.kwargs['Item']
        assert saved_item['status'] == 'ON'

    def test_deactivate_calls_update_status(self):
        """
        deactivate()がset_with_details()を呼び出す

        条件: deactivate()呼び出し
        期待: set_with_details(status='OFF')が実行される
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.deactivate()

        # Assert
        assert result is True

        # put_itemが呼ばれたことを確認
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args.kwargs['Item']
        assert saved_item['status'] == 'OFF'


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
