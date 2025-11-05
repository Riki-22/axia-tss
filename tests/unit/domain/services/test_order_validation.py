# tests/unit/domain/services/test_order_validation.py
"""
Order Validation Service 単体テスト

対象: src/domain/services/order_validation.py
"""

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

from src.domain.services.order_validation import OrderValidationService


class TestOrderValidationService:
    """OrderValidationService のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.service = OrderValidationService()

    # ========================================
    # 【正常系】3テスト
    # ========================================

    def test_check_tp_sl_both_none(self):
        """
        TP/SL両方None（TP/SLなし注文）

        条件: tp_price=None, sl_price=None
        期待: True返却、TP/SL=Decimal('0.0')
        """
        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='BUY',
            reference_price=150.00,
            tp_price=None,
            sl_price=None,
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is True
        assert tp == Decimal('0.0')
        assert sl == Decimal('0.0')

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_buy_order_valid(self, mock_mt5):
        """
        BUY注文のTP/SL正常ケース

        条件: BUY注文、TP > ref > SL、最小ストップレベル満たす
        期待: True返却
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,  # 10 points
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='BUY',
            reference_price=150.000,  # 基準価格
            tp_price=150.100,  # TP: +100 points (10 points以上)
            sl_price=149.900,  # SL: -100 points (10 points以上)
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is True
        assert tp == Decimal('150.100')
        assert sl == Decimal('149.900')

        mock_mt5.symbol_info.assert_called_once_with('USDJPY')

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_sell_order_valid(self, mock_mt5):
        """
        SELL注文のTP/SL正常ケース

        条件: SELL注文、SL > ref > TP、最小ストップレベル満たす
        期待: True返却
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='SELL',
            reference_price=150.000,
            tp_price=149.900,  # TP: -100 points (SELL なので下)
            sl_price=150.100,  # SL: +100 points (SELL なので上)
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is True
        assert tp == Decimal('149.900')
        assert sl == Decimal('150.100')

    # ========================================
    # 【エラーケース】5テスト
    # ========================================

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_buy_invalid_sl_above_ref(self, mock_mt5):
        """
        BUY注文のSL不正（基準価格以上）

        条件: BUY注文、SL >= reference_price
        期待: False返却、エラーログ
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='BUY',
            reference_price=150.000,
            tp_price=150.100,
            sl_price=150.100,  # SL が reference_price 以上（不正）
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is False

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_buy_sl_too_close(self, mock_mt5):
        """
        BUY注文のSL不正（最小ストップレベル未満）

        条件: BUY注文、SL距離が最小ストップレベル未満
        期待: False返却、エラーログ
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 100,  # 100 points必要
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='BUY',
            reference_price=150.000,
            tp_price=150.200,
            sl_price=149.960,  # SL距離: 40 points (100 points未満なので不正)
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is False

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_buy_invalid_tp_below_ref(self, mock_mt5):
        """
        BUY注文のTP不正（基準価格以下）

        条件: BUY注文、TP <= reference_price
        期待: False返却、エラーログ
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='BUY',
            reference_price=150.000,
            tp_price=149.900,  # TP が reference_price 以下（不正）
            sl_price=149.800,
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is False

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_sell_invalid_sl_below_ref(self, mock_mt5):
        """
        SELL注文のSL不正（基準価格以下）

        条件: SELL注文、SL <= reference_price
        期待: False返却、エラーログ
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='SELL',
            reference_price=150.000,
            tp_price=149.900,
            sl_price=149.900,  # SL が reference_price 以下（不正）
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is False

    @patch('src.domain.services.order_validation.mt5')
    def test_check_tp_sl_unsupported_action(self, mock_mt5):
        """
        未対応のorder_action

        条件: order_action='INVALID'
        期待: False返却、エラーログ
        """
        # Arrange
        mock_symbol_info = type('SymbolInfo', (), {
            'point': 0.001,
            'trade_stops_level': 10,
            'digits': 3
        })()
        mock_mt5.symbol_info.return_value = mock_symbol_info

        # Act
        is_valid, tp, sl = self.service.check_tp_sl_validity(
            order_action_str='INVALID',  # 未対応のaction
            reference_price=150.000,
            tp_price=150.100,
            sl_price=149.900,
            symbol='USDJPY'
        )

        # Assert
        assert is_valid is False
