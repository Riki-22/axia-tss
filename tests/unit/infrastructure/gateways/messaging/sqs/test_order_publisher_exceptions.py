# tests/unit/infrastructure/gateways/messaging/sqs/test_order_publisher_exceptions.py
"""
SQS Order Publisher 例外ハンドリングテスト

対象: src/infrastructure/gateways/messaging/sqs/order_publisher.py
フォーカス: 追加の例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock
from botocore.exceptions import ClientError

from src.infrastructure.gateways.messaging.sqs.order_publisher import SQSOrderPublisher


class TestSQSOrderPublisherExceptions:
    """SQSOrderPublisher の例外ハンドリングテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックSQSクライアント
        self.mock_sqs_client = Mock()
        self.queue_url = "https://sqs.ap-northeast-1.amazonaws.com/123456789/TSS_OrderRequestQueue"
        self.publisher = SQSOrderPublisher(self.queue_url, self.mock_sqs_client)

        # 標準注文データ
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
    # 【SQS例外ハンドリング】5テスト
    # ========================================

    def test_send_message_client_error_access_denied(self):
        """
        send_message()でAccessDenied例外

        条件: send_message()でAccessDenied ClientError発生
        期待: send_order()=(False, エラーメッセージ)、エラーログ
        """
        # Arrange
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User is not authorized to perform sqs:SendMessage'
            }
        }
        self.mock_sqs_client.send_message.side_effect = ClientError(error_response, 'SendMessage')

        # Act
        success, error_msg = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is False
        assert 'AccessDenied' in error_msg or 'not authorized' in error_msg

    def test_send_message_client_error_queue_not_found(self):
        """
        send_message()でQueueDoesNotExist例外

        条件: send_message()でQueueDoesNotExist ClientError発生
        期待: send_order()=(False, エラーメッセージ)、エラーログ
        """
        # Arrange
        error_response = {
            'Error': {
                'Code': 'AWS.SimpleQueueService.NonExistentQueue',
                'Message': 'The specified queue does not exist'
            }
        }
        self.mock_sqs_client.send_message.side_effect = ClientError(error_response, 'SendMessage')

        # Act
        success, error_msg = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is False
        assert 'NonExistentQueue' in error_msg or 'does not exist' in error_msg

    def test_send_message_generic_exception(self):
        """
        send_message()で一般Exception例外

        条件: send_message()でException発生
        期待: send_order()=(False, エラーメッセージ)、エラーログ
        """
        # Arrange
        self.mock_sqs_client.send_message.side_effect = Exception("Network timeout")

        # Act
        success, error_msg = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is False
        assert 'Network timeout' in error_msg

    def test_send_message_no_message_id_returned(self):
        """
        send_message()でMessageIdなし

        条件: send_message()成功だがMessageIdがNone
        期待: send_order()=(False, エラーメッセージ)
        """
        # Arrange
        self.mock_sqs_client.send_message.return_value = {
            # 'MessageId': 'msg-xxx',  # 欠落
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }

        # Act
        success, error_msg = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is False
        assert 'No MessageId' in error_msg

    def test_send_message_timeout_exception(self):
        """
        send_message()でTimeout例外

        条件: send_message()でTimeoutError発生
        期待: send_order()=(False, エラーメッセージ)
        """
        # Arrange
        self.mock_sqs_client.send_message.side_effect = TimeoutError("Request timed out after 30 seconds")

        # Act
        success, error_msg = self.publisher.send_order(self.standard_order)

        # Assert
        assert success is False
        assert 'timed out' in error_msg

    # ========================================
    # 【バリデーション追加】3テスト
    # ========================================

    def test_validation_invalid_symbol_type(self):
        """
        symbolの型が不正

        条件: symbol=123（文字列でない）
        期待: バリデーション失敗
        """
        # Arrange
        invalid_order = self.standard_order.copy()
        invalid_order['symbol'] = 123  # 数値（文字列でない）

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert 'validation failed' in error_msg

    def test_validation_empty_symbol(self):
        """
        symbol空文字列

        条件: symbol=""
        期待: バリデーション失敗
        """
        # Arrange
        invalid_order = self.standard_order.copy()
        invalid_order['symbol'] = ""

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert 'validation failed' in error_msg

    def test_validation_invalid_lot_size_type(self):
        """
        lot_sizeの型が不正

        条件: lot_size="invalid"（数値に変換不可）
        期待: バリデーション失敗
        """
        # Arrange
        invalid_order = self.standard_order.copy()
        invalid_order['lot_size'] = "invalid_string"

        # Act
        success, error_msg = self.publisher.send_order(invalid_order)

        # Assert
        assert success is False
        assert 'validation failed' in error_msg


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
