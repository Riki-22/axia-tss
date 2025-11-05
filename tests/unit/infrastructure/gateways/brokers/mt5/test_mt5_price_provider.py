# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_price_provider.py
"""
MT5 Price Provider 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.infrastructure.gateways.brokers.mt5.mt5_price_provider import MT5PriceProvider


class TestMT5PriceProvider:
    """MT5PriceProvider のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モック接続
        self.mock_connection = Mock()
        self.mock_connection.ensure_connected.return_value = True

        # プロバイダーインスタンス
        self.provider = MT5PriceProvider(self.mock_connection)

    # ========================================
    # 【正常系】4テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_current_price_success(self, mock_mt5):
        """
        現在価格取得成功

        条件: MT5接続成功、Tick情報取得成功
        期待: Bid/Ask/Spread返却
        """
        # Arrange
        mock_tick = type('Tick', (), {
            'bid': 150.000,
            'ask': 150.030,
            'time': 1699000000
        })()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        result = self.provider.get_current_price('USDJPY')

        # Assert
        assert result is not None
        assert result['symbol'] == 'USDJPY'
        assert result['bid'] == 150.000
        assert result['ask'] == 150.030
        assert result['spread'] == pytest.approx(30.0)  # (150.030 - 150.000) / 0.001 = 30 pips
        assert 'time' in result

        mock_mt5.symbol_info_tick.assert_called_once_with('USDJPY')
        mock_mt5.symbol_info.assert_called_once_with('USDJPY')

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_current_price_without_symbol_info(self, mock_mt5):
        """
        現在価格取得成功（シンボル情報なし）

        条件: Tick情報成功、シンボル情報失敗
        期待: spread=0.0で返却
        """
        # Arrange
        mock_tick = type('Tick', (), {
            'bid': 150.000,
            'ask': 150.030,
            'time': 1699000000
        })()
        mock_mt5.symbol_info_tick.return_value = mock_tick
        mock_mt5.symbol_info.return_value = None  # シンボル情報取得失敗

        # Act
        result = self.provider.get_current_price('USDJPY')

        # Assert
        assert result is not None
        assert result['spread'] == 0.0  # シンボル情報なしの場合

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_bid_ask_success(self, mock_mt5):
        """
        Bid/Ask価格取得成功

        条件: get_current_price成功
        期待: (bid, ask)タプル返却
        """
        # Arrange
        mock_tick = type('Tick', (), {
            'bid': 150.000,
            'ask': 150.030,
            'time': 1699000000
        })()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        result = self.provider.get_bid_ask('USDJPY')

        # Assert
        assert result is not None
        assert result == (150.000, 150.030)

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_symbol_info_success(self, mock_mt5):
        """
        シンボル情報取得成功

        条件: MT5接続成功、シンボル情報取得成功
        期待: シンボル詳細情報返却
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'digits': 3,
            'point': 0.001,
            'trade_contract_size': 100000.0,
            'volume_min': 0.01,
            'volume_max': 100.0,
            'volume_step': 0.01
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        result = self.provider.get_symbol_info('USDJPY')

        # Assert
        assert result is not None
        assert result['symbol'] == 'USDJPY'
        assert result['digits'] == 3
        assert result['point'] == 0.001
        assert result['trade_contract_size'] == 100000.0
        assert result['volume_min'] == 0.01
        assert result['volume_max'] == 100.0
        assert result['volume_step'] == 0.01

        mock_mt5.symbol_info.assert_called_once_with('USDJPY')

    # ========================================
    # 【エラーハンドリング】4テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_current_price_connection_failure(self, mock_mt5):
        """
        MT5未接続

        条件: ensure_connected()=False
        期待: None返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = False

        # Act
        result = self.provider.get_current_price('USDJPY')

        # Assert
        assert result is None
        mock_mt5.symbol_info_tick.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_current_price_tick_not_found(self, mock_mt5):
        """
        Tick情報取得失敗

        条件: symbol_info_tick()がNone返却
        期待: None返却
        """
        # Arrange
        mock_mt5.symbol_info_tick.return_value = None

        # Act
        result = self.provider.get_current_price('INVALID_SYMBOL')

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_bid_ask_failure(self, mock_mt5):
        """
        Bid/Ask取得失敗

        条件: get_current_price失敗
        期待: None返却
        """
        # Arrange
        mock_mt5.symbol_info_tick.return_value = None

        # Act
        result = self.provider.get_bid_ask('INVALID_SYMBOL')

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_price_provider.mt5')
    def test_get_symbol_info_not_found(self, mock_mt5):
        """
        シンボル情報取得失敗

        条件: symbol_info()がNone返却
        期待: None返却
        """
        # Arrange
        mock_mt5.symbol_info.return_value = None

        # Act
        result = self.provider.get_symbol_info('INVALID_SYMBOL')

        # Assert
        assert result is None
