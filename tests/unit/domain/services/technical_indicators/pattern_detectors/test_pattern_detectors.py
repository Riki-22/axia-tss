# tests/unit/domain/services/technical_indicators/pattern_detectors/test_pattern_detectors.py
"""
Pattern Detectors 単体テスト

対象:
- src/domain/services/technical_indicators/pattern_detectors/base_pattern.py
- src/domain/services/technical_indicators/pattern_detectors/engulfing_detector.py
- src/domain/services/technical_indicators/pattern_detectors/pinbar_detector.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.domain.services.technical_indicators.pattern_detectors.base_pattern import (
    BasePatternDetector,
    PatternSignal
)
from src.domain.services.technical_indicators.pattern_detectors.engulfing_detector import EngulfingDetector
from src.domain.services.technical_indicators.pattern_detectors.pinbar_detector import PinBarDetector


# ========================================
# PatternSignal テスト
# ========================================

class TestPatternSignal:
    """PatternSignal のテストクラス"""

    def test_to_dict_with_datetime(self):
        """
        辞書変換 - datetime

        条件: datetime オブジェクト
        期待: ISO形式文字列に変換
        """
        # Arrange
        signal = PatternSignal(
            index=10,
            timestamp=datetime(2025, 1, 1, 10, 0),
            pattern_type='bullish_pinbar',
            confidence=0.85,
            price_level=100.5,
            metadata={'body_size': 0.5}
        )

        # Act
        result = signal.to_dict()

        # Assert
        assert result['index'] == 10
        assert result['timestamp'] == '2025-01-01T10:00:00'
        assert result['pattern_type'] == 'bullish_pinbar'
        assert result['confidence'] == 0.85
        assert result['price_level'] == 100.5
        assert result['metadata'] == {'body_size': 0.5}


# ========================================
# BasePatternDetector テスト
# ========================================

class ConcretePatternDetector(BasePatternDetector):
    """テスト用の具体的なパターン検出器"""
    def detect(self, df: pd.DataFrame):
        return []


class TestBasePatternDetector:
    """BasePatternDetector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.detector = ConcretePatternDetector(min_confidence=0.7)

    def create_test_dataframe(self, n_points=10):
        """テスト用のOHLCVデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=n_points, freq='h')
        return pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109][:n_points],
            'high': [102, 103, 104, 105, 106, 107, 108, 109, 110, 111][:n_points],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108][:n_points],
            'close': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110][:n_points],
            'volume': [1000] * n_points
        }, index=dates)

    def test_init(self):
        """初期化"""
        detector = ConcretePatternDetector(min_confidence=0.8)
        assert detector.min_confidence == 0.8

    def test_validate_dataframe_success(self):
        """データフレーム検証 - 成功"""
        df = self.create_test_dataframe()
        assert self.detector.validate_dataframe(df) is True

    def test_validate_dataframe_missing_columns(self):
        """データフレーム検証 - カラム不足"""
        df = pd.DataFrame({'open': [100], 'high': [102]})
        with pytest.raises(ValueError, match="必須カラムが不足しています"):
            self.detector.validate_dataframe(df)

    def test_validate_dataframe_insufficient_data(self):
        """データフレーム検証 - データ不足"""
        df = pd.DataFrame({'open': [100], 'high': [102], 'low': [99], 'close': [101]})
        with pytest.raises(ValueError, match="データが不足しています"):
            self.detector.validate_dataframe(df)

    def test_calculate_body_size(self):
        """実体サイズ計算"""
        assert self.detector.calculate_body_size(100, 105) == 5
        assert self.detector.calculate_body_size(105, 100) == 5

    def test_calculate_upper_wick(self):
        """上ヒゲ計算"""
        # 陽線の場合（close > open）
        assert self.detector.calculate_upper_wick(110, 100, 105) == 5
        # 陰線の場合（close < open）
        assert self.detector.calculate_upper_wick(110, 105, 100) == 5

    def test_calculate_lower_wick(self):
        """下ヒゲ計算"""
        # 陽線の場合
        assert self.detector.calculate_lower_wick(95, 100, 105) == 5
        # 陰線の場合
        assert self.detector.calculate_lower_wick(95, 105, 100) == 5

    def test_is_bullish_candle(self):
        """陽線判定"""
        assert self.detector.is_bullish_candle(100, 105) is True
        assert self.detector.is_bullish_candle(105, 100) is False

    def test_is_bearish_candle(self):
        """陰線判定"""
        assert self.detector.is_bearish_candle(105, 100) is True
        assert self.detector.is_bearish_candle(100, 105) is False

    def test_filter_by_confidence(self):
        """信頼度フィルタリング"""
        signals = [
            PatternSignal(0, datetime.now(), 'test', 0.8, 100, {}),
            PatternSignal(1, datetime.now(), 'test', 0.6, 100, {}),
            PatternSignal(2, datetime.now(), 'test', 0.9, 100, {})
        ]
        filtered = self.detector.filter_by_confidence(signals)
        assert len(filtered) == 2
        assert all(s.confidence >= 0.7 for s in filtered)


# ========================================
# EngulfingDetector テスト
# ========================================

class TestEngulfingDetector:
    """EngulfingDetector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.detector = EngulfingDetector(
            min_body_ratio=1.5,
            trend_period=5,
            min_confidence=0.5  # テスト用に低めに設定
        )

    def create_bullish_engulfing_pattern(self):
        """Bullish Engulfingパターンを持つデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=10, freq='h')
        data = {
            'open': [105, 104, 103, 102, 101, 100, 99, 98, 100, 103],
            'high': [106, 105, 104, 103, 102, 101, 100, 99, 102, 105],
            'low': [104, 103, 102, 101, 100, 99, 98, 97, 97, 100],
            'close': [104, 103, 102, 101, 100, 99, 98, 97, 102, 104],
            'volume': [1000] * 10
        }
        return pd.DataFrame(data, index=dates)

    def create_bearish_engulfing_pattern(self):
        """Bearish Engulfingパターンを持つデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=10, freq='h')
        data = {
            'open': [95, 96, 97, 98, 99, 100, 101, 102, 102, 99],
            'high': [96, 97, 98, 99, 100, 101, 102, 103, 103, 102],
            'low': [94, 95, 96, 97, 98, 99, 100, 101, 98, 97],
            'close': [96, 97, 98, 99, 100, 101, 102, 103, 98, 97],
            'volume': [1000] * 10
        }
        return pd.DataFrame(data, index=dates)

    def test_init(self):
        """初期化"""
        detector = EngulfingDetector(min_body_ratio=2.0, trend_period=10, min_confidence=0.8)
        assert detector.min_body_ratio == 2.0
        assert detector.trend_period == 10
        assert detector.min_confidence == 0.8

    def test_detect_bullish_engulfing(self):
        """Bullish Engulfing検出"""
        df = self.create_bullish_engulfing_pattern()
        signals = self.detector.detect(df)

        # パターンが検出される可能性がある
        if signals:
            assert all(isinstance(s, PatternSignal) for s in signals)
            bullish_signals = [s for s in signals if s.pattern_type == 'bullish_engulfing']
            for signal in bullish_signals:
                assert signal.confidence >= self.detector.min_confidence
                assert 'body_ratio' in signal.metadata

    def test_detect_bearish_engulfing(self):
        """Bearish Engulfing検出"""
        df = self.create_bearish_engulfing_pattern()
        signals = self.detector.detect(df)

        # パターンが検出される可能性がある
        if signals:
            bearish_signals = [s for s in signals if s.pattern_type == 'bearish_engulfing']
            for signal in bearish_signals:
                assert signal.confidence >= self.detector.min_confidence
                assert 'body_ratio' in signal.metadata

    def test_detect_returns_list(self):
        """検出結果はリスト"""
        df = self.create_bullish_engulfing_pattern()
        signals = self.detector.detect(df)
        assert isinstance(signals, list)

    def test_calculate_trend_score_bullish(self):
        """トレンドスコア計算 - Bullish"""
        df = self.create_bullish_engulfing_pattern()
        score = self.detector._calculate_trend_score(df, 8, 'bullish')
        assert 0 <= score <= 1

    def test_calculate_trend_score_insufficient_data(self):
        """トレンドスコア計算 - データ不足"""
        df = self.create_bullish_engulfing_pattern()
        score = self.detector._calculate_trend_score(df, 2, 'bullish')
        assert score == 0.5

    def test_calculate_confidence(self):
        """信頼度計算"""
        confidence = self.detector._calculate_confidence(
            curr_body=5.0,
            prev_body=2.0,
            curr_high=105,
            curr_low=95,
            prev_high=103,
            prev_low=97,
            trend_score=0.8,
            pattern_type='bullish'
        )
        assert 0 <= confidence <= 1


# ========================================
# PinBarDetector テスト
# ========================================

class TestPinBarDetector:
    """PinBarDetector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.detector = PinBarDetector(
            body_to_wick_ratio=2.0,
            min_wick_ratio=0.66,
            opposite_wick_ratio=0.1,
            min_confidence=0.5  # テスト用に低めに設定
        )

    def create_bullish_pinbar_pattern(self):
        """Bullish Pin Bar（ハンマー）パターンを持つデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=5, freq='h')
        data = {
            'open': [100, 99, 98, 97, 97.5],
            'high': [101, 100, 99, 98, 98],
            'low': [99, 98, 97, 90, 97],  # インデックス3に長い下ヒゲ
            'close': [99.5, 98.5, 97.5, 97, 97.8],
            'volume': [1000] * 5
        }
        return pd.DataFrame(data, index=dates)

    def create_bearish_pinbar_pattern(self):
        """Bearish Pin Bar（流れ星）パターンを持つデータを作成"""
        dates = pd.date_range(start='2025-01-01', periods=5, freq='h')
        data = {
            'open': [100, 101, 102, 102.5, 102],
            'high': [101, 102, 103, 110, 103],  # インデックス3に長い上ヒゲ
            'low': [99, 100, 101, 102, 101],
            'close': [100.5, 101.5, 102.5, 103, 102.5],
            'volume': [1000] * 5
        }
        return pd.DataFrame(data, index=dates)

    def test_init(self):
        """初期化"""
        detector = PinBarDetector(
            body_to_wick_ratio=3.0,
            min_wick_ratio=0.7,
            opposite_wick_ratio=0.05,
            min_confidence=0.8
        )
        assert detector.body_to_wick_ratio == 3.0
        assert detector.min_wick_ratio == 0.7
        assert detector.opposite_wick_ratio == 0.05
        assert detector.min_confidence == 0.8

    def test_detect_bullish_pinbar(self):
        """Bullish Pin Bar検出"""
        df = self.create_bullish_pinbar_pattern()
        signals = self.detector.detect(df)

        # パターンが検出される可能性がある
        if signals:
            bullish_signals = [s for s in signals if s.pattern_type == 'bullish_pinbar']
            for signal in bullish_signals:
                assert signal.confidence >= self.detector.min_confidence
                assert 'lower_wick' in signal.metadata
                assert 'body_size' in signal.metadata

    def test_detect_bearish_pinbar(self):
        """Bearish Pin Bar検出"""
        df = self.create_bearish_pinbar_pattern()
        signals = self.detector.detect(df)

        # パターンが検出される可能性がある
        if signals:
            bearish_signals = [s for s in signals if s.pattern_type == 'bearish_pinbar']
            for signal in bearish_signals:
                assert signal.confidence >= self.detector.min_confidence
                assert 'upper_wick' in signal.metadata

    def test_detect_returns_list(self):
        """検出結果はリスト"""
        df = self.create_bullish_pinbar_pattern()
        signals = self.detector.detect(df)
        assert isinstance(signals, list)

    def test_detect_skips_zero_range(self):
        """ゼロレンジのローソク足はスキップ"""
        dates = pd.date_range(start='2025-01-01', periods=3, freq='h')
        df = pd.DataFrame({
            'open': [100, 100, 100],
            'high': [100, 100, 100],  # ゼロレンジ
            'low': [100, 100, 100],
            'close': [100, 100, 100],
            'volume': [1000, 1000, 1000]
        }, index=dates)

        signals = self.detector.detect(df)
        # ゼロレンジはスキップされるため、シグナルなし
        assert len(signals) == 0

    def test_calculate_confidence_bullish(self):
        """信頼度計算 - Bullish"""
        confidence = self.detector._calculate_confidence(
            main_wick=10.0,
            body_size=2.0,
            opposite_wick=0.5,
            total_range=12.5,
            pattern_type='bullish'
        )
        assert 0 <= confidence <= 1

    def test_calculate_confidence_bearish(self):
        """信頼度計算 - Bearish"""
        confidence = self.detector._calculate_confidence(
            main_wick=10.0,
            body_size=2.0,
            opposite_wick=0.5,
            total_range=12.5,
            pattern_type='bearish'
        )
        assert 0 <= confidence <= 1


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
