# tests/unit/infrastructure/persistence/dynamodb/test_base_repository.py
"""
Base DynamoDB Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/base_repository.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.infrastructure.persistence.dynamodb.base_repository import BaseDynamoDBRepository


class TestBaseDynamoDBRepository:
    """BaseDynamoDBRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.table_name = "test-table"
        self.mock_client = Mock()
        self.mock_resource = Mock()
        self.mock_table = Mock()

    # ========================================
    # 【初期化】3テスト
    # ========================================

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_init_with_client(self, mock_boto3):
        """
        初期化 - クライアント指定

        条件: dynamodb_client を渡す
        期待: 指定したクライアントが使用される
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table

        # Act
        repo = BaseDynamoDBRepository(
            table_name=self.table_name,
            dynamodb_client=self.mock_client
        )

        # Assert
        assert repo.table_name == self.table_name
        assert repo.client == self.mock_client
        mock_boto3.resource.assert_called_once_with('dynamodb')
        self.mock_resource.Table.assert_called_once_with(self.table_name)

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_init_without_client(self, mock_boto3):
        """
        初期化 - クライアント未指定

        条件: dynamodb_client = None
        期待: boto3.client('dynamodb') がデフォルトで使用される
        """
        # Arrange
        mock_boto3.client.return_value = self.mock_client
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table

        # Act
        repo = BaseDynamoDBRepository(table_name=self.table_name)

        # Assert
        assert repo.table_name == self.table_name
        mock_boto3.client.assert_called_once_with('dynamodb')
        mock_boto3.resource.assert_called_once_with('dynamodb')

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_init_table_setup(self, mock_boto3):
        """
        初期化 - テーブルリソース設定

        条件: table_name 指定
        期待: resource.Table(table_name) が呼ばれ、tableに設定される
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table

        # Act
        repo = BaseDynamoDBRepository(
            table_name="my-table",
            dynamodb_client=self.mock_client
        )

        # Assert
        assert repo.table == self.mock_table
        self.mock_resource.Table.assert_called_once_with("my-table")

    # ========================================
    # 【put_item】3テスト
    # ========================================

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_put_item_success(self, mock_boto3):
        """
        アイテム保存 - 成功

        条件: table.put_item が正常終了
        期待: True を返す
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_item = {'id': '123', 'name': 'test'}
        self.mock_table.put_item.return_value = {}

        # Act
        result = repo.put_item(test_item)

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once_with(Item=test_item)

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_put_item_client_error(self, mock_boto3):
        """
        アイテム保存 - ClientError

        条件: table.put_item が ClientError を発生
        期待: False を返す、エラーログ出力
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_item = {'id': '456', 'data': 'value'}
        error_response = {'Error': {'Code': 'ValidationException', 'Message': 'Invalid item'}}
        self.mock_table.put_item.side_effect = ClientError(error_response, 'PutItem')

        # Act
        with patch('src.infrastructure.persistence.dynamodb.base_repository.logger') as mock_logger:
            result = repo.put_item(test_item)

        # Assert
        assert result is False
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert 'DynamoDB put_item error' in error_message

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_put_item_calls_table(self, mock_boto3):
        """
        アイテム保存 - table.put_item 呼び出し確認

        条件: put_item 実行
        期待: table.put_item が正しいパラメータで呼ばれる
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_item = {'pk': 'partition-key', 'sk': 'sort-key', 'attribute': 'value'}

        # Act
        repo.put_item(test_item)

        # Assert
        self.mock_table.put_item.assert_called_once_with(Item=test_item)

    # ========================================
    # 【get_item】4テスト
    # ========================================

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_get_item_success(self, mock_boto3):
        """
        アイテム取得 - 成功

        条件: table.get_item がアイテムを返す
        期待: Item を返す
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_key = {'id': '789'}
        test_item = {'id': '789', 'name': 'retrieved'}
        self.mock_table.get_item.return_value = {'Item': test_item}

        # Act
        result = repo.get_item(test_key)

        # Assert
        assert result == test_item
        self.mock_table.get_item.assert_called_once_with(Key=test_key)

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_get_item_not_found(self, mock_boto3):
        """
        アイテム取得 - 見つからない

        条件: table.get_item が 'Item' キーなしのレスポンス
        期待: None を返す
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_key = {'id': 'not-exists'}
        self.mock_table.get_item.return_value = {}  # No 'Item' key

        # Act
        result = repo.get_item(test_key)

        # Assert
        assert result is None

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_get_item_client_error(self, mock_boto3):
        """
        アイテム取得 - ClientError

        条件: table.get_item が ClientError を発生
        期待: None を返す、エラーログ出力
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_key = {'id': 'error-key'}
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}}
        self.mock_table.get_item.side_effect = ClientError(error_response, 'GetItem')

        # Act
        with patch('src.infrastructure.persistence.dynamodb.base_repository.logger') as mock_logger:
            result = repo.get_item(test_key)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert 'DynamoDB get_item error' in error_message

    @patch('src.infrastructure.persistence.dynamodb.base_repository.boto3')
    def test_get_item_calls_table(self, mock_boto3):
        """
        アイテム取得 - table.get_item 呼び出し確認

        条件: get_item 実行
        期待: table.get_item が正しいキーで呼ばれる
        """
        # Arrange
        mock_boto3.resource.return_value = self.mock_resource
        self.mock_resource.Table.return_value = self.mock_table
        repo = BaseDynamoDBRepository(self.table_name, self.mock_client)

        test_key = {'pk': 'partition-value', 'sk': 'sort-value'}
        self.mock_table.get_item.return_value = {'Item': {'data': 'test'}}

        # Act
        repo.get_item(test_key)

        # Assert
        self.mock_table.get_item.assert_called_once_with(Key=test_key)


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
