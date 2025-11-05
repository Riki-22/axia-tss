# tests/unit/infrastructure/di/test_container.py
"""
DI Container 単体テスト

対象: src/infrastructure/di/container.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.infrastructure.di.container import DIContainer


class TestDIContainer:
    """DIContainer のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # settingsをモック化
        self.mock_settings = Mock()
        self.mock_settings.dynamodb_table_name = "test-table"
        self.mock_settings.dynamodb_resource = Mock()
        self.mock_settings.mt5_terminal_path = "/path/to/terminal"
        self.mock_settings.mt5_magic_number = 12345
        self.mock_settings.redis = Mock()
        self.mock_settings.redis.redis_endpoint = "localhost"
        self.mock_settings.redis.redis_port = 6379
        self.mock_settings.redis.redis_db = 0
        self.mock_settings.redis.redis_socket_timeout = 5
        self.mock_settings.redis.redis_socket_connect_timeout = 5
        self.mock_settings.redis.redis_retry_on_timeout = True
        self.mock_settings.redis.redis_max_connections = 10
        self.mock_settings.redis.redis_decode_responses = True

    # ========================================
    # 【初期化】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    def test_init(self, mock_settings_module):
        """
        初期化

        条件: DIContainer生成
        期待: 全属性がNoneで初期化される
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings

        # Act
        container = DIContainer()

        # Assert
        assert container._mt5_connection is None
        assert container._order_repository is None
        assert container._kill_switch_repository is None
        assert container._redis_client is None
        assert container._ohlcv_cache is None

    # ========================================
    # 【get_kill_switch_repository】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.DynamoDBKillSwitchRepository')
    def test_get_kill_switch_repository_singleton(self, mock_repo_class, mock_settings_module):
        """
        Kill Switchリポジトリ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        container = DIContainer()

        # Act
        repo1 = container.get_kill_switch_repository()
        repo2 = container.get_kill_switch_repository()

        # Assert
        assert repo1 is repo2
        mock_repo_class.assert_called_once()

    @patch('src.infrastructure.di.container.DynamoDBKillSwitchRepository')
    def test_get_kill_switch_repository_parameters(self, mock_repo_class):
        """
        Kill Switchリポジトリ取得 - パラメータ

        条件: リポジトリ取得
        期待: 正しいパラメータで初期化される
        """
        # Arrange
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        with patch('src.infrastructure.di.container.settings', self.mock_settings):
            container = DIContainer()

            # Act
            container.get_kill_switch_repository()

            # Assert
            mock_repo_class.assert_called_once_with(
                table_name=self.mock_settings.dynamodb_table_name,
                dynamodb_resource=self.mock_settings.dynamodb_resource
            )

    # ========================================
    # 【get_order_repository】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.DynamoDBOrderRepository')
    def test_get_order_repository_singleton(self, mock_repo_class, mock_settings_module):
        """
        Orderリポジトリ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        container = DIContainer()

        # Act
        repo1 = container.get_order_repository()
        repo2 = container.get_order_repository()

        # Assert
        assert repo1 is repo2
        mock_repo_class.assert_called_once()

    @patch('src.infrastructure.di.container.DynamoDBOrderRepository')
    def test_get_order_repository_parameters(self, mock_repo_class):
        """
        Orderリポジトリ取得 - パラメータ

        条件: リポジトリ取得
        期待: 正しいパラメータで初期化される
        """
        # Arrange
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        with patch('src.infrastructure.di.container.settings', self.mock_settings):
            container = DIContainer()

            # Act
            container.get_order_repository()

            # Assert
            mock_repo_class.assert_called_once_with(
                table_name=self.mock_settings.dynamodb_table_name,
                dynamodb_resource=self.mock_settings.dynamodb_resource
            )

    # ========================================
    # 【get_mt5_connection】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.MT5Connection')
    def test_get_mt5_connection_singleton(self, mock_conn_class, mock_settings_module):
        """
        MT5接続取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        self.mock_settings.get_mt5_credentials.return_value = {'user': 'test'}
        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance

        container = DIContainer()

        # Act
        conn1 = container.get_mt5_connection()
        conn2 = container.get_mt5_connection()

        # Assert
        assert conn1 is conn2
        mock_conn_class.assert_called_once()

    @patch('src.infrastructure.di.container.MT5Connection')
    def test_get_mt5_connection_parameters(self, mock_conn_class):
        """
        MT5接続取得 - パラメータ

        条件: 接続取得
        期待: 正しいパラメータで初期化される
        """
        # Arrange
        mock_credentials = {'user': 'test', 'password': 'pass'}
        self.mock_settings.get_mt5_credentials.return_value = mock_credentials
        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance

        with patch('src.infrastructure.di.container.settings', self.mock_settings):
            container = DIContainer()

            # Act
            container.get_mt5_connection()

            # Assert
            mock_conn_class.assert_called_once_with(
                credentials=mock_credentials,
                terminal_path=self.mock_settings.mt5_terminal_path
            )

    # ========================================
    # 【get_mt5_order_executor】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.MT5OrderExecutor')
    @patch('src.infrastructure.di.container.MT5Connection')
    @patch('src.infrastructure.di.container.DynamoDBOrderRepository')
    def test_get_mt5_order_executor(self, mock_order_repo, mock_conn_class,
                                     mock_executor_class):
        """
        MT5注文実行クラス取得

        条件: 実行クラス取得
        期待: 依存関係が正しく注入される
        """
        # Arrange
        self.mock_settings.get_mt5_credentials.return_value = {'user': 'test'}

        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance
        mock_repo_instance = Mock()
        mock_order_repo.return_value = mock_repo_instance
        mock_executor_instance = Mock()
        mock_executor_class.return_value = mock_executor_instance

        with patch('src.infrastructure.di.container.settings', self.mock_settings):
            container = DIContainer()

            # Act
            executor = container.get_mt5_order_executor()

            # Assert
            mock_executor_class.assert_called_once()
            call_kwargs = mock_executor_class.call_args.kwargs
            assert 'connection' in call_kwargs
            assert 'validation_service' in call_kwargs
            assert 'order_repository' in call_kwargs
            assert call_kwargs['magic_number'] == self.mock_settings.mt5_magic_number

    # ========================================
    # 【get_order_validation_service】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.OrderValidationService')
    def test_get_order_validation_service(self, mock_service_class, mock_settings_module):
        """
        注文検証サービス取得

        条件: サービス取得
        期待: 新しいインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        container = DIContainer()

        # Act
        service = container.get_order_validation_service()

        # Assert
        mock_service_class.assert_called_once()

    # ========================================
    # 【get_position_repository】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.DynamoDBPositionRepository')
    def test_get_position_repository_singleton(self, mock_repo_class, mock_settings_module):
        """
        Positionリポジトリ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        container = DIContainer()

        # Act
        repo1 = container.get_position_repository()
        repo2 = container.get_position_repository()

        # Assert
        assert repo1 is repo2
        mock_repo_class.assert_called_once()

    @patch('src.infrastructure.di.container.DynamoDBPositionRepository')
    def test_get_position_repository_parameters(self, mock_repo_class):
        """
        Positionリポジトリ取得 - パラメータ

        条件: リポジトリ取得
        期待: 正しいパラメータで初期化される
        """
        # Arrange
        mock_repo_instance = Mock()
        mock_repo_class.return_value = mock_repo_instance

        with patch('src.infrastructure.di.container.settings', self.mock_settings):
            container = DIContainer()

            # Act
            container.get_position_repository()

            # Assert
            mock_repo_class.assert_called_once_with(
                table_name=self.mock_settings.dynamodb_table_name,
                dynamodb_resource=self.mock_settings.dynamodb_resource
            )

    # ========================================
    # 【get_mt5_price_provider】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.MT5PriceProvider')
    @patch('src.infrastructure.di.container.MT5Connection')
    def test_get_mt5_price_provider_singleton(self, mock_conn_class,
                                               mock_provider_class, mock_settings_module):
        """
        MT5価格プロバイダ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        self.mock_settings.get_mt5_credentials.return_value = {'user': 'test'}

        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance
        mock_provider_instance = Mock()
        mock_provider_class.return_value = mock_provider_instance

        container = DIContainer()

        # Act
        provider1 = container.get_mt5_price_provider()
        provider2 = container.get_mt5_price_provider()

        # Assert
        assert provider1 is provider2
        mock_provider_class.assert_called_once()

    # ========================================
    # 【get_mt5_account_provider】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.MT5AccountProvider')
    @patch('src.infrastructure.di.container.MT5Connection')
    def test_get_mt5_account_provider_singleton(self, mock_conn_class,
                                                 mock_provider_class, mock_settings_module):
        """
        MT5アカウントプロバイダ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        self.mock_settings.get_mt5_credentials.return_value = {'user': 'test'}

        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance
        mock_provider_instance = Mock()
        mock_provider_class.return_value = mock_provider_instance

        container = DIContainer()

        # Act
        provider1 = container.get_mt5_account_provider()
        provider2 = container.get_mt5_account_provider()

        # Assert
        assert provider1 is provider2
        mock_provider_class.assert_called_once()

    # ========================================
    # 【get_mt5_position_provider】1テスト
    # ========================================

    @patch('src.infrastructure.di.container.settings')
    @patch('src.infrastructure.di.container.MT5PositionProvider')
    @patch('src.infrastructure.di.container.MT5Connection')
    def test_get_mt5_position_provider_singleton(self, mock_conn_class,
                                                  mock_provider_class, mock_settings_module):
        """
        MT5ポジションプロバイダ取得 - シングルトン

        条件: 2回呼び出し
        期待: 同じインスタンスを返す
        """
        # Arrange
        mock_settings_module.return_value = self.mock_settings
        self.mock_settings.get_mt5_credentials.return_value = {'user': 'test'}

        mock_conn_instance = Mock()
        mock_conn_class.return_value = mock_conn_instance
        mock_provider_instance = Mock()
        mock_provider_class.return_value = mock_provider_instance

        container = DIContainer()

        # Act
        provider1 = container.get_mt5_position_provider()
        provider2 = container.get_mt5_position_provider()

        # Assert
        assert provider1 is provider2
        mock_provider_class.assert_called_once()


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
