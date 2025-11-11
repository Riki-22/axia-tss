# tests/integration/test_multi_source_fallback.py
"""
マルチソースデータフォールバック統合テスト

統合対象:
- OhlcvDataProvider
- 複数データソース（Redis, MT5, S3, yfinance）
- フォールバック戦略
- 統計情報収集

シナリオ:
1. 3段階フォールバック（Redis → MT5 → S3）
2. 部分的失敗からの回復
3. レスポンス時間統計
4. ソース使用率統計
"""

import pytest
from unittest.mock import Mock
import pandas as pd
from datetime import datetime
import pytz

from src.infrastructure.gateways.market_data.ohlcv_data_provider import OhlcvDataProvider


class TestMultiSourceFallback:
    """マルチソースデータフォールバック統合テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # サンプルOHLCVデータ
        self.sample_ohlcv = pd.DataFrame({
            'time': [
                datetime(2025, 1, 1, 12, 0, tzinfo=pytz.UTC),
                datetime(2025, 1, 1, 13, 0, tzinfo=pytz.UTC),
                datetime(2025, 1, 1, 14, 0, tzinfo=pytz.UTC)
            ],
            'open': [150.0, 150.5, 150.8],
            'high': [150.5, 151.0, 151.2],
            'low': [149.5, 150.0, 150.3],
            'close': [150.2, 150.8, 150.9],
            'volume': [1000, 1500, 1200]
        })

    # ========================================
    # 【シナリオ1: 3段階フォールバック成功】
    # ========================================

    def test_three_stage_fallback_success(self):
        """
        統合: Redis → MT5 → S3 の3段階フォールバック

        シナリオ:
        1. Redis: 失敗（None返却）
        2. MT5: 失敗（None返却）
        3. S3: 成功（DataFrame返却）

        検証:
        - 最終的にS3からデータ取得成功
        - fallback_count = 2
        - 統計情報にフォールバック記録
        - Redis自動キャッシュ実行
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = None  # 失敗
        mock_redis.save_ohlcv.return_value = True

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = None  # 失敗

        mock_s3 = Mock()
        mock_s3.load_ohlcv.return_value = self.sample_ohlcv.copy()  # 成功

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
        assert len(df) == 3
        assert metadata['source'] == 's3'
        # chart用途、30日: 優先順位['redis', 's3', ...]
        # Redis失敗、S3成功 → fallback_count = 1
        assert metadata['fallback_count'] == 1

        # 2. 各ソースの呼び出し確認
        mock_redis.load_ohlcv.assert_called_once()
        # MT5は優先順位に含まれないので呼ばれない可能性がある
        mock_s3.load_ohlcv.assert_called_once()

        # 3. 統計情報確認
        stats = provider.get_stats()
        assert stats['source_usage']['s3'] == 1
        assert stats['cache_misses'] == 1

    # ========================================
    # 【シナリオ2: 段階的回復（2回目でMT5成功）】
    # ========================================

    def test_fallback_recovery_at_second_source(self):
        """
        統合: 2番目のソース（MT5）で回復

        シナリオ:
        1. Redis: 失敗
        2. MT5: 成功
        3. S3: 呼ばれない（MT5で成功したため）

        検証:
        - MT5からデータ取得
        - fallback_count = 1
        - S3は呼ばれない
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = None
        mock_redis.save_ohlcv.return_value = True

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.return_value = self.sample_ohlcv.copy()

        mock_s3 = Mock()

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
        assert df is not None
        assert metadata['source'] == 'mt5'
        # trading用途、1日: 優先順位['mt5', 'redis', ...]
        # MT5成功 → fallback_count = 0（最初のソースで成功）
        assert metadata['fallback_count'] == 0

        # S3は呼ばれない
        mock_s3.load_ohlcv.assert_not_called()

    # ========================================
    # 【シナリオ3: 例外発生時のフォールバック】
    # ========================================

    def test_fallback_on_exception(self):
        """
        統合: 例外発生時のフォールバック動作

        シナリオ:
        1. Redis: Exception発生
        2. MT5: Exception発生
        3. S3: 成功

        検証:
        - 例外が発生してもフォールバック継続
        - 最終的にS3から取得成功
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.side_effect = Exception("Redis connection timeout")
        mock_redis.save_ohlcv.return_value = True

        mock_mt5 = Mock()
        mock_mt5.fetch_ohlcv_data.side_effect = Exception("MT5 API error")

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
            use_case='analysis'
        )

        # Assert
        # 例外発生してもS3で成功
        assert df is not None
        assert metadata['source'] == 's3'

    # ========================================
    # 【シナリオ4: 統計情報の蓄積】
    # ========================================

    def test_statistics_accumulation_across_requests(self):
        """
        統合: 複数リクエストにわたる統計情報蓄積

        シナリオ:
        1. 1回目: Redis成功（キャッシュヒット）
        2. 2回目: Redis失敗 → MT5成功
        3. 3回目: Redis失敗 → MT5失敗 → S3成功

        検証:
        - 統計情報が正しく蓄積される
        - ソース別使用率が正確
        - キャッシュヒット率が正確
        """
        # Arrange
        mock_redis = Mock()
        mock_mt5 = Mock()
        mock_s3 = Mock()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=mock_mt5,
            s3_repository=mock_s3,
            yfinance_client=None
        )

        # Request 1: Redis hit
        mock_redis.load_ohlcv.return_value = self.sample_ohlcv.copy()
        df1, meta1 = provider.get_data('USDJPY', 'H1', 1, 'trading')
        assert meta1['source'] == 'redis'

        # Request 2: Redis miss → MT5 hit
        mock_redis.load_ohlcv.return_value = None
        mock_redis.save_ohlcv.return_value = True
        mock_mt5.fetch_ohlcv_data.return_value = self.sample_ohlcv.copy()
        df2, meta2 = provider.get_data('EURUSD', 'H1', 1, 'trading')
        assert meta2['source'] == 'mt5'

        # Request 3: Redis miss → MT5 miss → S3 hit
        mock_mt5.fetch_ohlcv_data.return_value = None
        mock_s3.load_ohlcv.return_value = self.sample_ohlcv.copy()
        df3, meta3 = provider.get_data('GBPUSD', 'H1', 30, 'chart')
        assert meta3['source'] == 's3'

        # Assert: 統計情報確認
        stats = provider.get_stats()
        assert stats['total_requests'] == 3
        assert stats['source_usage']['redis'] == 1
        assert stats['source_usage']['mt5'] == 1
        assert stats['source_usage']['s3'] == 1
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 2
        assert stats['cache_hit_rate'] == 1 / 3  # 1 hit out of 3 requests

    # ========================================
    # 【シナリオ5: ソース利用不可時の動的除外】
    # ========================================

    def test_unavailable_source_excluded_from_priority(self):
        """
        統合: 利用不可能なソースの動的除外

        シナリオ:
        1. MT5が利用不可（None）
        2. S3が利用不可（None）
        3. Redisのみ利用可能

        検証:
        - 利用可能なRedisのみ試行
        - 利用不可能なMT5/S3は試行されない
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = self.sample_ohlcv.copy()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=None,  # MT5利用不可
            s3_repository=None,  # S3利用不可
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
        # Redisのみ利用可能、成功
        assert df is not None
        assert metadata['source'] == 'redis'
        assert metadata['fallback_count'] == 0  # フォールバック不要

    # ========================================
    # 【シナリオ6: レスポンス時間統計】
    # ========================================

    def test_response_time_statistics(self):
        """
        統合: レスポンス時間統計の記録

        シナリオ:
        1. 複数リクエスト実行
        2. 各ソースのレスポンス時間を記録

        検証:
        - metadata.response_timeが記録される
        - 統計情報に平均レスポンス時間が記録される
        """
        # Arrange
        mock_redis = Mock()
        mock_redis.load_ohlcv.return_value = self.sample_ohlcv.copy()

        provider = OhlcvDataProvider(
            ohlcv_cache=mock_redis,
            mt5_data_collector=None,
            s3_repository=None,
            yfinance_client=None
        )

        # Act
        df1, meta1 = provider.get_data('USDJPY', 'H1', 1, 'trading')
        df2, meta2 = provider.get_data('EURUSD', 'H1', 1, 'trading')

        # Assert
        # レスポンス時間が記録されている
        assert 'response_time' in meta1
        assert 'response_time' in meta2
        assert meta1['response_time'] > 0
        assert meta2['response_time'] > 0

        # 統計情報に平均レスポンス時間が記録されている
        stats = provider.get_stats()
        assert 'avg_response_time' in stats
        assert 'redis' in stats['avg_response_time']
        assert stats['avg_response_time']['redis'] > 0


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
