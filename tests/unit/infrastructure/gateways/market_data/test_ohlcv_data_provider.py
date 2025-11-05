# tests/unit/infrastructure/gateways/market_data/test_ohlcv_data_provider.py
"""OhlcvDataProvider 単体テスト"""

import pytest
from unittest.mock import Mock

from src.infrastructure.gateways.market_data.ohlcv_data_provider import OhlcvDataProvider


class TestOhlcvDataProvider:
    """OhlcvDataProvider のテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックオブジェクト作成
        self.ohlcv_cache = Mock()
        self.mt5_collector = Mock()
        self.s3_repo = Mock()
        self.yfinance_client = Mock()
        
        # プロバイダー作成（全ソース利用可能）
        self.provider = OhlcvDataProvider(
            ohlcv_cache=self.ohlcv_cache,
            mt5_data_collector=self.mt5_collector,
            s3_repository=self.s3_repo,
            yfinance_client=self.yfinance_client
        )
    
    # ========================================
    # 初期化テスト
    # ========================================
    
    def test_init_all_sources(self):
        """全ソース利用可能な初期化"""
        assert self.provider.cache is not None
        assert self.provider.mt5 is not None
        assert self.provider.s3 is not None
        assert self.provider.yfinance is not None
    
    def test_init_redis_only(self):
        """Redis のみの初期化"""
        provider = OhlcvDataProvider(
            ohlcv_cache=self.ohlcv_cache
        )
        
        assert provider.cache is not None
        assert provider.mt5 is None
        assert provider.s3 is None
        assert provider.yfinance is None
    
    def test_init_statistics(self):
        """統計情報の初期化"""
        stats = self.provider.get_stats()
        
        assert stats['total_requests'] == 0
        assert stats['cache_hit_rate'] == 0.0
        assert len(stats['source_usage']) == 4
    
    # ========================================
    # _get_source_priority() テスト
    # ========================================
    
    def test_source_priority_trading_recent(self):
        """trading用、24時間以内"""
        priority = self.provider._get_source_priority('trading', 1)
        
        assert priority == ['mt5', 'redis', 'yfinance']
    
    def test_source_priority_trading_long(self):
        """trading用、24時間超"""
        priority = self.provider._get_source_priority('trading', 30)
        
        assert priority == ['mt5', 'yfinance']
        # S3はスキップ
        assert 's3' not in priority
    
    def test_source_priority_chart_recent(self):
        """chart用、24時間以内"""
        priority = self.provider._get_source_priority('chart', 1)
        
        assert priority == ['redis', 'mt5', 'yfinance']
        # Redis優先
        assert priority[0] == 'redis'
    
    def test_source_priority_chart_long(self):
        """chart用、24時間超"""
        priority = self.provider._get_source_priority('chart', 30)
        
        assert priority == ['redis', 's3', 'yfinance']
        # S3が含まれる
        assert 's3' in priority
    
    def test_source_priority_analysis_recent(self):
        """analysis用、24時間以内"""
        priority = self.provider._get_source_priority('analysis', 1)
        
        assert priority == ['redis', 's3', 'yfinance']
    
    def test_source_priority_analysis_long(self):
        """analysis用、24時間超"""
        priority = self.provider._get_source_priority('analysis', 90)
        
        assert priority == ['s3', 'redis', 'yfinance']
        # S3優先
        assert priority[0] == 's3'
    
    def test_source_priority_force_source(self):
        """force_source指定時"""
        priority = self.provider._get_source_priority(
            'trading', 1, force_source='s3'
        )
        
        assert priority == ['s3']
        # 他のソースは無視される
        assert len(priority) == 1
    
    def test_source_priority_unknown_use_case(self):
        """未知のuse_case（デフォルト動作）"""
        priority = self.provider._get_source_priority('unknown', 1)
        
        # デフォルトは全ソース
        assert 'redis' in priority
        assert 'mt5' in priority
        assert 's3' in priority
        assert 'yfinance' in priority
    
    def test_source_priority_boundary_24h(self):
        """境界値: 24時間ちょうど"""
        priority_1day = self.provider._get_source_priority('chart', 1)
        priority_2days = self.provider._get_source_priority('chart', 2)
        
        # 1日: 直近扱い
        assert priority_1day[0] == 'redis'
        
        # 2日: 長期扱い
        assert 's3' in priority_2days
    
    # ========================================
    # _filter_available_sources() テスト
    # ========================================
    
    def test_filter_available_sources_all(self):
        """全ソース利用可能"""
        sources = ['redis', 'mt5', 's3', 'yfinance']
        filtered = self.provider._filter_available_sources(sources)
        
        assert filtered == sources
    
    def test_filter_available_sources_redis_only(self):
        """Redis のみ利用可能"""
        provider = OhlcvDataProvider(ohlcv_cache=self.ohlcv_cache)
        
        sources = ['redis', 'mt5', 's3', 'yfinance']
        filtered = provider._filter_available_sources(sources)
        
        assert filtered == ['redis']
    
    def test_filter_available_sources_none(self):
        """利用可能なソースがない"""
        provider = OhlcvDataProvider(ohlcv_cache=self.ohlcv_cache)
        
        sources = ['mt5', 's3']  # Redisは含まれない
        filtered = provider._filter_available_sources(sources)
        
        assert filtered == []
    
    # ========================================
    # 統計情報テスト
    # ========================================
    
    def test_get_stats_initial(self):
        """初期状態の統計情報"""
        stats = self.provider.get_stats()
        
        assert stats['total_requests'] == 0
        assert stats['cache_hit_rate'] == 0.0
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0
    
    def test_reset_stats(self):
        """統計情報のリセット"""
        # 統計情報を変更
        self.provider._stats['total_requests'] = 10
        self.provider._stats['cache_hits'] = 5

        # リセット
        self.provider.reset_stats()

        # 初期状態に戻る
        stats = self.provider.get_stats()
        assert stats['total_requests'] == 0
        assert stats['cache_hits'] == 0

    # ========================================
    # get_data() フォールバック経路テスト
    # ========================================

    def test_get_data_redis_success(self):
        """get_data: Redis成功（chart use case）

        条件: chart用、Redis からデータ取得成功
        期待: DataFrameとmetadata返却、source='redis', fallback_count=0
        """
        # Arrange
        import pandas as pd
        test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15', periods=24, freq='h'),
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        })

        self.ohlcv_cache.load_ohlcv.return_value = test_df

        # Act (chart use caseはRedis優先)
        df, metadata = self.provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='chart'  # Redis優先
        )

        # Assert
        assert df is not None
        assert len(df) == 24
        assert metadata['source'] == 'redis'
        assert metadata['cache_hit'] is True
        assert metadata['fallback_count'] == 0
        assert 'response_time' in metadata

    def test_get_data_mt5_success(self):
        """get_data: MT5成功（trading use case）

        条件: trading用、MT5からデータ取得成功
        期待: MT5からデータ取得、Redisにキャッシュ、fallback_count=0
        """
        # Arrange
        import pandas as pd
        from datetime import datetime, timedelta
        import pytz

        # 最近のデータ（過去12時間）を作成（24時間以内なのでキャッシュ対象）
        now = datetime.now(pytz.UTC)
        start_time = now - timedelta(hours=12)

        test_df = pd.DataFrame({
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        }, index=pd.date_range(start=start_time, periods=24, freq='30min', name='timestamp_utc', tz=pytz.UTC))

        # MT5成功
        self.mt5_collector.fetch_ohlcv_data.return_value = test_df

        # Redisキャッシュ成功
        self.ohlcv_cache.save_ohlcv.return_value = True

        # Act (trading use caseはMT5優先)
        df, metadata = self.provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'  # MT5優先
        )

        # Assert
        assert df is not None
        assert len(df) == 24
        assert metadata['source'] == 'mt5'
        assert metadata['cache_hit'] is False
        assert metadata['fallback_count'] == 0

        # Redisキャッシュが呼ばれたか
        self.ohlcv_cache.save_ohlcv.assert_called_once()

    def test_get_data_redis_fail_s3_success(self):
        """get_data: Redis失敗 → S3成功（フォールバック1回）

        条件: Redis失敗、S3成功
        期待: S3からデータ取得、fallback_count=1
        """
        # Arrange
        import pandas as pd
        test_df = pd.DataFrame({
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        }, index=pd.date_range('2025-10-15', periods=24, freq='h', name='timestamp_utc'))

        # Redis失敗
        self.ohlcv_cache.load_ohlcv.return_value = None

        # S3成功
        self.s3_repo.load_ohlcv.return_value = test_df

        # Redisキャッシュ成功
        self.ohlcv_cache.save_ohlcv.return_value = True

        # Act (chart use case, 30日: redis → s3 → yfinance)
        df, metadata = self.provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=30,  # 長期データでS3を使う
            use_case='chart'
        )

        # Assert
        assert df is not None
        assert len(df) == 24
        assert metadata['source'] == 's3'
        assert metadata['fallback_count'] == 1  # redis失敗 → s3成功

    def test_get_data_all_sources_fail(self):
        """get_data: 全ソース失敗

        条件: MT5, Redis, yfinance 全て失敗
        期待: None返却、error付きmetadata
        """
        # Arrange
        # 全ソース失敗
        self.ohlcv_cache.load_ohlcv.return_value = None
        self.mt5_collector.fetch_ohlcv_data.return_value = None
        self.yfinance_client.fetch_ohlcv_data.return_value = None

        # Act (trading use case: mt5 → redis → yfinance の順で試行)
        df, metadata = self.provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'
        )

        # Assert
        assert df is None
        assert 'error' in metadata
        assert metadata['fallback_count'] == 3  # 3つ全てのソースを試行

    def test_get_data_no_sources_available(self):
        """get_data: 利用可能なソースがない

        条件: 全ソースがNone（初期化されていない）
        期待: None返却、"No data sources available"エラー
        """
        # Arrange
        # 全ソースなしのプロバイダー作成
        provider_no_sources = OhlcvDataProvider(
            ohlcv_cache=None,
            mt5_data_collector=None,
            s3_repository=None,
            yfinance_client=None
        )

        # Act
        df, metadata = provider_no_sources.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading'
        )

        # Assert
        assert df is None
        assert 'error' in metadata
        assert 'No data sources available' in metadata['error']
        assert metadata['fallback_count'] == 0

    def test_get_data_force_source(self):
        """get_data: force_source指定

        条件: force_source='s3' 指定
        期待: 他のソースをスキップしてS3のみ試行
        """
        # Arrange
        import pandas as pd
        test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15', periods=24, freq='h'),
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        })

        # S3成功
        self.s3_repo.load_ohlcv.return_value = test_df
        self.ohlcv_cache.save_ohlcv.return_value = True

        # Act
        df, metadata = self.provider.get_data(
            symbol='USDJPY',
            timeframe='H1',
            period_days=1,
            use_case='trading',
            force_source='s3'
        )

        # Assert
        assert df is not None
        assert metadata['source'] == 's3'
        assert metadata['fallback_count'] == 0

        # Redis, MT5は呼ばれない
        self.ohlcv_cache.load_ohlcv.assert_not_called()
        self.mt5_collector.fetch_ohlcv_data.assert_not_called()

    # ========================================
    # _days_to_bars() テスト
    # ========================================

    def test_days_to_bars_h1(self):
        """bar数計算 - H1"""
        bars = self.provider._days_to_bars(7, 'H1')
        # 7日 * (5/7) * 24時間 = 120
        assert bars == 120

    def test_days_to_bars_m5(self):
        """bar数計算 - M5"""
        bars = self.provider._days_to_bars(1, 'M5')
        # 1日 * (5/7) * 288 = 約205
        assert bars > 0

    def test_days_to_bars_minimum(self):
        """bar数計算 - 最小値1"""
        bars = self.provider._days_to_bars(0, 'H1')
        assert bars == 1

    # ========================================
    # _fetch_from_redis() テスト
    # ========================================

    def test_fetch_from_redis_success(self):
        """Redis取得 - 成功"""
        import pandas as pd
        test_df = pd.DataFrame({'close': [100, 101, 102]})
        self.ohlcv_cache.load_ohlcv.return_value = test_df

        result = self.provider._fetch_from_redis('USDJPY', 'H1', 1)

        assert result is not None
        assert len(result) == 3
        self.ohlcv_cache.load_ohlcv.assert_called_once_with(
            symbol='USDJPY', timeframe='H1', days=1
        )

    def test_fetch_from_redis_empty(self):
        """Redis取得 - 空"""
        import pandas as pd
        self.ohlcv_cache.load_ohlcv.return_value = pd.DataFrame()

        result = self.provider._fetch_from_redis('USDJPY', 'H1', 1)

        assert result is None

    def test_fetch_from_redis_exception(self):
        """Redis取得 - 例外"""
        self.ohlcv_cache.load_ohlcv.side_effect = Exception("Redis error")

        result = self.provider._fetch_from_redis('USDJPY', 'H1', 1)

        assert result is None

    # ========================================
    # _fetch_from_mt5() テスト
    # ========================================

    def test_fetch_from_mt5_success(self):
        """MT5取得 - 成功"""
        import pandas as pd
        test_df = pd.DataFrame({'close': [100, 101, 102]})
        self.mt5_collector.fetch_ohlcv_data.return_value = test_df

        result = self.provider._fetch_from_mt5('USDJPY', 'H1', 1)

        assert result is not None
        assert len(result) == 3

    def test_fetch_from_mt5_empty(self):
        """MT5取得 - 空"""
        import pandas as pd
        self.mt5_collector.fetch_ohlcv_data.return_value = pd.DataFrame()

        result = self.provider._fetch_from_mt5('USDJPY', 'H1', 1)

        assert result is None

    def test_fetch_from_mt5_exception(self):
        """MT5取得 - 例外"""
        self.mt5_collector.fetch_ohlcv_data.side_effect = Exception("MT5 error")

        result = self.provider._fetch_from_mt5('USDJPY', 'H1', 1)

        assert result is None

    # ========================================
    # _fetch_from_s3() テスト
    # ========================================

    def test_fetch_from_s3_success(self):
        """S3取得 - 成功"""
        import pandas as pd
        test_df = pd.DataFrame({'close': [100, 101, 102]})
        self.s3_repo.load_ohlcv.return_value = test_df

        result = self.provider._fetch_from_s3('USDJPY', 'H1', 30)

        assert result is not None
        assert len(result) == 3

    def test_fetch_from_s3_exception(self):
        """S3取得 - 例外"""
        self.s3_repo.load_ohlcv.side_effect = Exception("S3 error")

        result = self.provider._fetch_from_s3('USDJPY', 'H1', 30)

        assert result is None

    # ========================================
    # _fetch_from_yfinance() テスト
    # ========================================

    def test_fetch_from_yfinance_success(self):
        """yfinance取得 - 成功"""
        import pandas as pd
        from datetime import datetime, timedelta
        import pytz
        # 'time'カラム付きのDataFrameを作成（yfinanceの期待形式）
        # period_days=30なので、30日以内のデータを生成
        now = datetime.now(pytz.UTC)
        dates = pd.date_range(end=now, periods=3, freq='h')
        test_df = pd.DataFrame({
            'time': dates,
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'close': [100, 101, 102],
            'volume': [1000, 1000, 1000]
        })
        # yfinanceのfetch_ohlcvメソッドはDataFrameを返す
        self.yfinance_client.fetch_ohlcv.return_value = test_df

        result = self.provider._fetch_from_yfinance('USDJPY', 'H1', 30)

        assert result is not None
        assert len(result) == 3

    def test_fetch_from_yfinance_exception(self):
        """yfinance取得 - 例外"""
        self.yfinance_client.fetch_ohlcv.side_effect = Exception("yfinance error")

        result = self.provider._fetch_from_yfinance('USDJPY', 'H1', 30)

        assert result is None

    # ========================================
    # _cache_result() テスト
    # ========================================

    def test_cache_result_success(self):
        """結果キャッシュ - 成功"""
        import pandas as pd
        from datetime import datetime, timedelta
        import pytz
        # 現在時刻付近のdatetimeインデックスを作成（24時間以内のデータ）
        now = datetime.now(pytz.UTC)
        dates = pd.date_range(end=now, periods=3, freq='h')
        test_df = pd.DataFrame({
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'close': [100, 101, 102],
            'volume': [1000, 1000, 1000]
        }, index=dates)

        # _cache_result は4引数: (self, df, symbol, timeframe)
        self.ohlcv_cache.save_ohlcv.return_value = True
        self.provider._cache_result(test_df, 'USDJPY', 'H1')

        self.ohlcv_cache.save_ohlcv.assert_called_once()

    def test_cache_result_exception(self):
        """結果キャッシュ - 例外"""
        import pandas as pd
        from datetime import datetime
        import pytz
        now = datetime.now(pytz.UTC)
        dates = pd.date_range(end=now, periods=3, freq='h')
        test_df = pd.DataFrame({
            'open': [99, 100, 101],
            'close': [100, 101, 102]
        }, index=dates)
        self.ohlcv_cache.save_ohlcv.side_effect = Exception("Cache error")

        # 例外が発生してもクラッシュしない
        self.provider._cache_result(test_df, 'USDJPY', 'H1')

    # ========================================
    # _update_stats() テスト
    # ========================================

    def test_update_stats(self):
        """統計更新"""
        initial_count = self.provider._stats['source_usage']['mt5']

        # _update_stats は4引数: (self, source, response_time, success)
        self.provider._update_stats('mt5', 0.1, True)

        assert self.provider._stats['source_usage']['mt5'] == initial_count + 1
        assert 0.1 in self.provider._stats['response_times']['mt5']

    # ========================================
    # _get_max_age() テスト
    # ========================================

    def test_get_max_age_m1(self):
        """最大経過時間 - M1"""
        from datetime import timedelta
        max_age = self.provider._get_max_age('M1')
        assert max_age == timedelta(minutes=5)

    def test_get_max_age_h1(self):
        """最大経過時間 - H1"""
        from datetime import timedelta
        max_age = self.provider._get_max_age('H1')
        assert max_age == timedelta(hours=2)  # 実装では2時間

    def test_get_max_age_d1(self):
        """最大経過時間 - D1"""
        from datetime import timedelta
        max_age = self.provider._get_max_age('D1')
        assert max_age == timedelta(days=1)  # 実装では1日


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])