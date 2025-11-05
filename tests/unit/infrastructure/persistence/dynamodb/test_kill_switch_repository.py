# tests/unit/infrastructure/persistence/dynamodb/test_kill_switch_repository.py
"""
Kill Switch Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_kill_switch_repository.py
設計: docs/testing/test_design.md (lines 544-593)
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.infrastructure.persistence.dynamodb.dynamodb_kill_switch_repository import DynamoDBKillSwitchRepository


class TestDynamoDBKillSwitchRepository:
    """DynamoDBKillSwitchRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックDynamoDBリソース
        self.mock_dynamodb_resource = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb_resource.Table.return_value = self.mock_table

        # リポジトリインスタンス
        self.table_name = "TSS_Positions"
        self.repository = DynamoDBKillSwitchRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb_resource
        )

        # Kill Switchキー
        self.key = {'pk': 'GLOBALCONFIG', 'sk': 'SETTING#KILL_SWITCH'}

    # ========================================
    # 【正常系】3テスト
    # ========================================

    def test_is_active_returns_true_when_on(self):
        """
        Kill Switch ON時の状態確認

        条件: DynamoDBに status='ON' が保存済み
        期待: is_active()=True、警告ログ出力
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'GLOBALCONFIG',
                'sk': 'SETTING#KILL_SWITCH',
                'status': 'ON',
                'last_updated_utc': '2025-11-05T10:00:00'
            }
        }

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True
        self.mock_table.get_item.assert_called_once_with(Key=self.key)

    def test_activate_success(self):
        """
        Kill Switch有効化

        条件: activate()を実行
        期待: DynamoDBのstatusが'ON'に更新、成功フラグTrue
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.activate()

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数を確認
        call_args = self.mock_table.put_item.call_args[1]
        assert call_args['Item']['status'] == 'ON'
        assert call_args['Item']['pk'] == 'GLOBALCONFIG'
        assert call_args['Item']['sk'] == 'SETTING#KILL_SWITCH'

    def test_deactivate_success(self):
        """
        Kill Switch無効化

        条件: deactivate()を実行
        期待: DynamoDBのstatusが'OFF'に更新、成功フラグTrue
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.deactivate()

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数を確認
        call_args = self.mock_table.put_item.call_args[1]
        assert call_args['Item']['status'] == 'OFF'

    # ========================================
    # 【詳細情報】2テスト
    # ========================================

    def test_get_status_detail_with_reason(self):
        """
        詳細情報取得

        条件: reason, updated_by付きでset_with_details()実行済み
        期待: get_status_detail()で全情報返却（status, last_updated, reason, updated_by）
        """
        # Arrange
        test_timestamp = '2025-11-05T12:00:00'
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'GLOBALCONFIG',
                'sk': 'SETTING#KILL_SWITCH',
                'status': 'ON',
                'last_updated_utc': test_timestamp,
                'reason': 'Emergency stop due to market volatility',
                'updated_by': 'admin@example.com'
            }
        }

        # Act
        result = self.repository.get_status_detail()

        # Assert
        assert result['active'] is True
        assert result['status'] == 'ON'
        assert result['last_updated'] == test_timestamp
        assert result['reason'] == 'Emergency stop due to market volatility'
        assert result['updated_by'] == 'admin@example.com'

    def test_set_with_details_success(self):
        """
        詳細情報付き更新

        条件: status, reason, updated_byを指定してset_with_details()実行
        期待: DynamoDBに全フィールド保存、タイムスタンプ記録
        """
        # Arrange
        self.mock_table.put_item.return_value = {}
        test_reason = 'Planned maintenance'
        test_updated_by = 'operator@example.com'

        # Act
        result = self.repository.set_with_details(
            status='ON',
            reason=test_reason,
            updated_by=test_updated_by
        )

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数を確認
        call_args = self.mock_table.put_item.call_args[1]
        item = call_args['Item']

        assert item['status'] == 'ON'
        assert item['reason'] == test_reason
        assert item['updated_by'] == test_updated_by
        assert 'last_updated_utc' in item
        assert item['item_type'] == 'GlobalSetting'

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    def test_is_active_when_table_not_initialized(self):
        """
        テーブル未初期化時の安全動作

        条件: DynamoDBテーブル未初期化（table=None）
        期待: is_active()=True（安全のため）、エラーログ出力
        """
        # Arrange - テーブル未初期化のリポジトリ
        repo_without_table = DynamoDBKillSwitchRepository(
            table_name="",
            dynamodb_resource=None
        )

        # Act
        result = repo_without_table.is_active()

        # Assert
        assert result is True  # 安全のためON扱い

    def test_is_active_when_item_not_found(self):
        """
        Kill Switchアイテム未登録時の安全動作

        条件: DynamoDBにKill Switchアイテムが存在しない
        期待: is_active()=True（安全のため）、警告ログ出力
        """
        # Arrange - アイテムが存在しない
        self.mock_table.get_item.return_value = {}

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True  # 安全のためON扱い
        self.mock_table.get_item.assert_called_once_with(Key=self.key)

    def test_error_handling_on_dynamodb_failure(self):
        """
        DynamoDB障害時の安全動作

        条件: DynamoDB get_item()で例外発生
        期待: is_active()=True（安全のため）、エラーログ出力
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB connection error")

        # Act
        result = self.repository.is_active()

        # Assert
        assert result is True  # エラー時は安全のためON扱い
        self.mock_table.get_item.assert_called_once_with(Key=self.key)
