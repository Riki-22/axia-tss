# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_data_collector.py
"""
MT5 Data Collector 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_data_collector.py
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector


class TestMT5DataCollector:
    """MT5DataCollector のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.mock_connection = Mock()
        self.timeframe_map = {
            'M1': 1,
            'M5': 5,
            'M15': 15,
            'M30': 30,
            'H1': 16385,
            'H4': 16388,
            'D1': 16408
        }

    # ========================================
    # 【初期化】3テスト
    # ========================================

    def test_init_basic(self):
        """
        初期化 - 基本

        条件: connection と timeframe_map を渡す
        期待: 正しく初期化される
        """
        # Act
        collector = MT5DataCollector(
            connection=self.mock_connection,
            timeframe_map=self.timeframe_map
        )

        # Assert
        assert collector.connection == self.mock_connection
        assert collector.timeframe_map == self.timeframe_map
        assert len(collector.timeframe_reverse_map) == 7

    def test_init_reverse_map(self):
        """
        初期化 - 逆マッピング

        条件: timeframe_map 指定
        期待: timeframe_reverse_map が正しく作成される
        """
        # Act
        collector = MT5DataCollector(
            connection=self.mock_connection,
            timeframe_map=self.timeframe_map
        )

        # Assert
        assert collector.timeframe_reverse_map[1] == 'M1'
        assert collector.timeframe_reverse_map[16385] == 'H1'
        assert collector.timeframe_reverse_map[16408] == 'D1'

    def test_init_empty_timeframe_map(self):
        """
        初期化 - 空のtimeframe_map

        条件: 空の timeframe_map
        期待: ValueError を発生
        """
        # Act & Assert
        with pytest.raises(ValueError, match="timeframe_map must not be empty"):
            MT5DataCollector(
                connection=self.mock_connection,
                timeframe_map={}
            )

    # ========================================
    # 【fetch_ohlcv_data】12テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_success(self, mock_mt5):
        """
        データ取得 - 成功

        条件: 正常なデータ取得
        期待: 標準OHLCV形式のDataFrameを返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        # Mock symbol_info
        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Mock rates data
        mock_rates = np.array([
            (1640000000, 110.0, 110.5, 109.5, 110.2, 1000, 0, 0),
            (1640003600, 110.2, 110.7, 110.0, 110.5, 1200, 0, 0),
            (1640007200, 110.5, 111.0, 110.3, 110.8, 1100, 0, 0)
        ], dtype=[
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ])
        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 3)

        # Assert
        assert result is not None
        assert len(result) == 3
        assert list(result.columns) == ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
        assert result['open'].dtype == 'float64'
        assert result['volume'].dtype == 'int64'
        mock_mt5.copy_rates_from_pos.assert_called_once_with('USDJPY', 16385, 0, 3)

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_unknown_timeframe(self, mock_mt5):
        """
        データ取得 - 未知のタイムフレーム

        条件: timeframe_map にない timeframe
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'UNKNOWN', 24)

        # Assert
        assert result is None
        # ensure_connected は呼ばれない（タイムフレームチェックで早期リターン）
        self.mock_connection.ensure_connected.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_connection_failed(self, mock_mt5):
        """
        データ取得 - 接続失敗

        条件: ensure_connected が False
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = False

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)

        # Assert
        assert result is None
        self.mock_connection.ensure_connected.assert_called_once()
        mock_mt5.symbol_info.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_symbol_not_found(self, mock_mt5):
        """
        データ取得 - シンボルが見つからない

        条件: symbol_info が None
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True
        mock_mt5.symbol_info.return_value = None

        # Act
        result = collector.fetch_ohlcv_data('INVALID', 'H1', 24)

        # Assert
        assert result is None
        mock_mt5.symbol_info.assert_called_once_with('INVALID')

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.time.sleep')
    def test_fetch_ohlcv_data_symbol_not_visible(self, mock_sleep, mock_mt5):
        """
        データ取得 - シンボルが非表示

        条件: symbol_info.visible が False
        期待: symbol_select を呼んで選択を試みる
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = False
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_select.return_value = True

        # Mock rates
        mock_rates = np.array([
            (1640000000, 110.0, 110.5, 109.5, 110.2, 1000, 0, 0)
        ], dtype=[
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ])
        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 1)

        # Assert
        assert result is not None
        mock_mt5.symbol_select.assert_called_once_with('USDJPY', True)
        mock_sleep.assert_called_once_with(1)

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_symbol_select_failed(self, mock_mt5):
        """
        データ取得 - シンボル選択失敗

        条件: symbol_select が False
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = False
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_select.return_value = False

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)

        # Assert
        assert result is None
        mock_mt5.copy_rates_from_pos.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_no_rates(self, mock_mt5):
        """
        データ取得 - データなし

        条件: copy_rates_from_pos が None
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.copy_rates_from_pos.return_value = None

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_empty_rates(self, mock_mt5):
        """
        データ取得 - 空のデータ

        条件: copy_rates_from_pos が空配列
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.copy_rates_from_pos.return_value = np.array([])

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_exception(self, mock_mt5):
        """
        データ取得 - 例外発生

        条件: copy_rates_from_pos が例外を発生
        期待: None を返す
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.copy_rates_from_pos.side_effect = Exception("MT5 error")

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 24)

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_data_types(self, mock_mt5):
        """
        データ取得 - データ型確認

        条件: 正常なデータ取得
        期待: 正しいデータ型に変換される
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info

        mock_rates = np.array([
            (1640000000, 110.0, 110.5, 109.5, 110.2, 1000, 0, 0)
        ], dtype=[
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ])
        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        # Act
        result = collector.fetch_ohlcv_data('USDJPY', 'H1', 1)

        # Assert
        assert result['open'].dtype == 'float64'
        assert result['high'].dtype == 'float64'
        assert result['low'].dtype == 'float64'
        assert result['close'].dtype == 'float64'
        assert result['volume'].dtype == 'int64'
        # timestamp_utc should be datetime with UTC timezone
        assert pd.api.types.is_datetime64_any_dtype(result['timestamp_utc'])

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_data_collector.mt5')
    def test_fetch_ohlcv_data_different_timeframes(self, mock_mt5):
        """
        データ取得 - 異なるタイムフレーム

        条件: 複数のタイムフレームでデータ取得
        期待: 正しいタイムフレームintが渡される
        """
        # Arrange
        collector = MT5DataCollector(self.mock_connection, self.timeframe_map)
        self.mock_connection.ensure_connected.return_value = True

        mock_symbol_info = Mock()
        mock_symbol_info.visible = True
        mock_mt5.symbol_info.return_value = mock_symbol_info

        mock_rates = np.array([
            (1640000000, 110.0, 110.5, 109.5, 110.2, 1000, 0, 0)
        ], dtype=[
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ])
        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        # Act & Assert
        # M1
        collector.fetch_ohlcv_data('USDJPY', 'M1', 1)
        mock_mt5.copy_rates_from_pos.assert_called_with('USDJPY', 1, 0, 1)

        # H1
        collector.fetch_ohlcv_data('USDJPY', 'H1', 1)
        mock_mt5.copy_rates_from_pos.assert_called_with('USDJPY', 16385, 0, 1)

        # D1
        collector.fetch_ohlcv_data('USDJPY', 'D1', 1)
        mock_mt5.copy_rates_from_pos.assert_called_with('USDJPY', 16408, 0, 1)


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
