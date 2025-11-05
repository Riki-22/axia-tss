# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_account_provider.py
"""
MT5 Account Provider 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import pytz

from src.infrastructure.gateways.brokers.mt5.mt5_account_provider import MT5AccountProvider


class TestMT5AccountProvider:
    """MT5AccountProvider のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モック接続
        self.mock_connection = Mock()
        self.mock_connection.ensure_connected.return_value = True

        # プロバイダーインスタンス
        self.provider = MT5AccountProvider(self.mock_connection)

    # ========================================
    # 【正常系】5テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_account_info_success(self, mock_mt5):
        """
        口座情報取得成功

        条件: MT5接続成功、口座情報取得成功
        期待: 口座情報辞書返却、証拠金率計算
        """
        # Arrange
        mock_account = type('Account', (), {
            'balance': 1000000.0,
            'equity': 1050000.0,
            'margin': 100000.0,
            'margin_free': 950000.0,
            'profit': 50000.0,
            'currency': 'JPY',
            'leverage': 25
        })()
        mock_mt5.account_info.return_value = mock_account

        # Act
        result = self.provider.get_account_info()

        # Assert
        assert result is not None
        assert result['balance'] == 1000000.0
        assert result['equity'] == 1050000.0
        assert result['margin'] == 100000.0
        assert result['free_margin'] == 950000.0
        assert result['margin_level'] == pytest.approx(1050.0)  # (1050000 / 100000) * 100
        assert result['profit'] == 50000.0
        assert result['currency'] == 'JPY'
        assert result['leverage'] == 25

        mock_mt5.account_info.assert_called_once()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_account_info_margin_zero_with_equity(self, mock_mt5):
        """
        証拠金率計算（margin=0, equity>0）

        条件: margin=0, equity>0
        期待: margin_level=inf（無限大）
        """
        # Arrange
        mock_account = type('Account', (), {
            'balance': 1000000.0,
            'equity': 1000000.0,
            'margin': 0.0,  # ポジションなし
            'margin_free': 1000000.0,
            'profit': 0.0,
            'currency': 'JPY',
            'leverage': 25
        })()
        mock_mt5.account_info.return_value = mock_account

        # Act
        result = self.provider.get_account_info()

        # Assert
        assert result is not None
        assert result['margin_level'] == float('inf')

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_balance_success(self, mock_mt5):
        """
        残高取得成功

        条件: get_account_info成功
        期待: 残高のみ返却
        """
        # Arrange
        mock_account = type('Account', (), {
            'balance': 1000000.0,
            'equity': 1050000.0,
            'margin': 100000.0,
            'margin_free': 950000.0,
            'profit': 50000.0,
            'currency': 'JPY',
            'leverage': 25
        })()
        mock_mt5.account_info.return_value = mock_account

        # Act
        result = self.provider.get_balance()

        # Assert
        assert result == 1000000.0

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_margin_info_success(self, mock_mt5):
        """
        証拠金情報取得成功

        条件: get_account_info成功
        期待: 証拠金情報のみ返却
        """
        # Arrange
        mock_account = type('Account', (), {
            'balance': 1000000.0,
            'equity': 1050000.0,
            'margin': 100000.0,
            'margin_free': 950000.0,
            'profit': 50000.0,
            'currency': 'JPY',
            'leverage': 25
        })()
        mock_mt5.account_info.return_value = mock_account

        # Act
        result = self.provider.get_margin_info()

        # Assert
        assert result is not None
        assert result['margin'] == 100000.0
        assert result['free_margin'] == 950000.0
        assert result['margin_level'] == pytest.approx(1050.0)

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_calculate_today_pl_success(self, mock_mt5):
        """
        本日損益計算成功

        条件: 取引履歴あり、含み損益あり
        期待: 実現損益+含み損益返却
        """
        # Arrange
        # 口座情報Mock
        mock_account = type('Account', (), {
            'balance': 1000000.0,
            'equity': 1050000.0,
            'margin': 100000.0,
            'margin_free': 950000.0,
            'profit': 30000.0,  # 含み損益
            'currency': 'JPY',
            'leverage': 25
        })()
        mock_mt5.account_info.return_value = mock_account

        # 取引履歴Mock（2件の決済）
        mock_deal1 = type('Deal', (), {
            'entry': 1,  # 決済
            'profit': 10000.0
        })()
        mock_deal2 = type('Deal', (), {
            'entry': 1,  # 決済
            'profit': 5000.0
        })()
        mock_mt5.history_deals_get.return_value = [mock_deal1, mock_deal2]

        # Act
        result = self.provider.calculate_today_pl()

        # Assert
        assert result is not None
        # 実現損益: 10000 + 5000 = 15000
        # 含み損益: 30000
        # 合計: 45000
        assert result['amount'] == 45000.0
        # %計算: (45000 / 1000000) * 100 = 4.5%
        assert result['percentage'] == pytest.approx(4.5)

        mock_mt5.history_deals_get.assert_called_once()

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_account_info_connection_failure(self, mock_mt5):
        """
        MT5未接続

        条件: ensure_connected()=False
        期待: None返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = False

        # Act
        result = self.provider.get_account_info()

        # Assert
        assert result is None
        mock_mt5.account_info.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_get_account_info_not_found(self, mock_mt5):
        """
        口座情報取得失敗

        条件: account_info()がNone返却
        期待: None返却
        """
        # Arrange
        mock_mt5.account_info.return_value = None

        # Act
        result = self.provider.get_account_info()

        # Assert
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_account_provider.mt5')
    def test_calculate_today_pl_no_history(self, mock_mt5):
        """
        本日損益計算（取引履歴なし）

        条件: history_deals_get()がNone返却
        期待: amount=0.0, percentage=0.0
        """
        # Arrange
        mock_mt5.history_deals_get.return_value = None

        # Act
        result = self.provider.calculate_today_pl()

        # Assert
        assert result is not None
        assert result['amount'] == 0.0
        assert result['percentage'] == 0.0
