# tests/unit/infrastructure/gateways/messaging/sqs/test_order_publisher.py
"""
SQS Order Publisher 単体テスト

対象: src/infrastructure/gateways/messaging/sqs/order_publisher.py
設計: docs/testing/test_design.md (lines 480-540)
"""

import pytest
from unittest.mock import Mock, MagicMock
import json

from src.infrastructure.gateways.messaging.sqs.order_publisher import SQSOrderPublisher


class TestSQSOrderPublisher:
    """SQSOrderPublisher のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックSQSクライアント
        self.mock_sqs_client = Mock()
        self.queue_url = "https://sqs.ap-northeast-1.amazonaws.com/123456789/TSS_OrderRequestQueue"

        # プロバイダーインスタンス
        self.publisher = SQSOrderPublisher(self.queue_url, self.mock_sqs_client)

        # 標準注文データ（BUY）
        self.standard_order = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'tp_price': 151.0,
            'sl_price': 149.0,
            'comment': 'Test Order'
        }

    # ========================================
    # 【正常系】3テスト
    # ========================================

    def test_send_order_success(self):
        """
        全フィールド設定での注文送信（正常系）

        条件: 全フィールド設定（BUY注文）
        期待: MessageID返却、SQS送信成功、ログ記録
        """
        # Arrange
        mock_response = {
            'MessageId': 'msg-12345678-abcd-efgh',
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        self.mock_sqs_client.send_message.return_value = mock_response

        # Act
        success, message_id = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is True
        assert message_id == 'msg-12345678-abcd-efgh'

        # SQS送信が呼ばれたことを確認
        self.mock_sqs_client.send_message.assert_called_once()
        call_args = self.mock_sqs_client.send_message.call_args
        assert call_args[1]['QueueUrl'] == self.queue_url

        # メッセージ本文の検証
        sent_body = json.loads(call_args[1]['MessageBody'])
        assert sent_body['symbol'] == 'USDJPY'
        assert sent_body['order_action'] == 'BUY'
        assert sent_body['lot_size'] == 0.1

    def test_send_order_minimal_fields(self):
        """
        必須フィールドのみでの注文送信（正常系）

        条件: 必須フィールドのみ（commentなし）
        期待: オプション省略でも成功
        """
        # Arrange
        minimal_order = {
            'symbol': 'EURUSD',
            'order_action': 'SELL',
            'order_type': 'MARKET',
            'lot_size': 0.05,
            'tp_price': 1.0800,
            'sl_price': 1.0900
        }

        mock_response = {'MessageId': 'msg-minimal-test'}
        self.mock_sqs_client.send_message.return_value = mock_response

        # Act
        success, message_id = self.publisher.send_order(minimal_order)

        # Assert
        assert success is True
        assert message_id == 'msg-minimal-test'
        self.mock_sqs_client.send_message.assert_called_once()

    def test_send_close_order_success(self):
        """
        CLOSE注文の送信（正常系）

        条件: CLOSE注文（order_action='CLOSE', mt5_ticket指定）
        期待: CLOSE専用バリデーション通過、SQS送信成功
        """
        # Arrange
        close_order = {
            'symbol': 'USDJPY',
            'order_action': 'CLOSE',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'mt5_ticket': 12345678,
            'comment': 'Close Position'
        }

        mock_response = {'MessageId': 'msg-close-order'}
        self.mock_sqs_client.send_message.return_value = mock_response

        # Act
        success, message_id = self.publisher.send_order(close_order)

        # Assert
        assert success is True
        assert message_id == 'msg-close-order'

        # CLOSE注文の内容検証
        call_args = self.mock_sqs_client.send_message.call_args
        sent_body = json.loads(call_args[1]['MessageBody'])
        assert sent_body['order_action'] == 'CLOSE'
        assert sent_body['mt5_ticket'] == 12345678

    # ========================================
    # 【バリデーション】5テスト
    # ========================================

    def test_validation_missing_symbol(self):
        """
        symbolフィールド欠落

        条件: symbolフィールド欠落
        期待: バリデーション失敗、エラーログ
        """
        # Arrange
        invalid_order = {
            # 'symbol': 'USDJPY',  # 欠落
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'tp_price': 151.0,
            'sl_price': 149.0
        }

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert "validation failed" in error_msg
        self.mock_sqs_client.send_message.assert_not_called()

    def test_validation_invalid_action(self):
        """
        無効なorder_action

        条件: order_action='INVALID'（BUY/SELL/CLOSE以外）
        期待: バリデーション失敗
        """
        # Arrange
        invalid_order = self.standard_order.copy()
        invalid_order['order_action'] = 'INVALID'

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert "validation failed" in error_msg
        self.mock_sqs_client.send_message.assert_not_called()

    def test_validation_invalid_lot_size(self):
        """
        無効なlot_size

        条件: lot_size=0 または lot_size>10
        期待: バリデーション失敗
        """
        # Test Case 1: lot_size = 0
        invalid_order_zero = self.standard_order.copy()
        invalid_order_zero['lot_size'] = 0

        success, error_msg = self.publisher.send_order(invalid_order_zero)
        assert success is False
        assert "validation failed" in error_msg

        # Test Case 2: lot_size > 10
        invalid_order_large = self.standard_order.copy()
        invalid_order_large['lot_size'] = 15.0

        success, error_msg = self.publisher.send_order(invalid_order_large)
        assert success is False
        assert "validation failed" in error_msg

        self.mock_sqs_client.send_message.assert_not_called()

    def test_validation_negative_price(self):
        """
        無効な価格（負またはゼロ）

        条件: tp_price<=0 または sl_price<=0
        期待: バリデーション失敗
        """
        # Test Case 1: tp_price = 0
        invalid_order_tp = self.standard_order.copy()
        invalid_order_tp['tp_price'] = 0

        success, error_msg = self.publisher.send_order(invalid_order_tp)
        assert success is False
        assert "validation failed" in error_msg

        # Test Case 2: sl_price < 0
        invalid_order_sl = self.standard_order.copy()
        invalid_order_sl['sl_price'] = -10.0

        success, error_msg = self.publisher.send_order(invalid_order_sl)
        assert success is False
        assert "validation failed" in error_msg

        self.mock_sqs_client.send_message.assert_not_called()

    def test_validation_close_missing_mt5_ticket(self):
        """
        CLOSE注文でmt5_ticket欠落

        条件: CLOSE注文でmt5_ticket欠落
        期待: バリデーション失敗（CLOSE注文特有の検証）
        """
        # Arrange
        close_order_no_ticket = {
            'symbol': 'USDJPY',
            'order_action': 'CLOSE',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            # 'mt5_ticket': 12345678,  # 欠落
            'comment': 'Close Position'
        }

        # Act
        success, error_msg = self.publisher.send_order(close_order_no_ticket)

        # Assert
        assert success is False
        assert "validation failed" in error_msg
        self.mock_sqs_client.send_message.assert_not_called()

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    def test_error_sqs_unavailable(self):
        """
        SQSクライアント=None（Mockモード）

        条件: SQSクライアント=None
        期待: Mock MessageID返却、警告ログ
        """
        # Arrange - SQSクライアントなしでPublisher作成
        mock_publisher = SQSOrderPublisher(self.queue_url, None)

        # Act
        success, message_id = mock_publisher.send_order(self.standard_order)

        # Assert
        assert success is True
        assert message_id.startswith('mock-')
        # 実際のSQS送信は呼ばれない（クライアントがNone）

    def test_error_json_serialization(self):
        """
        シリアライズ不可能なデータ

        条件: JSON化できないオブジェクト
        期待: 例外キャッチ、エラーログ
        """
        # Arrange - シリアライズできないオブジェクトを含む注文
        invalid_order = self.standard_order.copy()
        invalid_order['non_serializable'] = object()  # オブジェクトはJSON化不可

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert isinstance(error_msg, str)
        self.mock_sqs_client.send_message.assert_not_called()

    def test_comprehensive_validation(self):
        """
        複数フィールドが不正

        条件: 複数フィールドが不正
        期待: 最初の不正フィールドで失敗
        """
        # Arrange - 複数の不正項目
        invalid_order = {
            # 'symbol': 'USDJPY',  # 欠落 (1)
            'order_action': 'INVALID',  # 不正 (2)
            'order_type': 'MARKET',
            'lot_size': -1,  # 不正 (3)
            'tp_price': 0,  # 不正 (4)
            'sl_price': 149.0
        }

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert "validation failed" in error_msg
        # 最初のエラー（symbol欠落）で失敗すること
        self.mock_sqs_client.send_message.assert_not_called()
