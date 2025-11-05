# tests/unit/infrastructure/gateways/messaging/sqs/test_queue_listener.py
"""
SQS Queue Listener 単体テスト

対象: src/infrastructure/gateways/messaging/sqs/queue_listener.py
"""

import pytest
from unittest.mock import Mock, patch, call
import time

from src.infrastructure.gateways.messaging.sqs.queue_listener import SQSQueueListener


class TestSQSQueueListener:
    """SQSQueueListener のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        self.mock_sqs_client = Mock()
        self.mock_handler = Mock()
        self.listener = SQSQueueListener(
            queue_url=self.queue_url,
            sqs_client=self.mock_sqs_client,
            process_message_handler=self.mock_handler
        )

    # ========================================
    # 【初期化】2テスト
    # ========================================

    def test_init_basic(self):
        """
        初期化 - 基本

        条件: queue_url, sqs_client, handlerを渡す
        期待: 全属性が正しく設定される
        """
        # Arrange & Act
        listener = SQSQueueListener(
            queue_url="https://example.com/queue",
            sqs_client=self.mock_sqs_client,
            process_message_handler=self.mock_handler
        )

        # Assert
        assert listener.queue_url == "https://example.com/queue"
        assert listener.sqs_client == self.mock_sqs_client
        assert listener.process_message_handler == self.mock_handler
        assert listener.running is False

    def test_init_running_false(self):
        """
        初期化 - running フラグ

        条件: 新規インスタンス作成
        期待: running が False で開始
        """
        # Assert
        assert self.listener.running is False

    # ========================================
    # 【バリデーション】2テスト
    # ========================================

    def test_start_polling_no_queue_url(self):
        """
        ポーリング開始 - キューURLなし

        条件: queue_url が空
        期待: エラーログ出力、即座にreturn
        """
        # Arrange
        self.listener.queue_url = None

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        mock_logger.error.assert_called_once_with("SQSキューURLが正しく設定されていません。")
        self.mock_sqs_client.receive_message.assert_not_called()

    def test_start_polling_no_sqs_client(self):
        """
        ポーリング開始 - SQSクライアントなし

        条件: sqs_client が None
        期待: エラーログ出力、即座にreturn
        """
        # Arrange
        self.listener.sqs_client = None

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        mock_logger.error.assert_called_once_with("SQSクライアントが初期化されていません。")

    # ========================================
    # 【メッセージ受信】4テスト
    # ========================================

    def test_receive_message_success(self):
        """
        メッセージ受信 - 成功

        条件: 1件のメッセージ受信
        期待: handlerが呼ばれ、メッセージ削除される
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-123',
            'ReceiptHandle': 'receipt-handle-123',
            'Body': '{"test": "data"}'
        }
        self.mock_sqs_client.receive_message.return_value = {
            'Messages': [test_message]
        }
        self.mock_handler.return_value = True  # 処理成功

        # 1回ループして停止するように設定
        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        self.listener.start_polling()

        # Assert
        self.mock_sqs_client.receive_message.assert_called_once_with(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        self.mock_handler.assert_called_once_with(test_message)
        self.mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl=self.queue_url,
            ReceiptHandle='receipt-handle-123'
        )

    def test_receive_no_messages(self):
        """
        メッセージ受信 - メッセージなし

        条件: 'Messages' キーがないレスポンス
        期待: handlerは呼ばれず、削除もされない
        """
        # Arrange
        self.mock_sqs_client.receive_message.return_value = {}  # No 'Messages' key

        # 1回ループして停止
        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {}
        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        self.listener.start_polling()

        # Assert
        self.mock_sqs_client.receive_message.assert_called_once()
        self.mock_handler.assert_not_called()
        self.mock_sqs_client.delete_message.assert_not_called()

    def test_receive_message_parameters(self):
        """
        メッセージ受信 - パラメータ確認

        条件: start_polling 実行
        期待: 正しいパラメータで receive_message 呼び出し
        """
        # Arrange
        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {}
        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        self.listener.start_polling()

        # Assert
        self.mock_sqs_client.receive_message.assert_called_once_with(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )

    def test_receive_message_with_attributes(self):
        """
        メッセージ受信 - 属性付き

        条件: AttributeNames と MessageAttributeNames 指定
        期待: 'All' で取得される
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-456',
            'ReceiptHandle': 'receipt-456',
            'Body': '{"key": "value"}',
            'Attributes': {'ApproximateReceiveCount': '1'},
            'MessageAttributes': {'custom': {'StringValue': 'test'}}
        }

        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect
        self.mock_handler.return_value = True

        # Act
        self.listener.start_polling()

        # Assert
        call_kwargs = self.mock_sqs_client.receive_message.call_args.kwargs
        assert call_kwargs['AttributeNames'] == ['All']
        assert call_kwargs['MessageAttributeNames'] == ['All']

    # ========================================
    # 【メッセージ処理】4テスト
    # ========================================

    def test_process_message_handler_called(self):
        """
        メッセージ処理 - ハンドラー呼び出し

        条件: メッセージ受信
        期待: process_message_handler が正しいメッセージで呼ばれる
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-789',
            'ReceiptHandle': 'receipt-789',
            'Body': '{"order": "data"}'
        }

        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect
        self.mock_handler.return_value = True

        # Act
        self.listener.start_polling()

        # Assert
        self.mock_handler.assert_called_once_with(test_message)

    def test_message_deleted_on_success(self):
        """
        メッセージ削除 - 処理成功時

        条件: handler が True を返す
        期待: delete_message が呼ばれる
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-success',
            'ReceiptHandle': 'receipt-success',
            'Body': '{}'
        }

        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect
        self.mock_handler.return_value = True  # 処理成功

        # Act
        self.listener.start_polling()

        # Assert
        self.mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl=self.queue_url,
            ReceiptHandle='receipt-success'
        )

    def test_message_not_deleted_on_failure(self):
        """
        メッセージ削除スキップ - 処理失敗時

        条件: handler が False を返す
        期待: delete_message が呼ばれない、警告ログ出力
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-fail',
            'ReceiptHandle': 'receipt-fail',
            'Body': '{}'
        }

        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect
        self.mock_handler.return_value = False  # 処理失敗

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        self.mock_sqs_client.delete_message.assert_not_called()
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert 'メッセージ処理失敗' in warning_message
        assert 'msg-fail' in warning_message

    def test_message_deletion_error_handled(self):
        """
        メッセージ削除エラー - 例外処理

        条件: delete_message が例外を発生
        期待: エラーログ出力、プログラムは継続
        """
        # Arrange
        test_message = {
            'MessageId': 'msg-del-err',
            'ReceiptHandle': 'receipt-del-err',
            'Body': '{}'
        }

        def side_effect(*args, **kwargs):
            self.listener.running = False
            return {'Messages': [test_message]}
        self.mock_sqs_client.receive_message.side_effect = side_effect
        self.mock_handler.return_value = True
        self.mock_sqs_client.delete_message.side_effect = Exception("Delete failed")

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert 'メッセージ削除中にエラー' in error_message

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    def test_keyboard_interrupt_stops_polling(self):
        """
        KeyboardInterrupt 処理

        条件: receive_message が KeyboardInterrupt 発生
        期待: running が False、ループ終了
        """
        # Arrange
        self.mock_sqs_client.receive_message.side_effect = KeyboardInterrupt()

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        assert self.listener.running is False
        mock_logger.info.assert_any_call("停止シグナル受信。メインループを終了します。")

    @patch('src.infrastructure.gateways.messaging.sqs.queue_listener.time.sleep')
    def test_generic_exception_continues_polling(self, mock_sleep):
        """
        一般例外処理 - ポーリング継続

        条件: receive_message が一般例外を発生
        期待: エラーログ、60秒待機、ループ継続
        """
        # Arrange
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("SQS Error")
            else:
                self.listener.running = False
                return {}

        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        with patch('src.infrastructure.gateways.messaging.sqs.queue_listener.logger') as mock_logger:
            self.listener.start_polling()

        # Assert
        mock_logger.critical.assert_called_once()
        critical_message = mock_logger.critical.call_args[0][0]
        assert 'メインループで致命的なエラーが発生' in critical_message
        mock_sleep.assert_called_once_with(60)

    @patch('src.infrastructure.gateways.messaging.sqs.queue_listener.time.sleep')
    def test_exception_sleep_duration(self, mock_sleep):
        """
        例外処理 - 待機時間確認

        条件: receive_message が例外を発生
        期待: 60秒のsleep呼び出し
        """
        # Arrange
        def side_effect(*args, **kwargs):
            self.listener.running = False
            raise Exception("Test exception")

        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        self.listener.start_polling()

        # Assert
        mock_sleep.assert_called_once_with(60)

    # ========================================
    # 【停止メソッド】2テスト
    # ========================================

    def test_stop_method(self):
        """
        停止メソッド - running フラグ

        条件: stop() 呼び出し
        期待: running が False になる
        """
        # Arrange
        self.listener.running = True

        # Act
        self.listener.stop()

        # Assert
        assert self.listener.running is False

    def test_stop_during_polling(self):
        """
        停止メソッド - ポーリング中の停止

        条件: ポーリング中に stop() 呼び出し
        期待: ループが終了する
        """
        # Arrange
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                self.listener.stop()  # 2回目の呼び出しで停止
            return {}

        self.mock_sqs_client.receive_message.side_effect = side_effect

        # Act
        self.listener.start_polling()

        # Assert
        assert self.listener.running is False
        assert call_count[0] == 2  # 2回呼ばれた後に停止


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
