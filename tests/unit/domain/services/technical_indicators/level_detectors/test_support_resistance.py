# tests/unit/domain/services/technical_indicators/level_detectors/test_support_resistance.py
"""
Support/Resistance Detector 単体テスト

対象: src/domain/services/technical_indicators/level_detectors/support_resistance.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.domain.services.technical_indicators.level_detectors.support_resistance import (
    SupportResistanceDetector,
    PriceLevel
)


class TestPriceLevel:
    """PriceLevel のテストクラス"""

    def test_to_dict_with_datetime(self):
        """
        辞書変換 - datetime オブジェクト

        条件: datetime オブジェクトを使用
        期待: ISO形式の文字列に変換される
        """
        # Arrange
        level = PriceLevel(
            level=100.0,
            level_type='support',
            strength=0.5,
            touch_points=[1, 2, 3],
            first_touch=datetime(2025, 1, 1, 10, 0),
            last_touch=datetime(2025, 1, 2, 15, 30)
        )

        # Act
        result = level.to_dict()

        # Assert
        assert result['level'] == 100.0
        assert result['level_type'] == 'support'
        assert result['strength'] == 0.5
        assert result['touch_count'] == 3
        assert result['first_touch'] == '2025-01-01T10:00:00'
        assert result['last_touch'] == '2025-01-02T15:30:00'

    def test_to_dict_with_string(self):
        """
        辞書変換 - 文字列

        条件: 文字列のタイムスタンプ
        期待: 文字列のまま変換される
        """
        # Arrange
        level = PriceLevel(
            level=150.5,
            level_type='resistance',
            strength=0.8,
            touch_points=[5, 10, 15, 20],
            first_touch='2025-01-01',
            last_touch='2025-01-10'
        )

        # Act
        result = level.to_dict()

        # Assert
        assert result['level'] == 150.5
        assert result['level_type'] == 'resistance'
        assert result['touch_count'] == 4
        assert result['first_touch'] == '2025-01-01'
        assert result['last_touch'] == '2025-01-10'


class TestSupportResistanceDetector:
    """SupportResistanceDetector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.detector = SupportResistanceDetector(
            window=20,
            min_touches=2,
            price_threshold=0.001,
            max_levels=3
        )

    def create_test_dataframe(self, n_points=100):
        """テスト用のOHLCVデータフレームを作成"""
        dates = pd.date_range(start='2025-01-01', periods=n_points, freq='h')

        # サポート/レジスタンスレベルを持つ価格データ
        close = np.linspace(100, 110, n_points) + np.sin(np.linspace(0, 4*np.pi, n_points)) * 5

        df = pd.DataFrame({
            'open': close - 0.5,
            'high': close + 1.0,
            'low': close - 1.0,
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
        detector = SupportResistanceDetector(
            window=10,
            min_touches=3,
            price_threshold=0.002,
            max_levels=5
        )

        # Assert
        assert detector.window == 10
        assert detector.min_touches == 3
        assert detector.price_threshold == 0.002
        assert detector.max_levels == 5

    # ========================================
    # 【detect メソッド】4テスト
    # ========================================

    def test_detect_insufficient_data(self):
        """
        レベル検出 - データ不足

        条件: window * 2 未満のデータ
        期待: 空リストを返す
        """
        # Arrange
        df = self.create_test_dataframe(n_points=30)  # window=20, 必要=40

        # Act
        support, resistance = self.detector.detect(df)

        # Assert
        assert support == []
        assert resistance == []

    def test_detect_basic(self):
        """
        レベル検出 - 基本

        条件: 十分なデータ
        期待: サポート/レジスタンスレベルが検出される
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        support, resistance = self.detector.detect(df)

        # Assert
        assert isinstance(support, list)
        assert isinstance(resistance, list)
        # max_levels=3 なので、最大3つまで
        assert len(support) <= 3
        assert len(resistance) <= 3

    def test_detect_returns_price_levels(self):
        """
        レベル検出 - PriceLevel返却

        条件: 検出実行
        期待: PriceLevel オブジェクトのリストを返す
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        support, resistance = self.detector.detect(df)

        # Assert
        for level in support:
            assert isinstance(level, PriceLevel)
            assert level.level_type == 'support'
            assert level.level > 0
            assert level.strength >= 0
            assert len(level.touch_points) >= self.detector.min_touches

        for level in resistance:
            assert isinstance(level, PriceLevel)
            assert level.level_type == 'resistance'

    def test_detect_sorted_by_strength(self):
        """
        レベル検出 - 強度ソート

        条件: 複数レベル検出
        期待: 強度の高い順にソートされている
        """
        # Arrange
        df = self.create_test_dataframe(n_points=200)

        # Act
        support, resistance = self.detector.detect(df)

        # Assert
        if len(support) > 1:
            for i in range(len(support) - 1):
                assert support[i].strength >= support[i+1].strength

        if len(resistance) > 1:
            for i in range(len(resistance) - 1):
                assert resistance[i].strength >= resistance[i+1].strength

    # ========================================
    # 【_find_local_extrema】4テスト
    # ========================================

    def test_find_local_extrema_max(self):
        """
        ローカル極値検出 - 最大値

        条件: method='max'
        期待: ローカル高値を検出
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        extrema = self.detector._find_local_extrema(df, 'high', 'max')

        # Assert
        assert len(extrema) > 0
        for ext in extrema:
            assert 'index' in ext
            assert 'price' in ext
            assert 'timestamp' in ext
            assert isinstance(ext['index'], int)
            assert ext['price'] > 0

    def test_find_local_extrema_min(self):
        """
        ローカル極値検出 - 最小値

        条件: method='min'
        期待: ローカル安値を検出
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        extrema = self.detector._find_local_extrema(df, 'low', 'min')

        # Assert
        assert len(extrema) > 0
        for ext in extrema:
            assert ext['price'] > 0

    def test_find_local_extrema_within_bounds(self):
        """
        ローカル極値検出 - インデックス範囲

        条件: 極値検出
        期待: half_window から len(df)-half_window の範囲内
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        half_window = self.detector.window // 2

        # Act
        extrema = self.detector._find_local_extrema(df, 'high', 'max')

        # Assert
        for ext in extrema:
            assert ext['index'] >= half_window
            assert ext['index'] < len(df) - half_window

    def test_find_local_extrema_price_matches_dataframe(self):
        """
        ローカル極値検出 - 価格一致

        条件: 極値検出
        期待: 価格が元データと一致
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        extrema = self.detector._find_local_extrema(df, 'high', 'max')

        # Assert
        for ext in extrema:
            assert ext['price'] == df['high'].iloc[ext['index']]

    # ========================================
    # 【_identify_levels】3テスト
    # ========================================

    def test_identify_levels_empty_extrema(self):
        """
        レベル特定 - 極値なし

        条件: 空の極値リスト
        期待: 空リストを返す
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)

        # Act
        levels = self.detector._identify_levels(df, [], 'support', 'low')

        # Assert
        assert levels == []

    def test_identify_levels_min_touches_filter(self):
        """
        レベル特定 - 最小タッチ回数フィルタ

        条件: min_touches 条件
        期待: min_touches 以上のタッチがあるレベルのみ
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        extrema = self.detector._find_local_extrema(df, 'low', 'min')

        # Act
        levels = self.detector._identify_levels(df, extrema, 'support', 'low')

        # Assert
        for level in levels:
            assert len(level.touch_points) >= self.detector.min_touches

    def test_identify_levels_properties(self):
        """
        レベル特定 - プロパティ確認

        条件: レベル特定実行
        期待: 正しいプロパティが設定される
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        extrema = self.detector._find_local_extrema(df, 'high', 'max')

        # Act
        levels = self.detector._identify_levels(df, extrema, 'resistance', 'high')

        # Assert
        for level in levels:
            assert level.level_type == 'resistance'
            assert 0 < level.strength <= 1  # 正規化された強度
            assert level.first_touch == df.index[level.touch_points[0]]
            assert level.last_touch == df.index[level.touch_points[-1]]

    # ========================================
    # 【_find_all_touches】2テスト
    # ========================================

    def test_find_all_touches_basic(self):
        """
        タッチポイント検出 - 基本

        条件: 指定レベル価格
        期待: タッチしたインデックスのリストを返す
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        level_price = df['close'].iloc[50]

        # Act
        touches = self.detector._find_all_touches(df, level_price, 'close')

        # Assert
        assert isinstance(touches, list)
        assert len(touches) > 0
        assert all(isinstance(idx, int) for idx in touches)

    def test_find_all_touches_threshold(self):
        """
        タッチポイント検出 - 閾値確認

        条件: price_threshold 範囲内
        期待: 範囲内の価格のみ検出
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        level_price = 105.0
        threshold = level_price * self.detector.price_threshold

        # Act
        touches = self.detector._find_all_touches(df, level_price, 'close')

        # Assert
        for idx in touches:
            price = df['close'].iloc[idx]
            assert abs(price - level_price) <= threshold

    # ========================================
    # 【get_nearest_levels】4テスト
    # ========================================

    def test_get_nearest_levels_structure(self):
        """
        最近接レベル取得 - 構造確認

        条件: 実行
        期待: 正しい辞書構造を返す
        """
        # Arrange
        df = self.create_test_dataframe(n_points=100)
        current_price = 105.0

        # Act
        result = self.detector.get_nearest_levels(df, current_price)

        # Assert
        assert 'nearest_support' in result
        assert 'nearest_resistance' in result
        assert 'all_support' in result
        assert 'all_resistance' in result
        assert isinstance(result['all_support'], list)
        assert isinstance(result['all_resistance'], list)

    def test_get_nearest_levels_support_below_price(self):
        """
        最近接レベル取得 - サポートは価格より下

        条件: current_price 指定
        期待: nearest_support は current_price より低い
        """
        # Arrange
        df = self.create_test_dataframe(n_points=200)
        current_price = 105.0

        # Act
        result = self.detector.get_nearest_levels(df, current_price)

        # Assert
        if result['nearest_support']:
            assert result['nearest_support']['level'] < current_price

    def test_get_nearest_levels_resistance_above_price(self):
        """
        最近接レベル取得 - レジスタンスは価格より上

        条件: current_price 指定
        期待: nearest_resistance は current_price より高い
        """
        # Arrange
        df = self.create_test_dataframe(n_points=200)
        current_price = 105.0

        # Act
        result = self.detector.get_nearest_levels(df, current_price)

        # Assert
        if result['nearest_resistance']:
            assert result['nearest_resistance']['level'] > current_price

    def test_get_nearest_levels_closest_to_current(self):
        """
        最近接レベル取得 - 最も近いレベル

        条件: 複数のサポート/レジスタンス存在
        期待: 現在価格に最も近いものが選ばれる
        """
        # Arrange
        df = self.create_test_dataframe(n_points=200)
        current_price = 105.0

        # Act
        result = self.detector.get_nearest_levels(df, current_price)

        # Assert
        # 全サポートの中で最も高いものが選ばれる（現在価格より下で最も近い）
        if result['nearest_support']:
            for support in result['all_support']:
                if support['level'] < current_price:
                    assert support['level'] <= result['nearest_support']['level']

        # 全レジスタンスの中で最も低いものが選ばれる（現在価格より上で最も近い）
        if result['nearest_resistance']:
            for resistance in result['all_resistance']:
                if resistance['level'] > current_price:
                    assert resistance['level'] >= result['nearest_resistance']['level']


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
