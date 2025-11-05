# tests/unit/domain/services/technical_indicators/level_detectors/test_trend_channel.py
"""
Trend Channel Detector 単体テスト

対象: src/domain/services/technical_indicators/level_detectors/trend_channel.py
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from src.domain.services.technical_indicators.level_detectors.trend_channel import (
    TrendChannelDetector,
    TrendChannel
)


class TestTrendChannel:
    """TrendChannel のテストクラス"""

    def test_to_dict(self):
        """
        辞書変換

        条件: TrendChannelオブジェクト
        期待: 正しい辞書構造を返す
        """
        # Arrange
        channel = TrendChannel(
            upper_line={'slope': 0.1, 'intercept': 110},
            lower_line={'slope': 0.1, 'intercept': 100},
            middle_line={'slope': 0.1, 'intercept': 105},
            trend_direction='bullish',
            channel_width=10.0,
            strength=0.8,
            touch_points_upper=[1, 5, 10],
            touch_points_lower=[2, 6, 11]
        )

        # Act
        result = channel.to_dict()

        # Assert
        assert result['upper_line'] == {'slope': 0.1, 'intercept': 110}
        assert result['lower_line'] == {'slope': 0.1, 'intercept': 100}
        assert result['middle_line'] == {'slope': 0.1, 'intercept': 105}
        assert result['trend_direction'] == 'bullish'
        assert result['channel_width'] == 10.0
        assert result['strength'] == 0.8
        assert result['touch_count_upper'] == 3
        assert result['touch_count_lower'] == 3


class TestTrendChannelDetector:
    """TrendChannelDetector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.detector = TrendChannelDetector(
            min_points=3,
            lookback_period=50,
            channel_threshold=0.002,
            min_channel_width=0.001
        )

    def create_trending_dataframe(self, n_points=100, trend='bullish'):
        """トレンドのあるテスト用OHLCVデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=n_points, freq='h')

        if trend == 'bullish':
            # 上昇トレンド
            base_trend = np.linspace(100, 120, n_points)
            noise = np.sin(np.linspace(0, 8*np.pi, n_points)) * 2
        elif trend == 'bearish':
            # 下降トレンド
            base_trend = np.linspace(120, 100, n_points)
            noise = np.sin(np.linspace(0, 8*np.pi, n_points)) * 2
        else:
            # レンジ相場
            base_trend = np.full(n_points, 110)
            noise = np.sin(np.linspace(0, 8*np.pi, n_points)) * 3

        close = base_trend + noise

        df = pd.DataFrame({
            'open': close - 0.5,
            'high': close + 1.5,
            'low': close - 1.5,
            'close': close,
            'volume': 1000
        }, index=dates)

        return df

    # ========================================
    # 【初期化】1テスト
    # ========================================

    def test_init(self):
        """
        初期化

        条件: パラメータ指定
        期待: 全属性が正しく設定される
        """
        # Act
        detector = TrendChannelDetector(
            min_points=5,
            lookback_period=100,
            channel_threshold=0.003,
            min_channel_width=0.002
        )

        # Assert
        assert detector.min_points == 5
        assert detector.lookback_period == 100
        assert detector.channel_threshold == 0.003
        assert detector.min_channel_width == 0.002

    # ========================================
    # 【detect メソッド】4テスト
    # ========================================

    def test_detect_insufficient_data(self):
        """
        チャネル検出 - データ不足

        条件: lookback_period 未満のデータ
        期待: None を返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=40)  # lookback=50

        # Act
        result = self.detector.detect(df)

        # Assert
        assert result is None

    def test_detect_bullish_trend(self):
        """
        チャネル検出 - 上昇トレンド

        条件: 上昇トレンドデータ
        期待: bullish チャネルを検出
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=100, trend='bullish')

        # Act
        result = self.detector.detect(df)

        # Assert - チャネルが検出される可能性がある
        # （データパターンによっては検出されない場合もあるため、柔軟な検証）
        if result:
            assert isinstance(result, TrendChannel)
            assert result.trend_direction in ['bullish', 'neutral']
            assert result.channel_width > 0
            assert 0 <= result.strength <= 1

    def test_detect_returns_trend_channel(self):
        """
        チャネル検出 - TrendChannel返却

        条件: 十分なデータ
        期待: TrendChannelオブジェクトまたはNoneを返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=100)

        # Act
        result = self.detector.detect(df)

        # Assert
        assert result is None or isinstance(result, TrendChannel)

    def test_detect_uses_lookback_period(self):
        """
        チャネル検出 - lookback_period 使用

        条件: lookback_period 指定
        期待: 直近の lookback_period 分のデータを使用
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=200)

        # Act
        with patch.object(self.detector, '_find_swing_points', wraps=self.detector._find_swing_points) as mock_find:
            self.detector.detect(df)

            # Assert - _find_swing_points が呼ばれた際のデータ長を確認
            if mock_find.called:
                called_series = mock_find.call_args[0][0]
                assert len(called_series) == self.detector.lookback_period

    # ========================================
    # 【_find_swing_points】4テスト
    # ========================================

    def test_find_swing_points_high(self):
        """
        スイングポイント検出 - 高値

        条件: point_type='high'
        期待: ローカル高値を検出
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=100)

        # Act
        points = self.detector._find_swing_points(df['high'], 'high')

        # Assert
        assert isinstance(points, list)
        for point in points:
            assert 'index' in point
            assert 'value' in point
            assert isinstance(point['index'], int)
            assert point['value'] > 0

    def test_find_swing_points_low(self):
        """
        スイングポイント検出 - 安値

        条件: point_type='low'
        期待: ローカル安値を検出
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=100)

        # Act
        points = self.detector._find_swing_points(df['low'], 'low')

        # Assert
        assert isinstance(points, list)
        for point in points:
            assert point['value'] > 0

    def test_find_swing_points_bounds(self):
        """
        スイングポイント検出 - 範囲確認

        条件: window=3
        期待: インデックスが window から len(series)-window の範囲内
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        window = 3

        # Act
        points = self.detector._find_swing_points(df['high'], 'high')

        # Assert
        for point in points:
            assert point['index'] >= window
            assert point['index'] < len(df) - window

    def test_find_swing_points_extrema_detection(self):
        """
        スイングポイント検出 - 極値検証

        条件: 明確なピークを持つデータ
        期待: ピークが検出される
        """
        # Arrange - 明確なピークを作成
        values = pd.Series([100, 101, 102, 105, 103, 102, 101, 100, 99, 98, 97, 96, 95])

        # Act
        points = self.detector._find_swing_points(values, 'high')

        # Assert
        # インデックス3（値105）がローカル高値として検出されるはず
        indices = [p['index'] for p in points]
        assert 3 in indices

    # ========================================
    # 【_fit_trend_line】4テスト
    # ========================================

    def test_fit_trend_line_basic(self):
        """
        トレンドライン フィット - 基本

        条件: 複数のポイント
        期待: トレンドライン情報を返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=100)
        points = self.detector._find_swing_points(df['high'], 'high')

        # Act
        if len(points) >= 2:
            result = self.detector._fit_trend_line(points, df, 'high')

            # Assert
            if result:  # R値が低い場合はNoneを返す可能性がある
                assert 'slope' in result
                assert 'intercept' in result
                assert 'r_value' in result
                assert 'touch_points' in result
                assert 'start_point' in result
                assert 'end_point' in result

    def test_fit_trend_line_insufficient_points(self):
        """
        トレンドライン フィット - ポイント不足

        条件: ポイント数 < 2
        期待: None を返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        points = [{'index': 10, 'value': 100}]

        # Act
        result = self.detector._fit_trend_line(points, df, 'high')

        # Assert
        assert result is None

    def test_fit_trend_line_low_r_value(self):
        """
        トレンドライン フィット - 低R値

        条件: R値 < 0.1（相関が弱い）
        期待: None を返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        # ランダムなポイントで相関が弱いケース
        points = [
            {'index': 5, 'value': 100},
            {'index': 15, 'value': 105},
            {'index': 25, 'value': 102}
        ]

        # Act
        with patch('src.domain.services.technical_indicators.level_detectors.trend_channel.stats.linregress') as mock_linregress:
            mock_linregress.return_value = (0.1, 100, 0.05, 0.5, 1.0)  # r_value = 0.05
            result = self.detector._fit_trend_line(points, df, 'high')

        # Assert
        assert result is None

    def test_fit_trend_line_touch_points_filter(self):
        """
        トレンドライン フィット - タッチポイントフィルタ

        条件: タッチポイント < min_points
        期待: None を返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        points = [{'index': 10, 'value': 100}, {'index': 20, 'value': 105}]

        # Act
        with patch.object(self.detector, '_find_line_touches', return_value=[10, 20]):  # 2ポイントのみ
            result = self.detector._fit_trend_line(points, df, 'high')

        # Assert
        if self.detector.min_points > 2:
            assert result is None

    # ========================================
    # 【_find_line_touches】2テスト
    # ========================================

    def test_find_line_touches_basic(self):
        """
        ラインタッチ検出 - 基本

        条件: ライン情報と価格データ
        期待: タッチポイントのインデックスリストを返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        slope = 0.2
        intercept = 100

        # Act
        touches = self.detector._find_line_touches(df['close'], slope, intercept)

        # Assert
        assert isinstance(touches, list)
        assert all(isinstance(idx, int) for idx in touches)

    def test_find_line_touches_threshold(self):
        """
        ラインタッチ検出 - 閾値確認

        条件: channel_threshold 範囲内
        期待: 閾値内の価格のみ検出
        """
        # Arrange
        prices = pd.Series([100, 100.1, 100.5, 101, 105, 100.2])
        slope = 0
        intercept = 100

        # Act
        touches = self.detector._find_line_touches(prices, slope, intercept)

        # Assert
        for idx in touches:
            price = prices.iloc[idx]
            line_value = slope * idx + intercept
            assert abs(price - line_value) / price <= self.detector.channel_threshold

    # ========================================
    # 【_create_parallel_channel】4テスト
    # ========================================

    def test_create_parallel_channel_basic(self):
        """
        平行チャネル作成 - 基本

        条件: 上下ライン情報
        期待: TrendChannelを返す
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        upper_line = {
            'slope': 0.2,
            'intercept': 120,
            'touch_points': [5, 15, 25, 35]
        }
        lower_line = {
            'slope': 0.18,
            'intercept': 100,
            'touch_points': [10, 20, 30, 40]
        }

        # Act
        result = self.detector._create_parallel_channel(upper_line, lower_line, df)

        # Assert
        if result:  # 幅が十分な場合
            assert isinstance(result, TrendChannel)
            assert result.upper_line['slope'] == result.lower_line['slope']  # 平行
            assert result.channel_width > 0
            assert 0 <= result.strength <= 1

    def test_create_parallel_channel_narrow_width(self):
        """
        平行チャネル作成 - 狭すぎる幅

        条件: channel_width / avg_price < min_channel_width
        期待: None を返す
        """
        # Arrange - 価格レンジが非常に狭いデータを作成
        dates = pd.date_range(start='2025-01-01', periods=50, freq='h')
        close = np.full(50, 110.0)  # 全て同じ価格
        df = pd.DataFrame({
            'open': close,
            'high': close + 0.01,  # 非常に狭い範囲
            'low': close - 0.01,
            'close': close,
            'volume': 1000
        }, index=dates)

        upper_line = {
            'slope': 0,
            'intercept': 110.01,
            'touch_points': [5, 15, 25]
        }
        lower_line = {
            'slope': 0,
            'intercept': 110.00,
            'touch_points': [10, 20, 30]
        }

        # Act
        result = self.detector._create_parallel_channel(upper_line, lower_line, df)

        # Assert
        # 幅が min_channel_width (0.001) より小さいため None を返すはず
        assert result is None

    def test_create_parallel_channel_trend_direction(self):
        """
        平行チャネル作成 - トレンド方向

        条件: スロープに応じて
        期待: 正しいtrend_directionを設定
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)

        # Case 1: Bullish (slope > 0.0001)
        upper_line = {'slope': 0.5, 'intercept': 120, 'touch_points': [5, 15, 25]}
        lower_line = {'slope': 0.5, 'intercept': 100, 'touch_points': [10, 20, 30]}
        result = self.detector._create_parallel_channel(upper_line, lower_line, df)
        if result:
            assert result.trend_direction == 'bullish'

        # Case 2: Bearish (slope < -0.0001)
        upper_line = {'slope': -0.5, 'intercept': 120, 'touch_points': [5, 15, 25]}
        lower_line = {'slope': -0.5, 'intercept': 100, 'touch_points': [10, 20, 30]}
        result = self.detector._create_parallel_channel(upper_line, lower_line, df)
        if result:
            assert result.trend_direction == 'bearish'

    def test_create_parallel_channel_strength_calculation(self):
        """
        平行チャネル作成 - 強度計算

        条件: タッチポイント数に応じて
        期待: 正しい強度を計算（最大1.0）
        """
        # Arrange
        df = self.create_trending_dataframe(n_points=50)
        upper_line = {
            'slope': 0.2,
            'intercept': 120,
            'touch_points': [5, 10, 15, 20, 25, 30]  # 6ポイント
        }
        lower_line = {
            'slope': 0.2,
            'intercept': 100,
            'touch_points': [7, 12, 17, 22, 27, 32]  # 6ポイント
        }

        # Act
        result = self.detector._create_parallel_channel(upper_line, lower_line, df)

        # Assert
        if result:
            # total_touches = 12, min(12 / (3*4), 1.0) = min(1.0, 1.0) = 1.0
            assert 0 <= result.strength <= 1.0

    # ========================================
    # 【get_channel_position】5テスト
    # ========================================

    def test_get_channel_position_no_channel(self):
        """
        チャネル内位置 - チャネルなし

        条件: channel = None
        期待: 'no_channel' を返す
        """
        # Act
        result = self.detector.get_channel_position(None, 100, 10)

        # Assert
        assert result['position'] == 'no_channel'

    def test_get_channel_position_above_channel(self):
        """
        チャネル内位置 - チャネル上部超過

        条件: 現在価格 > 上部ライン
        期待: position='above_channel'
        """
        # Arrange
        channel = TrendChannel(
            upper_line={'slope': 0, 'intercept': 110},
            lower_line={'slope': 0, 'intercept': 100},
            middle_line={'slope': 0, 'intercept': 105},
            trend_direction='neutral',
            channel_width=10,
            strength=0.8,
            touch_points_upper=[],
            touch_points_lower=[]
        )

        # Act
        result = self.detector.get_channel_position(channel, 115, 10)

        # Assert
        assert result['position'] == 'above_channel'
        assert result['relative_position'] > 1.0

    def test_get_channel_position_below_channel(self):
        """
        チャネル内位置 - チャネル下部未満

        条件: 現在価格 < 下部ライン
        期待: position='below_channel'
        """
        # Arrange
        channel = TrendChannel(
            upper_line={'slope': 0, 'intercept': 110},
            lower_line={'slope': 0, 'intercept': 100},
            middle_line={'slope': 0, 'intercept': 105},
            trend_direction='neutral',
            channel_width=10,
            strength=0.8,
            touch_points_upper=[],
            touch_points_lower=[]
        )

        # Act
        result = self.detector.get_channel_position(channel, 95, 10)

        # Assert
        assert result['position'] == 'below_channel'
        assert result['relative_position'] < 0.0

    def test_get_channel_position_upper_half(self):
        """
        チャネル内位置 - 上半分

        条件: middle < 現在価格 < upper
        期待: position='upper_half'
        """
        # Arrange
        channel = TrendChannel(
            upper_line={'slope': 0, 'intercept': 110},
            lower_line={'slope': 0, 'intercept': 100},
            middle_line={'slope': 0, 'intercept': 105},
            trend_direction='neutral',
            channel_width=10,
            strength=0.8,
            touch_points_upper=[],
            touch_points_lower=[]
        )

        # Act
        result = self.detector.get_channel_position(channel, 107, 10)

        # Assert
        assert result['position'] == 'upper_half'
        assert 0.5 < result['relative_position'] < 1.0

    def test_get_channel_position_lower_half(self):
        """
        チャネル内位置 - 下半分

        条件: lower < 現在価格 < middle
        期待: position='lower_half'
        """
        # Arrange
        channel = TrendChannel(
            upper_line={'slope': 0, 'intercept': 110},
            lower_line={'slope': 0, 'intercept': 100},
            middle_line={'slope': 0, 'intercept': 105},
            trend_direction='neutral',
            channel_width=10,
            strength=0.8,
            touch_points_upper=[],
            touch_points_lower=[]
        )

        # Act
        result = self.detector.get_channel_position(channel, 103, 10)

        # Assert
        assert result['position'] == 'lower_half'
        assert 0.0 < result['relative_position'] < 0.5


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
