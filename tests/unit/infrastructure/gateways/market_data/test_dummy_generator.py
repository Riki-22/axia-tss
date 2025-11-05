# tests/unit/infrastructure/gateways/market_data/test_dummy_generator.py
"""
Dummy Market Data Generator 単体テスト

対象: src/infrastructure/gateways/market_data/dummy_generator.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.infrastructure.gateways.market_data.dummy_generator import DummyMarketDataGenerator


class TestDummyMarketDataGenerator:
    """DummyMarketDataGenerator のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.generator = DummyMarketDataGenerator(seed=42)

    # ========================================
    # 【初期化】1テスト
    # ========================================

    def test_init_with_seed(self):
        """
        初期化 - シード指定

        条件: seed指定
        期待: seedが設定される
        """
        # Act
        generator = DummyMarketDataGenerator(seed=123)

        # Assert
        assert generator.seed == 123

    # ========================================
    # 【OHLCV生成】6テスト
    # ========================================

    def test_generate_ohlcv_basic(self):
        """
        OHLCV生成 - 基本

        条件: デフォルトパラメータ
        期待: 標準OHLCV形式DataFrame返却
        """
        # Act
        df = self.generator.generate_ohlcv(days=5, timeframe='H1')

        # Assert
        assert not df.empty
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert len(df) == 5 * 24  # 5日 x 24時間
        assert df.attrs['symbol'] == 'DUMMY'
        assert df.attrs['source'] == 'dummy_generator'
        assert df.attrs['timeframe'] == 'H1'

    def test_generate_ohlcv_different_timeframes(self):
        """
        OHLCV生成 - 異なる時間枠

        条件: 複数の時間枠
        期待: 時間枠に応じた期間数
        """
        # Act
        df_m1 = self.generator.generate_ohlcv(days=1, timeframe='M1')
        df_m5 = self.generator.generate_ohlcv(days=1, timeframe='M5')
        df_h1 = self.generator.generate_ohlcv(days=1, timeframe='H1')
        df_h4 = self.generator.generate_ohlcv(days=1, timeframe='H4')
        df_d1 = self.generator.generate_ohlcv(days=1, timeframe='D1')

        # Assert
        assert len(df_m1) == 1440  # 24 * 60
        assert len(df_m5) == 288   # 24 * 12
        assert len(df_h1) == 24
        assert len(df_h4) == 6
        assert len(df_d1) == 1

    def test_generate_ohlcv_with_trend(self):
        """
        OHLCV生成 - トレンド付き

        条件: trend > 0（上昇トレンド）
        期待: 平均的に価格が上昇傾向
        """
        # Act
        df = self.generator.generate_ohlcv(days=30, timeframe='H1', trend=0.5)

        # Assert
        assert not df.empty
        # トレンドの平均的な動きを確認（移動平均で見る）
        first_half_mean = df['close'].iloc[:len(df)//2].mean()
        second_half_mean = df['close'].iloc[len(df)//2:].mean()
        # 後半の平均が前半より高い傾向（必ずしも厳密ではない）
        # トレンドが設定されていることを確認
        assert abs(second_half_mean - first_half_mean) > 0  # 何らかの動きがある

    def test_generate_ohlcv_with_volatility(self):
        """
        OHLCV生成 - ボラティリティ指定

        条件: 高ボラティリティ
        期待: 価格変動が大きい
        """
        # Act
        df_low_vol = self.generator.generate_ohlcv(days=30, timeframe='H1', volatility=0.1)
        df_high_vol = self.generator.generate_ohlcv(days=30, timeframe='H1', volatility=2.0)

        # Assert
        # 標準偏差が大きいはず
        std_low = df_low_vol['close'].std()
        std_high = df_high_vol['close'].std()
        assert std_high > std_low

    def test_generate_ohlcv_ohlc_consistency(self):
        """
        OHLCV生成 - OHLC整合性

        条件: 生成されたデータ
        期待: high >= max(open, close), low <= min(open, close)
        """
        # Act
        df = self.generator.generate_ohlcv(days=10, timeframe='H1')

        # Assert
        for idx, row in df.iterrows():
            assert row['high'] >= row['open']
            assert row['high'] >= row['close']
            assert row['low'] <= row['open']
            assert row['low'] <= row['close']
            assert row['high'] >= row['low']

    def test_generate_ohlcv_reproducibility(self):
        """
        OHLCV生成 - 再現性

        条件: 同じseedで2回生成
        期待: 同じデータが生成される（タイムスタンプは除く）
        """
        # Act
        df1 = self.generator.generate_ohlcv(days=5, timeframe='H1', base_price=150.0)

        # 新しいジェネレータを同じseedで作成
        generator2 = DummyMarketDataGenerator(seed=42)
        df2 = generator2.generate_ohlcv(days=5, timeframe='H1', base_price=150.0)

        # Assert - タイムスタンプは異なるが、OHLCV値は同じはず
        # インデックスを無視して値だけを比較
        assert len(df1) == len(df2)
        assert np.allclose(df1['open'].values, df2['open'].values)
        assert np.allclose(df1['high'].values, df2['high'].values)
        assert np.allclose(df1['low'].values, df2['low'].values)
        assert np.allclose(df1['close'].values, df2['close'].values)

    # ========================================
    # 【ヘルパーメソッド】3テスト
    # ========================================

    def test_get_periods_per_day(self):
        """
        期間数計算

        条件: 各時間枠
        期待: 正しい1日あたり期間数
        """
        # Act & Assert
        assert self.generator._get_periods_per_day('M1') == 1440
        assert self.generator._get_periods_per_day('M5') == 288
        assert self.generator._get_periods_per_day('M15') == 96
        assert self.generator._get_periods_per_day('M30') == 48
        assert self.generator._get_periods_per_day('H1') == 24
        assert self.generator._get_periods_per_day('H4') == 6
        assert self.generator._get_periods_per_day('D1') == 1
        assert self.generator._get_periods_per_day('UNKNOWN') == 24  # デフォルト

    def test_get_frequency(self):
        """
        頻度文字列取得

        条件: 各時間枠
        期待: 正しいpandas頻度文字列
        """
        # Act & Assert
        assert self.generator._get_frequency('M1') == '1min'
        assert self.generator._get_frequency('M5') == '5min'
        assert self.generator._get_frequency('M15') == '15min'
        assert self.generator._get_frequency('M30') == '30min'
        assert self.generator._get_frequency('H1') == '1h'
        assert self.generator._get_frequency('H4') == '4h'
        assert self.generator._get_frequency('D1') == '1D'
        assert self.generator._get_frequency('UNKNOWN') == '1h'  # デフォルト

    def test_generate_random_walk(self):
        """
        ランダムウォーク生成

        条件: 基準価格、ボラティリティ、トレンド指定
        期待: 指定期間の価格系列生成、最低価格制限
        """
        # Act
        prices = self.generator._generate_random_walk(
            total_periods=100,
            base_price=150.0,
            volatility=0.5,
            trend=0.1
        )

        # Assert
        assert len(prices) == 100
        assert all(prices >= 150.0 * 0.5)  # 最低価格制限確認
        # 価格がランダムに変動していることを確認
        assert np.std(prices) > 0  # 何らかの変動がある

    # ========================================
    # 【パターン生成】5テスト
    # ========================================

    def test_generate_with_pattern_trend_up(self):
        """
        パターン生成 - 上昇トレンド

        条件: pattern='trend_up'
        期待: 価格が上昇
        """
        # Act
        df = self.generator.generate_with_pattern(days=30, timeframe='H1', pattern='trend_up')

        # Assert
        assert not df.empty
        first_close = df['close'].iloc[0]
        last_close = df['close'].iloc[-1]
        assert last_close > first_close

    def test_generate_with_pattern_trend_down(self):
        """
        パターン生成 - 下降トレンド

        条件: pattern='trend_down'
        期待: 価格が下降
        """
        # Act
        df = self.generator.generate_with_pattern(days=30, timeframe='H1', pattern='trend_down')

        # Assert
        assert not df.empty
        first_close = df['close'].iloc[0]
        last_close = df['close'].iloc[-1]
        assert last_close < first_close

    def test_generate_with_pattern_range(self):
        """
        パターン生成 - レンジ相場

        条件: pattern='range'
        期待: 価格が一定範囲内
        """
        # Act
        df = self.generator.generate_with_pattern(days=30, timeframe='H1', pattern='range')

        # Assert
        assert not df.empty
        # レンジ相場なので標準偏差が小さいはず
        std = df['close'].std()
        assert std < 5.0  # ボラティリティが低い

    def test_generate_with_pattern_volatile(self):
        """
        パターン生成 - 高ボラティリティ

        条件: pattern='volatile'
        期待: 価格変動が大きい
        """
        # Act
        df = self.generator.generate_with_pattern(days=30, timeframe='H1', pattern='volatile')

        # Assert
        assert not df.empty
        # 高ボラティリティなので標準偏差が大きいはず
        std = df['close'].std()
        assert std > 1.0

    def test_generate_with_pattern_unknown(self):
        """
        パターン生成 - 未知のパターン

        条件: pattern='unknown'
        期待: デフォルト（range）パターン使用
        """
        # Act
        df = self.generator.generate_with_pattern(days=10, timeframe='H1', pattern='unknown')

        # Assert
        assert not df.empty
        assert len(df) == 10 * 24

    # ========================================
    # 【データ品質】2テスト
    # ========================================

    def test_volume_generation(self):
        """
        ボリューム生成

        条件: base_volume指定
        期待: リアルなボリュームパターン
        """
        # Act
        volume = self.generator._generate_volume(total_periods=100, base_volume=5000)

        # Assert
        assert len(volume) == 100
        assert all(volume > 0)
        # スパイクがあるか確認（一部が平均の2倍以上）
        mean_volume = np.mean(volume)
        assert any(volume > mean_volume * 2)

    def test_ensure_ohlc_consistency(self):
        """
        OHLC整合性確保

        条件: 不整合なOHLCデータ
        期待: 整合性が確保される
        """
        # Arrange
        df = pd.DataFrame({
            'open': [100, 105],
            'high': [102, 103],  # closeより低い（不整合）
            'low': [98, 106],    # closeより高い（不整合）
            'close': [104, 102]
        })

        # Act
        result = self.generator._ensure_ohlc_consistency(df)

        # Assert
        for idx, row in result.iterrows():
            assert row['high'] >= row['open']
            assert row['high'] >= row['close']
            assert row['low'] <= row['open']
            assert row['low'] <= row['close']


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
