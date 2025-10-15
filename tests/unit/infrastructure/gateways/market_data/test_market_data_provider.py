# tests/unit/infrastructure/gateways/market_data/test_market_data_provider.py
"""MarketDataProvider 単体テスト"""

import pytest
from unittest.mock import Mock

from src.infrastructure.gateways.market_data.market_data_provider import MarketDataProvider


class TestMarketDataProvider:
    """MarketDataProvider のテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックオブジェクト作成
        self.price_cache = Mock()
        self.mt5_collector = Mock()
        self.s3_repo = Mock()
        self.yfinance_client = Mock()
        
        # プロバイダー作成（全ソース利用可能）
        self.provider = MarketDataProvider(
            price_cache=self.price_cache,
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
        provider = MarketDataProvider(
            price_cache=self.price_cache
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
        assert len(stats['source_usage']) == 0
    
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
        provider = MarketDataProvider(price_cache=self.price_cache)
        
        sources = ['redis', 'mt5', 's3', 'yfinance']
        filtered = provider._filter_available_sources(sources)
        
        assert filtered == ['redis']
    
    def test_filter_available_sources_none(self):
        """利用可能なソースがない"""
        provider = MarketDataProvider(price_cache=self.price_cache)
        
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


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])