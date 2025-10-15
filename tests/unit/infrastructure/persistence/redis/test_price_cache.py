# tests/unit/infrastructure/persistence/redis/test_price_cache.py
"""PriceCache 単体テスト"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

from src.infrastructure.persistence.redis import RedisClient, PriceCache
from src.infrastructure.config.settings import settings


def create_test_dataframe(hours: int = 24) -> pd.DataFrame:
    """
    テスト用OHLCVデータフレームを作成
    
    Args:
        hours: データ時間数
    
    Returns:
        pd.DataFrame: OHLCVデータ
    """
    now = datetime.now(pytz.UTC)
    times = [now - timedelta(hours=i) for i in range(hours, 0, -1)]
    
    return pd.DataFrame({
        'open': [100.0 + i * 0.1 for i in range(hours)],
        'high': [101.0 + i * 0.1 for i in range(hours)],
        'low': [99.0 + i * 0.1 for i in range(hours)],
        'close': [100.5 + i * 0.1 for i in range(hours)],
        'volume': [1000 + i * 10 for i in range(hours)]
    }, index=pd.DatetimeIndex(times, name='time'))


class TestPriceCache:
    """PriceCache のテストクラス"""
    
    @classmethod
    def setup_class(cls):
        """テストクラス全体のセットアップ"""
        # Redis初期化
        RedisClient.reset_instance()
        RedisClient.get_instance(
            host=settings.redis_endpoint,
            port=settings.redis_port,
            db=settings.redis_db
        )
        cls.cache = PriceCache()
    
    def teardown_method(self):
        """各テストメソッド後のクリーンアップ"""
        # テストキーを削除
        client = self.cache.redis_client
        test_keys = client.keys("ohlcv:TEST*")
        if test_keys:
            client.delete(*test_keys)
    
    def test_save_ohlcv(self):
        """OHLCVデータ保存のテスト"""
        df = create_test_dataframe(24)
        
        result = self.cache.save_ohlcv(df, "TESTJPY", "H1")
        
        assert result is True
        assert self.cache.exists("TESTJPY", "H1") is True
    
    def test_load_ohlcv(self):
        """OHLCVデータ読み込みのテスト"""
        df_original = create_test_dataframe(24)
        
        # 保存
        self.cache.save_ohlcv(df_original, "TESTJPY", "H1")
        
        # 読み込み
        df_loaded = self.cache.load_ohlcv("TESTJPY", "H1")
        
        assert df_loaded is not None
        assert len(df_loaded) == 24
        
        # データの整合性確認
        # 注: UNIXタイムスタンプ（秒）変換でマイクロ秒は失われる
        # OHLCVデータは秒精度で十分なため、秒単位で比較
        pd.testing.assert_frame_equal(
            df_loaded.reset_index(drop=True),
            df_original.reset_index(drop=True),
            check_exact=False,
            rtol=1e-5
        )
        
        # タイムスタンプは秒単位で一致
        assert (df_loaded.index.floor('s') == df_original.index.floor('s')).all()
    
    def test_load_nonexistent(self):
        """存在しないデータの読み込み"""
        df = self.cache.load_ohlcv("NONEXISTENT", "H1")
        
        assert df is None
    
    def test_exists(self):
        """データ存在確認のテスト"""
        df = create_test_dataframe(24)
        
        # 存在しない
        assert self.cache.exists("TESTJPY", "H1") is False
        
        # 保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        
        # 存在する
        assert self.cache.exists("TESTJPY", "H1") is True
    
    def test_get_available_range(self):
        """データ期間取得のテスト"""
        df = create_test_dataframe(24)
        
        # 保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        
        # 期間取得
        date_range = self.cache.get_available_range("TESTJPY", "H1")
        
        assert date_range is not None
        start, end = date_range
        
        # 開始・終了時刻が正しい
        assert start == df.index[0]
        assert end == df.index[-1]
    
    def test_delete(self):
        """データ削除のテスト"""
        df = create_test_dataframe(24)
        
        # 保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        assert self.cache.exists("TESTJPY", "H1") is True
        
        # 削除
        result = self.cache.delete("TESTJPY", "H1")
        
        assert result is True
        assert self.cache.exists("TESTJPY", "H1") is False
    
    def test_clear_symbol(self):
        """通貨ペア単位削除のテスト"""
        df = create_test_dataframe(24)
        
        # 複数タイムフレーム保存
        timeframes = ["M15", "H1", "H4"]
        for tf in timeframes:
            self.cache.save_ohlcv(df, "TESTJPY", tf)
        
        # 全て存在確認
        for tf in timeframes:
            assert self.cache.exists("TESTJPY", tf) is True
        
        # 通貨ペア単位で削除
        deleted = self.cache.clear_symbol("TESTJPY")
        
        assert deleted >= len(timeframes)  # メタデータキーも含む
        
        # 全て削除されていることを確認
        for tf in timeframes:
            assert self.cache.exists("TESTJPY", tf) is False
    
    def test_load_with_date_filter(self):
        """日付フィルタ付き読み込みのテスト"""
        df = create_test_dataframe(48)  # 48時間分
        
        # 保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        
        # 最新24時間のみ取得
        df_filtered = self.cache.load_ohlcv("TESTJPY", "H1", days=1)
        
        assert df_filtered is not None
        assert len(df_filtered) <= 24
        
        # 最新データが含まれている（秒精度で比較）
        assert df_filtered.index[-1].floor('s') == df.index[-1].floor('s')
    
    def test_cache_stats(self):
        """統計情報取得のテスト"""
        df = create_test_dataframe(24)
        
        # データ保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        self.cache.save_ohlcv(df, "TESTJPY", "M15")
        
        # 統計取得
        stats = self.cache.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert stats['total_keys'] >= 2
        assert 'TESTJPY' in stats['symbols']
        assert 'H1' in stats['timeframes']
        assert 'M15' in stats['timeframes']
        assert stats['memory_used_mb'] > 0
    
    def test_memory_usage(self):
        """メモリ使用量取得のテスト"""
        memory = self.cache.get_memory_usage()
        
        assert isinstance(memory, dict)
        assert 'used_memory_mb' in memory
        assert 'status' in memory
        assert memory['used_memory_mb'] >= 0
        assert memory['status'] in ['OK', 'WARNING', 'CRITICAL']


class TestPriceCacheTTL:
    """PriceCache TTL機能のテスト"""
    
    @classmethod
    def setup_class(cls):
        """テストクラス全体のセットアップ"""
        RedisClient.reset_instance()
        RedisClient.get_instance(
            host=settings.redis_endpoint,
            port=settings.redis_port,
            db=settings.redis_db
        )
        cls.cache = PriceCache()
    
    def test_is_dst(self):
        """夏時間判定のテスト"""
        # 夏時間（7月）
        summer = datetime(2025, 7, 15, 12, 0, 0, tzinfo=pytz.UTC)
        assert self.cache._is_dst(summer) is True
        
        # 冬時間（1月）
        winter = datetime(2025, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        assert self.cache._is_dst(winter) is False
    
    def test_calculate_ttl_weekday(self):
        """平日のTTL計算テスト"""
        # 火曜 10:00 JST (= 火曜 01:00 UTC)
        tuesday = datetime(2025, 10, 14, 1, 0, 0, tzinfo=pytz.UTC)
        
        ttl = self.cache._calculate_ttl_until_ny_close(tuesday)
        
        # 次のNYクローズ（水曜 06:00 JST = 火曜 21:00 UTC）まで約20時間
        expected_hours = 20
        assert (expected_hours - 1) * 3600 < ttl < (expected_hours + 1) * 3600
    
    def test_calculate_ttl_weekend(self):
        """週末のTTL計算テスト"""
        # 金曜 20:00 JST (= 金曜 11:00 UTC)
        friday = datetime(2025, 10, 17, 11, 0, 0, tzinfo=pytz.UTC)
        
        ttl = self.cache._calculate_ttl_until_ny_close(friday)
        
        # 土曜 06:00 JST → 月曜 06:00 JST まで約58時間
        expected_hours = 58
        assert (expected_hours - 2) * 3600 < ttl < (expected_hours + 2) * 3600
    
    def test_ttl_set_on_save(self):
        """保存時のTTL設定確認"""
        df = create_test_dataframe(24)
        
        # 保存
        self.cache.save_ohlcv(df, "TESTJPY", "H1")
        
        # TTL確認
        key = self.cache._generate_key("TESTJPY", "H1")
        ttl = self.cache.redis_client.ttl(key)
        
        assert ttl > 0  # TTLが設定されている
        assert ttl <= 24 * 3600 * 3  # 最大3日以内


class TestPriceCacheSerialization:
    """PriceCache シリアライズのテスト"""
    
    @classmethod
    def setup_class(cls):
        """テストクラス全体のセットアップ"""
        RedisClient.reset_instance()
        RedisClient.get_instance(
            host=settings.redis.redis_endpoint,
            port=settings.redis.redis_port,
            db=settings.redis.redis_db
        )
        cls.cache = PriceCache()
    
    def test_serialize_deserialize(self):
        """シリアライズ/デシリアライズのテスト"""
        df_original = create_test_dataframe(24)
        
        # シリアライズ
        serialized = self.cache._serialize_dataframe(df_original)
        assert isinstance(serialized, bytes)
        
        # デシリアライズ
        df_restored = self.cache._deserialize_dataframe(serialized)
        
        # データの整合性確認（秒精度）
        pd.testing.assert_frame_equal(
            df_restored.reset_index(drop=True),
            df_original.reset_index(drop=True),
            check_exact=False,
            rtol=1e-5
        )
        
        # タイムスタンプは秒単位で一致
        assert (df_restored.index.floor('s') == df_original.index.floor('s')).all()
    
    def test_datetime_index_preservation(self):
        """DatetimeIndexの保存・復元テスト"""
        df = create_test_dataframe(24)
        
        # シリアライズ・デシリアライズ
        serialized = self.cache._serialize_dataframe(df)
        df_restored = self.cache._deserialize_dataframe(serialized)
        
        # インデックスがDatetimeIndex
        assert isinstance(df_restored.index, pd.DatetimeIndex)
        
        # UTCタイムゾーン
        assert df_restored.index.tz == pytz.UTC
        
        # 時刻が秒単位で一致
        assert (df.index.floor('s') == df_restored.index.floor('s')).all()
    
    def test_data_types_preservation(self):
        """データ型の保存・復元テスト"""
        df = create_test_dataframe(24)
        
        # シリアライズ・デシリアライズ
        serialized = self.cache._serialize_dataframe(df)
        df_restored = self.cache._deserialize_dataframe(serialized)
        
        # float64カラム
        for col in ['open', 'high', 'low', 'close']:
            assert df_restored[col].dtype == np.float64
        
        # int64カラム
        assert df_restored['volume'].dtype == np.int64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])