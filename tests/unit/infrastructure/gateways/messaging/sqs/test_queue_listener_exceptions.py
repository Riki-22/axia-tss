# tests/unit/infrastructure/gateways/messaging/sqs/test_queue_listener_exceptions.py
"""
SQS Queue Listener 例外ハンドリングテスト

対象: src/infrastructure/gateways/messaging/sqs/queue_listener.py
フォーカス: 例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock, call
from botocore.exceptions import ClientError

from src.infrastructure.gateways.messaging.sqs.queue_listener import SQSQueueListener


class TestSQSQueueListenerExceptions:
    """SQSQueueListener の例外ハンドリングテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックSQSクライアント
        self.mock_sqs_client = Mock()
        self.queue_url = "https://sqs.ap-northeast-1.amazonaws.com/123456789/TSS_OrderRequestQueue"

        # モックメッセージハンドラ
        self.mock_handler = Mock(return_value=True)

        # リスナーインスタンス
        self.listener = SQSQueueListener(
            queue_url=self.queue_url,
            sqs_client=self.mock_sqs_client,
            process_message_handler=self.mock_handler
        )

    # ========================================
    # 【正常系】2テスト
    # ========================================

    def test_start_polling_with_message(self):
        """
        メッセージ受信と処理成功

        条件: 1件メッセージ受信、処理成功
        期待: ハンドラ呼び出し、メッセージ削除
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-123',
            'ReceiptHandle': 'receipt-abc',
            'Body': '{"symbol": "USDJPY"}'
        }

        # 1回目: メッセージあり、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            {'Messages': [test_message]},
            KeyboardInterrupt()
        ]

        # Act
        self.listener.start_polling()

        # Assert
        # ハンドラが呼ばれた
        self.mock_handler.assert_called_once_with(test_message)
        # メッセージ削除が呼ばれた
        self.mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl=self.queue_url,
            ReceiptHandle='receipt-abc'
        )

    def test_stop_method(self):
        """
        stop()でポーリング停止

        条件: stop()呼び出し
        期待: running=False
        """
        # Act
        self.listener.stop()

        # Assert
        assert self.listener.running is False

    # ========================================
    # 【初期化エラー】2テスト
    # ========================================

    def test_start_polling_missing_queue_url(self):
        """
        queue_url未設定

        条件: queue_url=""
        期待: エラーログ、ポーリング開始しない
        """
        # Arrange
        listener_no_url = SQSQueueListener(
            queue_url="",
            sqs_client=self.mock_sqs_client,
            process_message_handler=self.mock_handler
        )

        # Act
        listener_no_url.start_polling()

        # Assert
        # receive_messageは呼ばれない
        self.mock_sqs_client.receive_message.assert_not_called()

    def test_start_polling_missing_sqs_client(self):
        """
        sqs_client未設定

        条件: sqs_client=None
        期待: エラーログ、ポーリング開始しない
        """
        # Arrange
        listener_no_client = SQSQueueListener(
            queue_url=self.queue_url,
            sqs_client=None,
            process_message_handler=self.mock_handler
        )

        # Act
        listener_no_client.start_polling()

        # Assert
        # ポーリングが開始されない
        assert listener_no_client.running is False

    # ========================================
    # 【メッセージ処理例外】5テスト
    # ========================================

    def test_receive_message_client_error(self):
        """
        receive_message()でClientError例外

        条件: receive_message()でAccessDenied発生
        期待: 例外キャッチ、60秒待機、ポーリング継続
        """
        # Arrange
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User is not authorized'
            }
        }

        # 1回目: ClientError、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            ClientError(error_response, 'ReceiveMessage'),
            KeyboardInterrupt()
        ]

        # time.sleep()をモック化して待機時間をスキップ
        import src.infrastructure.gateways.messaging.sqs.queue_listener as listener_module
        import time
        original_sleep = time.sleep
        listener_module.time.sleep = Mock()

        try:
            # Act
            self.listener.start_polling()

            # Assert
            # 60秒待機が呼ばれた
            listener_module.time.sleep.assert_called_with(60)
        finally:
            # Cleanup
            listener_module.time.sleep = original_sleep

    def test_receive_message_generic_exception(self):
        """
        receive_message()で一般Exception例外

        条件: receive_message()でException発生
        期待: 例外キャッチ、60秒待機、ポーリング継続
        """
        # Arrange
        # 1回目: Exception、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            Exception("Network timeout"),
            KeyboardInterrupt()
        ]

        # time.sleep()をモック化
        import src.infrastructure.gateways.messaging.sqs.queue_listener as listener_module
        import time
        original_sleep = time.sleep
        listener_module.time.sleep = Mock()

        try:
            # Act
            self.listener.start_polling()

            # Assert
            listener_module.time.sleep.assert_called_with(60)
        finally:
            # Cleanup
            listener_module.time.sleep = original_sleep

    def test_message_handler_returns_false(self):
        """
        ハンドラがFalseを返す

        条件: process_message_handler()がFalse返却
        期待: メッセージ削除スキップ、警告ログ
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-123',
            'ReceiptHandle': 'receipt-abc',
            'Body': '{"symbol": "USDJPY"}'
        }

        # ハンドラがFalseを返す
        self.mock_handler.return_value = False

        # 1回目: メッセージあり、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            {'Messages': [test_message]},
            KeyboardInterrupt()
        ]

        # Act
        self.listener.start_polling()

        # Assert
        # ハンドラは呼ばれた
        self.mock_handler.assert_called_once()
        # メッセージ削除は呼ばれない
        self.mock_sqs_client.delete_message.assert_not_called()

    def test_delete_message_exception(self):
        """
        delete_message()で例外発生

        条件: delete_message()でClientError発生
        期待: 例外キャッチ、エラーログ、ポーリング継続
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-123',
            'ReceiptHandle': 'receipt-abc',
            'Body': '{"symbol": "USDJPY"}'
        }

        error_response = {
            'Error': {
                'Code': 'ReceiptHandleIsInvalid',
                'Message': 'The receipt handle is invalid'
            }
        }

        self.mock_sqs_client.delete_message.side_effect = ClientError(error_response, 'DeleteMessage')

        # 1回目: メッセージあり、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            {'Messages': [test_message]},
            KeyboardInterrupt()
        ]

        # Act
        self.listener.start_polling()

        # Assert
        # delete_messageは呼ばれた（例外発生）
        self.mock_sqs_client.delete_message.assert_called_once()
        # ハンドラは呼ばれた
        self.mock_handler.assert_called_once()

    def test_keyboard_interrupt(self):
        """
        KeyboardInterruptで停止

        条件: receive_message()でKeyboardInterrupt発生
        期待: running=False、ループ終了
        """
        # Arrange
        self.mock_sqs_client.receive_message.side_effect = KeyboardInterrupt()

        # Act
        self.listener.start_polling()

        # Assert
        assert self.listener.running is False

    # ========================================
    # 【メッセージなし】1テスト
    # ========================================

    def test_no_messages_received(self):
        """
        メッセージなし

        条件: receive_message()が空レスポンス
        期待: デバッグログ、ポーリング継続
        """
        # Arrange
        # 1回目: メッセージなし、2回目: KeyboardInterruptで終了
        self.mock_sqs_client.receive_message.side_effect = [
            {},  # 'Messages'キーなし
            KeyboardInterrupt()
        ]

        # Act
        self.listener.start_polling()

        # Assert
        # ハンドラは呼ばれない
        self.mock_handler.assert_not_called()
        # メッセージ削除も呼ばれない
        self.mock_sqs_client.delete_message.assert_not_called()


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
