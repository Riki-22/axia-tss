# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_connection.py
"""
MT5 Connection 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_connection.py
設計: docs/testing/test_design.md (lines 596-637)
"""

import pytest
from unittest.mock import Mock, patch

from src.infrastructure.gateways.brokers.mt5.mt5_connection import MT5Connection


class TestMT5Connection:
    """MT5Connection のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # 標準認証情報
        self.credentials = {
            'mt5_login': '123456',
            'mt5_password': 'test_password',
            'mt5_server': 'TestServer-Demo'
        }

        self.terminal_path = '/Applications/MetaTrader5.app'

    # ========================================
    # 【正常系】2テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_connect_success(self, mock_mt5):
        """
        MT5接続成功

        条件: 有効な認証情報（login, password, server, terminal_path）
        期待: connect()=True、_connected=True、ログ出力（口座情報含む）
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)

        # MT5初期化成功
        mock_mt5.initialize.return_value = True

        # ターミナル情報Mock
        mock_terminal_info = type('TerminalInfo', (), {
            'name': 'MetaTrader5',
            'build': 3654,
            'connected': True
        })()
        mock_mt5.terminal_info.return_value = mock_terminal_info

        # 口座情報Mock
        mock_account_info = type('AccountInfo', (), {
            'login': 123456,
            'balance': 10000.00
        })()
        mock_mt5.account_info.return_value = mock_account_info

        # Act
        result = connection.connect()

        # Assert
        assert result is True
        assert connection._connected is True

        # MT5初期化が呼ばれたことを確認
        mock_mt5.initialize.assert_called_once_with(
            login=123456,
            password='test_password',
            server='TestServer-Demo',
            timeout=10000,
            path=self.terminal_path
        )

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_ensure_connected_when_already_connected(self, mock_mt5):
        """
        すでに接続済み時のensure_connected

        条件: すでに接続済み（is_connected()=True）
        期待: ensure_connected()=True、再接続は実行されない
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)
        connection._connected = True

        # 接続済み状態を返す
        mock_terminal_info = type('TerminalInfo', (), {'connected': True})()
        mock_mt5.terminal_info.return_value = mock_terminal_info

        # Act
        result = connection.ensure_connected()

        # Assert
        assert result is True
        # 既に接続済みなので、initializeは呼ばれない
        mock_mt5.initialize.assert_not_called()

    # ========================================
    # 【再接続】1テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_ensure_connected_triggers_reconnect(self, mock_mt5):
        """
        未接続時のensure_connected

        条件: 未接続状態（is_connected()=False）
        期待: ensure_connected()がconnect()を呼び出し、再接続実行
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)
        connection._connected = False

        # 最初は未接続、reconnect後は接続成功
        mock_mt5.terminal_info.return_value = None
        mock_mt5.initialize.return_value = True
        mock_mt5.account_info.return_value = type('AccountInfo', (), {
            'login': 123456,
            'balance': 10000.00
        })()

        # Act
        result = connection.ensure_connected()

        # Assert
        assert result is True
        # 再接続のためinitializeが呼ばれたことを確認
        mock_mt5.initialize.assert_called_once()

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    def test_connect_missing_credentials(self):
        """
        認証情報欠落

        条件: credentials=None または空辞書
        期待: connect()=False、エラーログ
        """
        # Test Case 1: None
        connection_none = MT5Connection(None, self.terminal_path)
        result = connection_none.connect()
        assert result is False

        # Test Case 2: Empty dict
        connection_empty = MT5Connection({}, self.terminal_path)
        result = connection_empty.connect()
        assert result is False

    def test_connect_invalid_login(self):
        """
        無効なlogin_id

        条件: login_idが数値に変換不可能（例: 'invalid'）
        期待: connect()=False、エラーログ
        """
        # Arrange
        invalid_credentials = self.credentials.copy()
        invalid_credentials['mt5_login'] = 'invalid_login'  # 数値に変換不可

        connection = MT5Connection(invalid_credentials, self.terminal_path)

        # Act
        result = connection.connect()

        # Assert
        assert result is False

    def test_connect_missing_terminal_path(self):
        """
        terminal_path欠落

        条件: terminal_path=None
        期待: connect()=False、エラーログ
        """
        # Arrange
        connection = MT5Connection(self.credentials, terminal_path=None)

        # Act
        result = connection.connect()

        # Assert
        assert result is False

    # ========================================
    # 【例外ハンドリング強化】5テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_initialize_raises_exception(self, mock_mt5):
        """
        MT5初期化時に例外発生

        条件: mt5.initialize()が例外発生（ライブラリエラー）
        期待: connect()=False、例外ログ
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)

        # initialize時に例外発生
        mock_mt5.initialize.side_effect = Exception("MT5 library initialization failed")

        # Act
        result = connection.connect()

        # Assert
        assert result is False
        assert connection._connected is False

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_terminal_info_raises_exception(self, mock_mt5):
        """
        terminal_info取得時に例外発生

        条件: mt5.terminal_info()が例外発生
        期待: is_connected()=False、例外処理
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)
        connection._connected = True

        # terminal_info取得時に例外発生
        mock_mt5.terminal_info.side_effect = Exception("Failed to get terminal info")

        # Act
        result = connection.is_connected()

        # Assert
        assert result is False

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_account_info_raises_exception(self, mock_mt5):
        """
        account_info取得時に例外発生

        条件: mt5.account_info()が例外発生
        期待: connect()は成功（口座情報取得は後続処理）
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)

        # initialize成功
        mock_mt5.initialize.return_value = True

        mock_terminal_info = type('TerminalInfo', (), {
            'name': 'MetaTrader5',
            'connected': True
        })()
        mock_mt5.terminal_info.return_value = mock_terminal_info

        # account_info取得時に例外発生
        mock_mt5.account_info.side_effect = Exception("Failed to get account info")

        # Act
        result = connection.connect()

        # Assert
        # 接続自体は成功（口座情報取得エラーは警告レベル）
        assert result is True
        assert connection._connected is True

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_connection_timeout_exception(self, mock_mt5):
        """
        接続タイムアウト

        条件: mt5.initialize()でTimeoutError発生
        期待: connect()=False、タイムアウトログ
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)

        # タイムアウト例外
        mock_mt5.initialize.side_effect = TimeoutError("Connection timeout after 10 seconds")

        # Act
        result = connection.connect()

        # Assert
        assert result is False
        assert connection._connected is False

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_connection.mt5')
    def test_network_error_during_connection(self, mock_mt5):
        """
        ネットワークエラー

        条件: mt5.initialize()でOSError発生（ネットワーク不通）
        期待: connect()=False、ネットワークエラーログ
        """
        # Arrange
        connection = MT5Connection(self.credentials, self.terminal_path)

        # ネットワークエラー
        mock_mt5.initialize.side_effect = OSError("Network is unreachable")

        # Act
        result = connection.connect()

        # Assert
        assert result is False
        assert connection._connected is False


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
