# tests/unit/application/use_cases/order_processing/test_process_sqs_order_close.py
"""
Process SQS Order (CLOSE処理) 単体テスト

対象: src/application/use_cases/order_processing/process_sqs_order.py (_execute_close_order)
設計: docs/testing/test_design.md (lines 428-477)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

from src.application.use_cases.order_processing.process_sqs_order import ProcessSQSOrderUseCase


class TestProcessSQSOrderClose:
    """ProcessSQSOrderUseCase のCLOSE注文処理テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モック依存関係
        self.mock_kill_switch_repo = Mock()
        self.mock_mt5_connection = Mock()
        self.mock_mt5_order_executor = Mock()
        self.mock_settings = Mock()

        # ユースケースインスタンス
        self.use_case = ProcessSQSOrderUseCase(
            kill_switch_repository=self.mock_kill_switch_repo,
            mt5_connection=self.mock_mt5_connection,
            mt5_order_executor=self.mock_mt5_order_executor,
            settings=self.mock_settings
        )

        # 標準CLOSEペイロード
        self.close_payload = {
            'order_action': 'CLOSE',
            'mt5_ticket': 12345678,
            'lot_size': 0.1,
            'symbol': 'USDJPY',
            'comment': 'Test Close'
        }

        # MT5認証情報
        self.credentials = {
            'login': 123456,
            'password': 'test_pass',
            'server': 'TestServer'
        }

    # ========================================
    # 【正常系】3テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    def test_execute_close_order_success(self, mock_container):
        """
        CLOSE注文実行（正常系）

        条件: 有効なCLOSEペイロード
        期待: 決済成功、Position更新
        """
        # Arrange
        # Position Provider Mock
        mock_position_provider = Mock()
        mock_position_provider.close_position.return_value = (True, None)
        mock_position_provider.get_position_by_ticket.return_value = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'volume': 0.1,
            'profit': 1000.0
        }

        # Position Repository Mock
        mock_position_repo = Mock()
        mock_existing_position = Mock()
        mock_existing_position.unrealized_pnl = 1000.0
        mock_position_repo.find_by_mt5_ticket.return_value = mock_existing_position

        # Container Mock
        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            self.close_payload,
            self.credentials
        )

        # Assert
        assert success is True
        assert result is not None
        assert hasattr(result, 'order')
        assert result.order == 12345678

        # MT5決済が呼ばれたことを確認
        mock_position_provider.close_position.assert_called_once_with(
            ticket=12345678,
            volume=0.1
        )

        # DynamoDB更新が呼ばれたことを確認
        mock_position_repo.update_status.assert_called_once()

    @patch('src.infrastructure.di.container.container')
    def test_execute_close_order_partial(self, mock_container):
        """
        部分決済（正常系）

        条件: 部分決済（lot_size < 保有量）
        期待: 部分決済成功、残ポジション維持
        """
        # Arrange
        partial_payload = self.close_payload.copy()
        partial_payload['lot_size'] = 0.05  # 保有0.1のうち0.05だけ決済

        mock_position_provider = Mock()
        mock_position_provider.close_position.return_value = (True, None)
        mock_position_provider.get_position_by_ticket.return_value = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'volume': 0.1,
            'profit': 500.0
        }

        mock_position_repo = Mock()
        mock_existing_position = Mock()
        mock_existing_position.unrealized_pnl = 500.0
        mock_position_repo.find_by_mt5_ticket.return_value = mock_existing_position

        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            partial_payload,
            self.credentials
        )

        # Assert
        assert success is True
        # 部分決済のvolume=0.05が使用されたことを確認
        mock_position_provider.close_position.assert_called_once_with(
            ticket=12345678,
            volume=0.05
        )

    @patch('src.domain.entities.position.Position')
    @patch('src.infrastructure.di.container.container')
    def test_execute_close_order_db_save(self, mock_container, mock_position_class):
        """
        初回決済（DynamoDB未登録ポジション）

        条件: DynamoDB未登録ポジション
        期待: MT5→DynamoDB保存→決済実行
        """
        # Arrange
        mock_position_provider = Mock()
        mock_position_provider.get_position_by_ticket.return_value = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'volume': 0.1,
            'profit': 1000.0
        }
        mock_position_provider.close_position.return_value = (True, None)

        # Position Repository: 最初はNone、保存後に見つかる
        mock_position_repo = Mock()
        mock_position_repo.find_by_mt5_ticket.side_effect = [None, Mock(unrealized_pnl=1000.0)]

        # Position Entity Mock
        mock_position_entity = Mock()
        mock_position_entity.position_id = 'pos-12345'
        mock_position_class.from_mt5_position.return_value = mock_position_entity

        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            self.close_payload,
            self.credentials
        )

        # Assert
        assert success is True

        # MT5からポジション取得→DynamoDB保存が呼ばれたことを確認
        mock_position_provider.get_position_by_ticket.assert_called_once_with(12345678)
        mock_position_class.from_mt5_position.assert_called_once()
        mock_position_repo.save.assert_called_once_with(mock_position_entity)

    # ========================================
    # 【バリデーション】3テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    def test_validation_missing_mt5_ticket(self, mock_container):
        """
        mt5_ticket未指定

        条件: mt5_ticket未指定
        期待: エラーハンドリング
        """
        # Arrange
        invalid_payload = {
            'order_action': 'CLOSE',
            # 'mt5_ticket': 12345678,  # 欠落
            'lot_size': 0.1,
            'symbol': 'USDJPY'
        }

        mock_position_provider = Mock()
        mock_position_repo = Mock()
        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            invalid_payload,
            self.credentials
        )

        # Assert
        # mt5_ticketがNoneの場合、処理は失敗する
        assert success is False or result is None

    @patch('src.infrastructure.di.container.container')
    def test_validation_invalid_lot_size(self, mock_container):
        """
        無効なlot_size

        条件: 負のlot_size
        期待: MT5側でバリデーションエラー
        """
        # Arrange
        invalid_payload = self.close_payload.copy()
        invalid_payload['lot_size'] = -0.1  # 負の値

        mock_position_provider = Mock()
        # MT5が負のlot_sizeを拒否
        mock_position_provider.close_position.return_value = (False, "Invalid volume")
        mock_position_provider.get_position_by_ticket.return_value = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'volume': 0.1
        }

        mock_position_repo = Mock()
        mock_position_repo.find_by_mt5_ticket.return_value = Mock()

        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            invalid_payload,
            self.credentials
        )

        # Assert
        assert success is False

    @patch('src.infrastructure.di.container.container')
    def test_validation_position_not_found(self, mock_container):
        """
        存在しないチケット番号

        条件: 存在しないチケット番号
        期待: エラーハンドリング
        """
        # Arrange
        mock_position_provider = Mock()
        mock_position_provider.get_position_by_ticket.return_value = None  # ポジション見つからず
        mock_position_provider.close_position.return_value = (False, "Position not found")

        mock_position_repo = Mock()
        mock_position_repo.find_by_mt5_ticket.return_value = None

        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # Act
        success, result = self.use_case._execute_close_order(
            self.close_payload,
            self.credentials
        )

        # Assert
        assert success is False

    # ========================================
    # 【SQS統一アーキテクチャ】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    def test_close_order_sqs_flow_complete(self, mock_container):
        """
        SQS→Process→MT5→DynamoDB エンドツーエンド

        条件: 完全なSQSフロー
        期待: エンドツーエンド成功
        """
        # Arrange
        # Kill Switch OFF
        self.mock_kill_switch_repo.is_active.return_value = False

        # MT5認証情報
        self.mock_settings.get_mt5_credentials.return_value = self.credentials

        # MT5接続成功
        self.mock_mt5_connection.connect.return_value = True

        # Position Provider Mock
        mock_position_provider = Mock()
        mock_position_provider.close_position.return_value = (True, None)
        mock_position_provider.get_position_by_ticket.return_value = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'volume': 0.1,
            'profit': 1000.0
        }

        # Position Repository Mock
        mock_position_repo = Mock()
        mock_existing_position = Mock()
        mock_existing_position.unrealized_pnl = 1000.0
        mock_position_repo.find_by_mt5_ticket.return_value = mock_existing_position

        mock_container.get_mt5_position_provider.return_value = mock_position_provider
        mock_container.get_position_repository.return_value = mock_position_repo

        # SQSメッセージ
        sqs_message = {
            'MessageId': 'msg-test-123',
            'Body': json.dumps(self.close_payload)
        }

        # Act
        message_deleted = self.use_case.execute(sqs_message)

        # Assert
        assert message_deleted is True
        mock_position_provider.close_position.assert_called_once()
        mock_position_repo.update_status.assert_called_once()

    def test_close_order_kill_switch_check(self):
        """
        Kill Switch確認

        条件: Kill Switch有効
        期待: 処理ブロック、メッセージ削除
        """
        # Arrange
        # Kill Switch ON
        self.mock_kill_switch_repo.is_active.return_value = True

        # SQSメッセージ
        sqs_message = {
            'MessageId': 'msg-test-kill-switch',
            'Body': json.dumps(self.close_payload)
        }

        # Act
        message_deleted = self.use_case.execute(sqs_message)

        # Assert
        assert message_deleted is True

        # MT5接続や注文実行は呼ばれないことを確認
        self.mock_mt5_connection.connect.assert_not_called()
