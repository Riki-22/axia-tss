# tests/unit/infrastructure/persistence/s3/test_s3_ohlcv_data_repository.py
"""S3OhlcvDataRepository 単体テスト"""

import pytest
from datetime import datetime
import pytz
from unittest.mock import Mock

from src.infrastructure.persistence.s3.s3_ohlcv_data_repository import S3OhlcvDataRepository


class TestS3OhlcvDataRepository:
    """S3OhlcvDataRepository のテストクラス"""
    
    @classmethod
    def setup_class(cls):
        """テストクラス全体のセットアップ"""
        cls.s3_client = Mock()
        cls.bucket_name = "test-bucket"
        cls.repo = S3OhlcvDataRepository(
            bucket_name=cls.bucket_name,
            s3_client=cls.s3_client
        )
    
    # ========================================
    # _generate_partition_keys() テスト
    # ========================================
    
    def test_generate_partition_keys_single_day(self):
        """1日分のパーティションキー生成"""
        start = datetime(2025, 10, 15, 10, 30, 0, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, 18, 45, 0, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'USDJPY', 'H1', start, end
        )
        
        assert len(keys) == 1
        assert keys[0] == (
            'symbol=USDJPY/'
            'timeframe=H1/'
            'source=mt5/'
            'year=2025/'
            'month=10/'
            'day=15/'
        )
    
    def test_generate_partition_keys_multiple_days(self):
        """複数日のパーティションキー生成"""
        start = datetime(2025, 10, 13, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'EURUSD', 'M15', start, end
        )
        
        assert len(keys) == 3
        assert keys[0] == (
            'symbol=EURUSD/'
            'timeframe=M15/'
            'source=mt5/'
            'year=2025/'
            'month=10/'
            'day=13/'
        )
        assert keys[1] == (
            'symbol=EURUSD/'
            'timeframe=M15/'
            'source=mt5/'
            'year=2025/'
            'month=10/'
            'day=14/'
        )
        assert keys[2] == (
            'symbol=EURUSD/'
            'timeframe=M15/'
            'source=mt5/'
            'year=2025/'
            'month=10/'
            'day=15/'
        )
    
    def test_generate_partition_keys_month_boundary(self):
        """月跨ぎのパーティションキー生成"""
        start = datetime(2025, 9, 29, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 2, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'GBPJPY', 'D1', start, end
        )
        
        assert len(keys) == 4
        # 9月分
        assert 'month=09/day=29/' in keys[0]
        assert 'month=09/day=30/' in keys[1]
        # 10月分
        assert 'month=10/day=01/' in keys[2]
        assert 'month=10/day=02/' in keys[3]
    
    def test_generate_partition_keys_year_boundary(self):
        """年跨ぎのパーティションキー生成"""
        start = datetime(2024, 12, 30, tzinfo=pytz.UTC)
        end = datetime(2025, 1, 2, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'USDJPY', 'H1', start, end
        )
        
        assert len(keys) == 4
        # 2024年分
        assert 'year=2024/month=12/day=30/' in keys[0]
        assert 'year=2024/month=12/day=31/' in keys[1]
        # 2025年分
        assert 'year=2025/month=01/day=01/' in keys[2]
        assert 'year=2025/month=01/day=02/' in keys[3]
    
    def test_generate_partition_keys_30_days(self):
        """30日分のパーティションキー生成"""
        start = datetime(2025, 9, 16, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'EURUSD', 'H1', start, end
        )
        
        assert len(keys) == 30
        # 最初と最後を確認
        assert 'year=2025/month=09/day=16/' in keys[0]
        assert 'year=2025/month=10/day=15/' in keys[-1]
    
    def test_generate_partition_keys_time_normalization(self):
        """時刻が正規化されることを確認"""
        # 時刻が異なっても同じ日として扱われる
        start = datetime(2025, 10, 15, 8, 30, 15, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, 22, 45, 30, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'USDJPY', 'H1', start, end
        )
        
        # 同じ日なので1つのキーのみ
        assert len(keys) == 1
    
    def test_generate_partition_keys_end_before_start(self):
        """終了日が開始日より前の場合（空リスト）"""
        start = datetime(2025, 10, 15, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 10, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'USDJPY', 'H1', start, end
        )
        
        # 終了日が開始日より前なので空リスト
        assert len(keys) == 0
    
    def test_generate_partition_keys_format_consistency(self):
        """キーフォーマットの一貫性確認"""
        start = datetime(2025, 1, 5, tzinfo=pytz.UTC)
        end = datetime(2025, 1, 5, tzinfo=pytz.UTC)
        
        keys = self.repo._generate_partition_keys(
            'USDJPY', 'H1', start, end
        )
        
        # フォーマットの確認
        expected_format = (
            'symbol=USDJPY/'
            'timeframe=H1/'
            'source=mt5/'
            'year=2025/'
            'month=01/'  # ゼロパディング確認
            'day=05/'    # ゼロパディング確認
        )
        assert keys[0] == expected_format
    
    # ========================================
    # _load_partition() テスト
    # ========================================
    
    def test_load_partition_success(self):
        """パーティション読み込み成功"""
        import pandas as pd
        import io
        
        # モックデータ準備
        test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15', periods=24, freq='H'),
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        })
        
        # Parquetバイナリ作成
        buffer = io.BytesIO()
        test_df.to_parquet(buffer, index=False)
        buffer.seek(0)
        parquet_data = buffer.getvalue()
        
        # S3モック設定
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data.parquet'}
            ]
        }
        self.s3_client.get_object.return_value = {
            'Body': io.BytesIO(parquet_data)
        }
        
        # テスト実行
        result = self.repo._load_partition(
            'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        )
        
        assert result is not None
        assert len(result) == 24
        assert list(result.columns) == ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
    
    def test_load_partition_no_files(self):
        """パーティションにファイルが存在しない"""
        # S3モック設定（空のレスポンス）
        self.s3_client.list_objects_v2.return_value = {}
        
        result = self.repo._load_partition(
            'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        )
        
        assert result is None
    
    def test_load_partition_no_parquet_files(self):
        """パーティションにParquetファイルが存在しない"""
        # S3モック設定（.parquet以外のファイル）
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data.txt'}
            ]
        }
        
        result = self.repo._load_partition(
            'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        )
        
        assert result is None
    
    def test_load_partition_multiple_files(self):
        """パーティション内に複数ファイルがある場合"""
        import pandas as pd
        import io
        
        # 2つのDataFrame
        df1 = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15 00:00', periods=12, freq='H'),
            'open': [100.0] * 12,
            'high': [101.0] * 12,
            'low': [99.0] * 12,
            'close': [100.5] * 12,
            'volume': [1000] * 12
        })
        
        df2 = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15 12:00', periods=12, freq='H'),
            'open': [101.0] * 12,
            'high': [102.0] * 12,
            'low': [100.0] * 12,
            'close': [101.5] * 12,
            'volume': [1100] * 12
        })
        
        # Parquetバイナリ作成
        buffer1 = io.BytesIO()
        df1.to_parquet(buffer1, index=False)
        buffer1.seek(0)
        
        buffer2 = io.BytesIO()
        df2.to_parquet(buffer2, index=False)
        buffer2.seek(0)
        
        # S3モック設定
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data1.parquet'},
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data2.parquet'}
            ]
        }
        
        # get_objectを複数回呼ぶモック
        self.s3_client.get_object.side_effect = [
            {'Body': buffer1},
            {'Body': buffer2}
        ]
        
        result = self.repo._load_partition(
            'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        )
        
        assert result is not None
        assert len(result) == 24  # 12 + 12
    
    def test_load_partition_nosuchkey_exception(self):
        """NoSuchKey例外の場合（Noneを返す）"""
        from botocore.exceptions import ClientError
        
        # NoSuchKeyエラーを返すモック
        error_response = {'Error': {'Code': 'NoSuchKey'}}
        self.s3_client.list_objects_v2.side_effect = ClientError(
            error_response, 'list_objects_v2'
        )
        
        # リセット
        self.s3_client.exceptions = Mock()
        self.s3_client.exceptions.NoSuchKey = ClientError
        
        result = self.repo._load_partition(
            'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/'
        )
        
        # NoSuchKeyの場合はNoneを返す（例外を投げない）
        assert result is None
    
    # ========================================
    # load_ohlcv() テスト
    # ========================================
    
    def test_load_ohlcv_with_days(self):
        """days指定でデータ読み込み"""
        import pandas as pd
        import io
        
        # モックデータ準備
        test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15', periods=24, freq='H'),
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        })
        
        buffer = io.BytesIO()
        test_df.to_parquet(buffer, index=False)
        buffer.seek(0)
        
        # S3モック設定
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data.parquet'}
            ]
        }
        self.s3_client.get_object.return_value = {
            'Body': buffer
        }
        
        # テスト実行（days=1）
        result = self.repo.load_ohlcv('USDJPY', 'H1', days=1)
        
        assert result is not None
        assert len(result) > 0
        assert 'timestamp_utc' in result.columns
    
    def test_load_ohlcv_with_date_range(self):
        """start_date/end_date指定でデータ読み込み"""
        import pandas as pd
        import io
        
        # 3日分のモックデータ
        test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-13', periods=72, freq='H'),
            'open': [100.0] * 72,
            'high': [101.0] * 72,
            'low': [99.0] * 72,
            'close': [100.5] * 72,
            'volume': [1000] * 72
        })
        
        buffer = io.BytesIO()
        test_df.to_parquet(buffer, index=False)
        buffer.seek(0)
        
        # S3モック設定
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=13/data.parquet'}
            ]
        }
        self.s3_client.get_object.return_value = {
            'Body': buffer
        }
        
        # テスト実行
        start = datetime(2025, 10, 13, tzinfo=pytz.UTC)
        end = datetime(2025, 10, 15, tzinfo=pytz.UTC)
        
        result = self.repo.load_ohlcv(
            'USDJPY', 'H1',
            start_date=start,
            end_date=end
        )
        
        assert result is not None
        assert len(result) > 0
    
    def test_load_ohlcv_no_data(self):
        """データが存在しない場合"""
        # 空のレスポンス
        self.s3_client.list_objects_v2.return_value = {}
        
        result = self.repo.load_ohlcv('USDJPY', 'H1', days=30)
        
        assert result is None
    
    # ========================================
    # exists() テスト
    # ========================================
    
    def test_exists_true(self):
        """データが存在する場合"""
        # S3モック設定
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data.parquet'}
            ]
        }
        
        result = self.repo.exists(
            'USDJPY', 'H1',
            datetime(2025, 10, 15, tzinfo=pytz.UTC)
        )
        
        assert result is True
    
    def test_exists_false(self):
        """データが存在しない場合"""
        # 空のレスポンス
        self.s3_client.list_objects_v2.return_value = {}
        
        result = self.repo.exists(
            'USDJPY', 'H1',
            datetime(2025, 10, 15, tzinfo=pytz.UTC)
        )
        
        assert result is False
    
    def test_exists_no_parquet_files(self):
        """Parquetファイルが存在しない場合"""
        # .parquet以外のファイル
        self.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'symbol=USDJPY/timeframe=H1/source=mt5/year=2025/month=10/day=15/data.txt'}
            ]
        }
        
        result = self.repo.exists(
            'USDJPY', 'H1',
            datetime(2025, 10, 15, tzinfo=pytz.UTC)
        )
        
        assert result is False


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])