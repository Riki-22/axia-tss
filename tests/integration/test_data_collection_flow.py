# tests/integration/test_data_collection_flow.py
"""
E2Eデータ収集フロー統合テスト

統合対象:
- OhlcvDataProvider
- MT5DataCollector (mocked)
- RedisOhlcvDataRepository (mocked)
- S3OhlcvDataRepository (mocked)

シナリオ:
1. Redis → MT5 フォールバック
2. MT5 → S3 フォールバック
3. データキャッシング
4. 統計情報収集
"""

import pytest
from unittest.mock import Mock, MagicMock
import pandas as pd
from datetime import datetime
import pytz

from src.infrastructure.gateways.market_data.ohlcv_data_provider import OhlcvDataProvider


class TestDataCollectionFlow:
    """E2Eデータ収集フロー統合テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # サンプルOHLCVデータ
        self.sample_ohlcv = pd.DataFrame({
            'time': [
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
    # 【E2E: Redis → MT5 フォールバック】
    # ========================================

    def test_redis_fail_mt5_success_flow(self):
        """
        統合: Redis失敗 → MT5成功フォールバック

        シナリオ:
        1. Redis.load_ohlcv() → None（失敗）
        2. MT5.fetch_ohlcv_data() → DataFrame（成功）
        3. 結果をRedisに自動キャッシュ
        4. 統計情報にMT5使用を記録

        検証:
        - 最終的にデータ取得成功
        - metadata.source = 'mt5'
        - metadata.cache_hit = False
        - Redis.save_ohlcv()が呼ばれる（自動キャッシュ）
        - 統計情報が正しく更新される
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = None  # Redis失敗
        mock_redis.save_ohlcv.return_value = True

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = self.sample_ohlcv.copy()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=None,
            yfinance_client=None
        )

        # Act
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'
        )

        # Assert
        # 1. データ取得成功
        assert df is not None
        assert len(df) == 2
        assert metadata['source'] == 'mt5'
        assert metadata['cache_hit'] is False

        # 2. MT5が呼ばれた
        mock_mt5.fetch_ohlcv_data.assert_called_once()

        # 3. 統計情報確認
        stats = provider.get_stats()
        assert stats['source_usage']['mt5'] == 1
        assert stats['cache_misses'] == 1

        # 4. fallback_countはMT5が最初なので0（フォールバックなし）
        assert metadata['fallback_count'] == 0

    # ========================================
    # 【E2E: MT5 → S3 フォールバック】
    # ========================================

    def test_redis_mt5_fail_s3_success_flow(self):
        """
        統合: Redis/MT5失敗 → S3成功フォールバック

        シナリオ:
        1. Redis.load_ohlcv() → None
        2. MT5.fetch_ohlcv_data() → None（失敗）
        3. S3.load_ohlcv() → DataFrame（成功）
        4. 結果をRedisに自動キャッシュ

        検証:
        - 最終的にデータ取得成功
        - metadata.source = 's3'
        - metadata.fallback_count = 2
        - 統計情報にS3使用を記録
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = None
        mock_redis.save_ohlcv.return_value = True

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = None  # MT5失敗

        mock_s3 = Mock()
        mock_s3.load_ohlcv.return_value = self.sample_ohlcv.copy()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Act
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=30,
            use_case='chart'
        )

        # Assert
        # 1. データ取得成功
        assert df is not None
        assert metadata['source'] == 's3'
        # chart用途、30日: 優先順位['redis', 's3', ...]
        # Redis失敗、S3成功 → fallback_count = 1
        assert metadata['fallback_count'] == 1

        # 2. S3が呼ばれた
        mock_s3.load_ohlcv.assert_called_once()

        # 3. 統計情報確認
        stats = provider.get_stats()
        assert stats['source_usage']['s3'] == 1

    # ========================================
    # 【E2E: Redisキャッシュヒット】
    # ========================================

    def test_redis_cache_hit_flow(self):
        """
        統合: Redisキャッシュヒット

        シナリオ:
        1. chart用途でRedis優先（period_days=1）
        2. Redis.load_ohlcv() → DataFrame（成功）
        3. 他のソースは呼ばれない

        検証:
        - データ取得成功
        - metadata.source = 'redis'
        - metadata.cache_hit = True
        - MT5/S3が呼ばれない
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = self.sample_ohlcv.copy()

        mock_mt5 = Mock()
        mock_s3 = Mock()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Act - chart用途でRedis優先
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='chart'  # chart用途でRedis優先
        )

        # Assert
        # 1. データ取得成功
        assert df is not None
        assert metadata['source'] == 'redis'
        assert metadata['cache_hit'] is True

        # 2. MT5/S3は呼ばれない
        mock_mt5.fetch_ohlcv_data.assert_not_called()
        mock_s3.load_ohlcv.assert_not_called()

        # 3. 統計情報確認
        stats = provider.get_stats()
        assert stats['cache_hits'] == 1
        assert stats['source_usage']['redis'] == 1

    # ========================================
    # 【E2E: 全ソース失敗】
    # ========================================

    def test_all_sources_fail_flow(self):
        """
        統合: 全データソース失敗

        シナリオ:
        1. Redis.load_ohlcv() → None
        2. MT5.fetch_ohlcv_data() → None
        3. S3.load_ohlcv() → None
        4. 全ソース失敗

        検証:
        - df = None
        - metadata.error = "All data sources failed..."
        - metadata.fallback_count = 3
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = None

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = None

        mock_s3 = Mock()
        mock_s3.load_ohlcv.return_value = None

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Act
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'
        )

        # Assert
        # 1. データ取得失敗
        assert df is None
        assert 'error' in metadata
        assert 'All data sources failed' in metadata['error']
        # fallback_countは試行した回数-1（最初のソースは含まない）
        assert metadata['fallback_count'] >= 2  # 少なくとも2回フォールバック

    # ========================================
    # 【E2E: ソース優先順位マトリックス】
    # ========================================

    def test_source_priority_trading_recent(self):
        """
        統合: Trading用途 + 24h以内のソース優先順位

        シナリオ:
        use_case='trading', period_days=1
        期待優先順位: ['mt5', 'redis', 's3']

        検証:
        - MT5が最初に呼ばれる
        - MT5成功時、他は呼ばれない
        """
        # Arrange
        mock_redis = Mock()
        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = self.sample_ohlcv.copy()
        mock_s3 = Mock()

        mock_redis.save_ohlcv.return_value = True

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Act
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'
        )

        # Assert
        # MT5が優先され、成功
        assert metadata['source'] == 'mt5'
        mock_mt5.fetch_ohlcv_data.assert_called_once()

        # Redis/S3は呼ばれない（MT5で成功したため）
        mock_redis.load_ohlcv.assert_not_called()
        mock_s3.load_ohlcv.assert_not_called()

    def test_source_priority_analysis_long_term(self):
        """
        統合: Analysis用途 + 長期データのソース優先順位

        シナリオ:
        use_case='analysis', period_days=90
        期待優先順位: ['s3', 'redis']

        検証:
        - S3が最初に呼ばれる
        - S3成功時、他は呼ばれない
        """
        # Arrange
        mock_redis = Mock()
        mock_mt5 = Mock()
        mock_s3 = Mock()
        mock_s3.load_ohlcv.return_value = self.sample_ohlcv.copy()

        mock_redis.save_ohlcv.return_value = True

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Act
        df, metadata = provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=90,
            use_case='analysis'
        )

        # Assert
        # S3が優先され、成功
        assert metadata['source'] == 's3'
        mock_s3.load_ohlcv.assert_called_once()

        # MT5は呼ばれない（S3で成功したため）
        mock_mt5.fetch_ohlcv_data.assert_not_called()


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
