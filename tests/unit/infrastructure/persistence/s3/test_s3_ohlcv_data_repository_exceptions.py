# tests/unit/infrastructure/persistence/s3/test_s3_ohlcv_data_repository_exceptions.py
"""
S3 OHLCV Data Repository 例外ハンドリングテスト

対象: src/infrastructure/persistence/s3/s3_ohlcv_data_repository.py
フォーカス: 例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime
import pytz
from botocore.exceptions import ClientError

from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository


class TestS3OhlcvDataRepositoryExceptions:
    """S3OhlcvDataRepository の例外ハンドリングテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # Mock S3 client
        self.mock_s3_client = Mock()
        self.bucket_name = "test-bucket"
        self.repository = S3OhlcvDataRepository(
            bucket_name=self.bucket_name,
            s3_client=self.mock_s3_client
        )

        # Sample DataFrame
        self.sample_df = pd.DataFrame({
            'timestamp_utc': [
                datetime(2025, 1, 1, 12, 0, tzinfo=pytz.UTC),
                datetime(2025, 1, 1, 13, 0, tzinfo=pytz.UTC)
            ],
            'open': [150.0, 150.5],
            'high': [150.5, 151.0],
            'low': [149.5, 150.0],
            'close': [150.2, 150.8],
            'volume': [1000, 1500]
        })

    # ========================================
    # 【正常系】2テスト
    # ========================================

    def test_save_ohlcv_success(self):
        """
        データ保存成功

        条件: 有効なDataFrame、S3 put_object成功
        期待: save_ohlcv()=True
        """
        # Arrange
        self.mock_s3_client.put_object.return_value = {}

        # Act
        result = self.repository.save_ohlcv(self.sample_df, 'USDJPY', 'H1')

        # Assert
        assert result is True
        self.mock_s3_client.put_object.assert_called_once()

    def test_exists_success(self):
        """
        データ存在確認成功

        条件: Parquetファイルが存在
        期待: exists()=True
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=01/day=01/test.parquet'}
            ]
        }

        # Act
        result = self.repository.exists('USDJPY', 'H1', datetime(2025, 1, 1, tzinfo=pytz.UTC))

        # Assert
        assert result is True

    # ========================================
    # 【例外ハンドリング】12テスト
    # ========================================

    def test_save_ohlcv_empty_dataframe(self):
        """
        save_ohlcv()で空DataFrame

        条件: 空のDataFrame
        期待: save_ohlcv()=False、put_object呼ばれない
        """
        # Arrange
        empty_df = pd.DataFrame()

        # Act
        result = self.repository.save_ohlcv(empty_df, 'USDJPY', 'H1')

        # Assert
        assert result is False
        self.mock_s3_client.put_object.assert_not_called()

    def test_save_ohlcv_none_dataframe(self):
        """
        save_ohlcv()でNone DataFrame

        条件: DataFrame=None
        期待: save_ohlcv()=False、put_object呼ばれない
        """
        # Act
        result = self.repository.save_ohlcv(None, 'USDJPY', 'H1')

        # Assert
        assert result is False
        self.mock_s3_client.put_object.assert_not_called()

    def test_save_ohlcv_s3_put_object_exception(self):
        """
        save_ohlcv()でS3 put_object例外

        条件: put_object()でClientError発生
        期待: save_ohlcv()=False、エラーログ
        """
        # Arrange
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }
        self.mock_s3_client.put_object.side_effect = ClientError(error_response, 'PutObject')

        # Act
        result = self.repository.save_ohlcv(self.sample_df, 'USDJPY', 'H1')

        # Assert
        assert result is False

    def test_save_ohlcv_parquet_conversion_exception(self):
        """
        save_ohlcv()でParquet変換例外

        条件: DataFrame.to_parquet()で例外発生
        期待: save_ohlcv()=False、エラーログ
        """
        # Arrange
        invalid_df = pd.DataFrame({'timestamp_utc': [None]})  # 無効なデータ

        # Act
        result = self.repository.save_ohlcv(invalid_df, 'USDJPY', 'H1')

        # Assert
        assert result is False

    def test_load_ohlcv_missing_start_date(self):
        """
        load_ohlcv()でstart_date未指定

        条件: start_date=None、end_date=None、days=None
        期待: load_ohlcv()=None、エラーログ
        """
        # Act
        result = self.repository.load_ohlcv('USDJPY', 'H1')

        # Assert
        assert result is None

    def test_load_ohlcv_partition_exception(self):
        """
        load_ohlcv()でパーティション読み込み例外

        条件: list_objects_v2()で例外発生
        期待: 該当パーティションをスキップ、処理継続
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.side_effect = Exception("S3 connection error")

        # Act
        result = self.repository.load_ohlcv('USDJPY', 'H1', days=1)

        # Assert
        # エラーがあっても None を返す（クラッシュしない）
        assert result is None

    def test_exists_list_objects_exception(self):
        """
        exists()でlist_objects_v2例外

        条件: list_objects_v2()で例外発生
        期待: exists()=False、エラーログ
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.side_effect = Exception("S3 connection timeout")

        # Act
        result = self.repository.exists('USDJPY', 'H1', datetime(2025, 1, 1, tzinfo=pytz.UTC))

        # Assert
        assert result is False

    def test_exists_no_contents(self):
        """
        exists()でContentsなし

        条件: list_objects_v2()が空レスポンス
        期待: exists()=False
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.return_value = {}  # 'Contents'キーなし

        # Act
        result = self.repository.exists('USDJPY', 'H1', datetime(2025, 1, 1, tzinfo=pytz.UTC))

        # Assert
        assert result is False

    def test_get_available_range_list_objects_exception(self):
        """
        get_available_range()でlist_objects_v2例外

        条件: list_objects_v2()で例外発生
        期待: get_available_range()=None、エラーログ
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.side_effect = Exception("S3 access error")

        # Act
        result = self.repository.get_available_range('USDJPY', 'H1')

        # Assert
        assert result is None

    def test_get_available_range_no_contents(self):
        """
        get_available_range()でデータなし

        条件: list_objects_v2()が空レスポンス
        期待: get_available_range()=None
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.return_value = {}  # 'Contents'キーなし

        # Act
        result = self.repository.get_available_range('USDJPY', 'H1')

        # Assert
        assert result is None

    def test_load_partition_get_object_exception(self):
        """
        _load_partition()でget_object例外

        条件: get_object()で例外発生
        期待: 個別ファイルエラーは無視、None返却（ロバスト性重視）
        """
        # Arrange
        self.mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=01/day=01/test.parquet'}
            ]
        }
        self.mock_s3_client.get_object.side_effect = Exception("Get object failed")

        # Act
        result = self.repository._load_partition('symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=01/day=01/')

        # Assert
        # 個別ファイルのエラーは続行し、最終的にNoneを返す
        assert result is None

    def test_load_partition_client_error_no_such_key(self):
        """
        _load_partition()でNoSuchKey

        条件: list_objects_v2()でNoSuchKey ClientError発生
        期待: _load_partition()=None（正常ケース）
        """
        # Arrange
        error_response = {
            'Error': {
                'Code': 'NoSuchKey',
                'Message': 'The specified key does not exist'
            }
        }
        self.mock_s3_client.list_objects_v2.side_effect = ClientError(error_response, 'ListObjectsV2')

        # Act
        result = self.repository._load_partition('symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=01/day=01/')

        # Assert
        assert result is None

    # ========================================
    # 【バリデーション】2テスト
    # ========================================

    def test_init_empty_bucket_name(self):
        """
        初期化で空bucket_name

        条件: bucket_name=""
        期待: ValueError発生
        """
        # Act & Assert
        with pytest.raises(ValueError, match="bucket_name must not be empty"):
            S3OhlcvDataRepository("", self.mock_s3_client)

    def test_init_none_bucket_name(self):
        """
        初期化でNone bucket_name

        条件: bucket_name=None
        期待: ValueError発生
        """
        # Act & Assert
        with pytest.raises(ValueError, match="bucket_name must not be empty"):
            S3OhlcvDataRepository(None, self.mock_s3_client)


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
