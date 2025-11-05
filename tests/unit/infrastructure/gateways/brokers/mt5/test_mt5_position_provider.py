# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_position_provider.py
"""
MT5 Position Provider 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_position_provider.py
設計: docs/testing/test_design.md (lines 367-425)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from src.infrastructure.gateways.brokers.mt5.mt5_position_provider import MT5PositionProvider


class TestMT5PositionProvider:
    """MT5PositionProvider のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モック接続
        self.mock_connection = Mock()
        self.mock_connection.ensure_connected.return_value = True

        # テスト用MT5ポジションデータ
        self.sample_mt5_position = type('MT5Position', (), {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 0,  # ORDER_TYPE_BUY
            'volume': 0.1,
            'price_open': 150.00,
            'price_current': 150.50,
            'sl': 149.00,
            'tp': 151.00,
            'profit': 5000.0,
            'swap': 100.0,
            'time': int(datetime(2025, 11, 1, 10, 0, 0).timestamp()),
            'magic': 12345,
            'comment': 'Test Position'
        })()

        # プロバイダーインスタンス
        self.provider = MT5PositionProvider(self.mock_connection)

    # ========================================
    # 【正常系】3テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_all_positions_success(self, mock_mt5):
        """
        全ポジション取得（正常系）

        条件: MT5接続成功、複数ポジション存在
        期待: Position情報リスト返却
        """
        # Arrange
        mock_mt5.positions_get.return_value = [self.sample_mt5_position]
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.001})()
        mock_mt5.ORDER_TYPE_BUY = 0

        # Act
        positions = self.provider.get_all_positions()

        # Assert
        assert len(positions) == 1
        assert positions[0]['ticket'] == 12345678
        assert positions[0]['symbol'] == 'USDJPY'
        assert positions[0]['type'] == 'BUY'
        assert positions[0]['volume'] == 0.1
        assert positions[0]['profit'] == 5000.0
        self.mock_connection.ensure_connected.assert_called_once()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_position_by_ticket_success(self, mock_mt5):
        """
        チケット番号指定でポジション取得（正常系）

        条件: 有効なチケット番号指定
        期待: 該当ポジション情報返却
        """
        # Arrange
        mock_mt5.positions_get.return_value = [self.sample_mt5_position]
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.001})()
        mock_mt5.ORDER_TYPE_BUY = 0

        # Act
        position = self.provider.get_position_by_ticket(12345678)

        # Assert
        assert position is not None
        assert position['ticket'] == 12345678
        assert position['symbol'] == 'USDJPY'
        mock_mt5.positions_get.assert_called_once_with(ticket=12345678)

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_full_success(self, mock_mt5, mock_container):
        """
        全決済（正常系）

        条件: 全決済（volume=None）
        期待: 決済成功、MT5で確認
        """
        # Arrange
        # Kill Switch Mock
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        # MT5 Mocks
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # ポジション情報取得のMock
        position_data = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'magic': 12345
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        # 決済価格のMock
        mock_symbol_info = type('SymbolInfo', (), {'bid': 150.50})()
        mock_mt5.symbol_info_tick.return_value = mock_symbol_info

        # 決済結果のMock
        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 87654321,
            'price': 150.50,
            'volume': 0.1,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        # Act
        success, error = self.provider.close_position(12345678)

        # Assert
        assert success is True
        assert error is None
        mock_mt5.order_send.assert_called_once()

    # ========================================
    # 【部分決済】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_partial_success(self, mock_mt5, mock_container):
        """
        部分決済（正常系）

        条件: 部分決済（volume指定）
        期待: 指定ロット分のみ決済
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        position_data = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'magic': 12345
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        mock_symbol_info = type('SymbolInfo', (), {'bid': 150.50})()
        mock_mt5.symbol_info_tick.return_value = mock_symbol_info

        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 87654321,
            'price': 150.50,
            'volume': 0.05,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        # Act
        success, error = self.provider.close_position(12345678, volume=0.05)

        # Assert
        assert success is True
        assert error is None
        # 部分決済の volume=0.05 が使用されたことを確認
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['volume'] == 0.05

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_volume_validation(self, mock_mt5, mock_container):
        """
        保有量超過のvolume指定

        条件: 保有量超過のvolume指定（実装では検証なし、MT5側でエラー）
        期待: MT5がエラーを返す想定（実装では通過するがMT5が拒否）

        Note: 現在の実装では事前検証がないため、MT5に送信されてエラーになる
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        position_data = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'magic': 12345
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        mock_symbol_info = type('SymbolInfo', (), {'bid': 150.50})()
        mock_mt5.symbol_info_tick.return_value = mock_symbol_info

        # MT5がエラーを返す
        mock_result = type('OrderResult', (), {
            'retcode': 10013,  # INVALID_VOLUME
            'comment': 'Invalid volume'
        })()
        mock_mt5.order_send.return_value = mock_result

        # Act
        success, error = self.provider.close_position(12345678, volume=1.0)  # 0.1保有で1.0決済

        # Assert
        assert success is False
        assert 'Invalid volume' in error or 'retcode=10013' in error

    # ========================================
    # 【Kill Switch連携】2テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    def test_close_position_kill_switch_active(self, mock_container):
        """
        Kill Switch有効時の決済ブロック

        条件: Kill Switch有効状態
        期待: 決済ブロック、エラーメッセージ返却
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = True
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        # Act
        success, error = self.provider.close_position(12345678)

        # Assert
        assert success is False
        assert 'Kill Switch is active' in error

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_positions_kill_switch_inactive(self, mock_mt5):
        """
        Kill Switch無効時の通常取得

        条件: Kill Switch無効状態
        期待: 通常通り取得可能

        Note: get_all_positionsはKill Switchをチェックしない（読み取り操作のため）
        """
        # Arrange
        mock_mt5.positions_get.return_value = [self.sample_mt5_position]
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.001})()
        mock_mt5.ORDER_TYPE_BUY = 0

        # Act
        positions = self.provider.get_all_positions()

        # Assert
        assert len(positions) == 1
        assert positions[0]['ticket'] == 12345678

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    @patch('src.infrastructure.di.container.container')
    def test_close_position_invalid_ticket(self, mock_container):
        """
        存在しないチケット番号での決済

        条件: 存在しないチケット番号
        期待: False返却、エラーメッセージ
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        # ポジションが見つからない
        self.provider.get_position_by_ticket = Mock(return_value=None)

        # Act
        success, error = self.provider.close_position(99999999)

        # Assert
        assert success is False
        assert 'not found' in error

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_mt5_connection_error(self, mock_mt5, mock_container):
        """
        MT5接続失敗時のエラーハンドリング

        条件: MT5接続失敗
        期待: 接続エラーハンドリング

        Note: Kill Switchチェックが先に実行されるため、
              Kill SwitchをOFFにしてから接続エラーをテスト
        """
        # Arrange
        # Kill SwitchをOFFに
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        # MT5接続失敗
        self.mock_connection.ensure_connected.return_value = False

        # Act
        success, error = self.provider.close_position(12345678)

        # Assert
        assert success is False
        assert 'connection not available' in error

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_calculate_total_pl_no_positions(self, mock_mt5):
        """
        ポジションゼロ時の損益計算

        条件: ポジションゼロ
        期待: 0.0返却
        """
        # Arrange
        mock_mt5.positions_get.return_value = []

        # Act
        total_pnl = self.provider.calculate_total_unrealized_pnl()

        # Assert
        assert total_pnl == 0.0

    # ========================================
    # 【追加カバレッジ改善】10テスト
    # ========================================

    def test_get_all_positions_connection_failure(self):
        """
        全ポジション取得 - MT5接続失敗

        条件: ensure_connected() = False
        期待: 空リスト返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = False

        # Act
        positions = self.provider.get_all_positions()

        # Assert
        assert positions == []

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_all_positions_exception_handling(self, mock_mt5):
        """
        全ポジション取得 - 例外ハンドリング

        条件: positions_get()で例外発生
        期待: 空リスト返却、エラーログ
        """
        # Arrange
        mock_mt5.positions_get.side_effect = Exception("MT5 internal error")

        # Act
        positions = self.provider.get_all_positions()

        # Assert
        assert positions == []

    def test_get_position_by_ticket_connection_failure(self):
        """
        チケット指定取得 - MT5接続失敗

        条件: ensure_connected() = False
        期待: None返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = False

        # Act
        position = self.provider.get_position_by_ticket(12345678)

        # Assert
        assert position is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_position_by_ticket_exception_handling(self, mock_mt5):
        """
        チケット指定取得 - 例外ハンドリング

        条件: positions_get()で例外発生
        期待: None返却、エラーログ
        """
        # Arrange
        mock_mt5.positions_get.side_effect = Exception("MT5 internal error")

        # Act
        position = self.provider.get_position_by_ticket(12345678)

        # Assert
        assert position is None

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_sell_success(self, mock_mt5, mock_container):
        """
        SELLポジション決済成功

        条件: SELLポジションを全決済（ASK価格使用）
        期待: 決済成功、BUY注文で決済
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # SELLポジション情報
        position_data = {
            'ticket': 88888888,
            'symbol': 'EURUSD',
            'type': 'SELL',
            'volume': 0.2,
            'magic': 99999
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        # ASK価格（SELL決済にはBUY注文が必要）
        mock_symbol_info = type('SymbolInfo', (), {'ask': 1.0850})()
        mock_mt5.symbol_info_tick.return_value = mock_symbol_info

        # 決済結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 77777777,
            'price': 1.0850,
            'volume': 0.2,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        # Act
        success, error = self.provider.close_position(88888888)

        # Assert
        assert success is True
        assert error is None

        # BUY注文で決済されたことを確認
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['type'] == 0  # ORDER_TYPE_BUY
        assert call_args['price'] == 1.0850

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_invalid_price(self, mock_mt5, mock_container):
        """
        ポジション決済 - 無効価格

        条件: symbol_info_tick()がNone or price=0
        期待: False返却、エラーメッセージ
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1

        position_data = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'magic': 12345
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        # symbol_info_tickがNoneを返す
        mock_mt5.symbol_info_tick.return_value = None

        # Act
        success, error = self.provider.close_position(12345678)

        # Assert
        assert success is False
        assert 'Invalid price' in error

    @patch('src.infrastructure.di.container.container')
    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_close_position_order_send_returns_none(self, mock_mt5, mock_container):
        """
        ポジション決済 - order_send()がNone返却

        条件: mt5.order_send()がNone返却
        期待: False返却、エラーメッセージ
        """
        # Arrange
        mock_kill_switch_repo = Mock()
        mock_kill_switch_repo.is_active.return_value = False
        mock_container.get_kill_switch_repository.return_value = mock_kill_switch_repo

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1

        position_data = {
            'ticket': 12345678,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'magic': 12345
        }
        self.provider.get_position_by_ticket = Mock(return_value=position_data)

        mock_symbol_info = type('SymbolInfo', (), {'bid': 150.50})()
        mock_mt5.symbol_info_tick.return_value = mock_symbol_info

        # order_send()がNoneを返す
        mock_mt5.order_send.return_value = None

        # Act
        success, error = self.provider.close_position(12345678)

        # Assert
        assert success is False
        assert 'returned None' in error

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_calculate_total_pl_with_positions(self, mock_mt5):
        """
        総含み損益計算 - ポジション有り

        条件: 複数ポジション存在
        期待: 合計損益返却
        """
        # Arrange
        position1 = type('MT5Position', (), {
            'ticket': 11111111,
            'symbol': 'USDJPY',
            'type': 0,  # BUY
            'volume': 0.1,
            'price_open': 150.00,
            'price_current': 150.50,
            'sl': 149.00,
            'tp': 151.00,
            'profit': 5000.0,
            'swap': 100.0,
            'time': int(datetime.now().timestamp()),
            'magic': 12345,
            'comment': 'Position 1'
        })()

        position2 = type('MT5Position', (), {
            'ticket': 22222222,
            'symbol': 'EURUSD',
            'type': 1,  # SELL
            'volume': 0.2,
            'price_open': 1.0900,
            'price_current': 1.0850,
            'sl': 1.0950,
            'tp': 1.0800,
            'profit': 10000.0,
            'swap': 50.0,
            'time': int(datetime.now().timestamp()),
            'magic': 12345,
            'comment': 'Position 2'
        })()

        mock_mt5.positions_get.return_value = [position1, position2]
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.001})()
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1

        # Act
        total_pnl = self.provider.calculate_total_unrealized_pnl()

        # Assert
        assert total_pnl == 15000.0  # 5000 + 10000

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_get_positions_by_symbol_success(self, mock_mt5):
        """
        シンボル指定取得 - 成功

        条件: 特定シンボルのポジション存在
        期待: 該当ポジションのみ返却
        """
        # Arrange
        position_usdjpy = type('MT5Position', (), {
            'ticket': 11111111,
            'symbol': 'USDJPY',
            'type': 0,
            'volume': 0.1,
            'price_open': 150.00,
            'price_current': 150.50,
            'sl': 149.00,
            'tp': 151.00,
            'profit': 5000.0,
            'swap': 100.0,
            'time': int(datetime.now().timestamp()),
            'magic': 12345,
            'comment': 'USDJPY Position'
        })()

        position_eurusd = type('MT5Position', (), {
            'ticket': 22222222,
            'symbol': 'EURUSD',
            'type': 1,
            'volume': 0.2,
            'price_open': 1.0900,
            'price_current': 1.0850,
            'sl': 1.0950,
            'tp': 1.0800,
            'profit': 10000.0,
            'swap': 50.0,
            'time': int(datetime.now().timestamp()),
            'magic': 12345,
            'comment': 'EURUSD Position'
        })()

        mock_mt5.positions_get.return_value = [position_usdjpy, position_eurusd]
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.001})()
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1

        # Act
        usdjpy_positions = self.provider.get_positions_by_symbol('USDJPY')

        # Assert
        assert len(usdjpy_positions) == 1
        assert usdjpy_positions[0]['symbol'] == 'USDJPY'
        assert usdjpy_positions[0]['ticket'] == 11111111

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_position_provider.mt5')
    def test_format_position_sell(self, mock_mt5):
        """
        _format_position() - SELLポジション

        条件: SELLポジション、pips計算
        期待: フォーマット済み情報、SELL pips計算
        """
        # Arrange
        sell_position = type('MT5Position', (), {
            'ticket': 99999999,
            'symbol': 'EURUSD',
            'type': 1,  # SELL (ORDER_TYPE_SELL)
            'volume': 0.3,
            'price_open': 1.0900,
            'price_current': 1.0850,
            'sl': 1.0950,
            'tp': 1.0800,
            'profit': 15000.0,
            'swap': 75.0,
            'time': int(datetime(2025, 11, 5, 15, 0, 0).timestamp()),
            'magic': 99999,
            'comment': 'SELL Position'
        })()

        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.symbol_info.return_value = type('SymbolInfo', (), {'point': 0.00001})()
        mock_mt5.positions_get.return_value = [sell_position]

        # Act
        positions = self.provider.get_all_positions()

        # Assert
        assert len(positions) == 1
        formatted = positions[0]
        assert formatted['type'] == 'SELL'
        assert formatted['ticket'] == 99999999
        # SELL pips計算: (1.0900 - 1.0850) / (0.00001 * 10) = 50 pips
        assert formatted['profit_pips'] == pytest.approx(50.0)
