# tests/unit/infrastructure/gateways/brokers/mt5/test_mt5_order_executor.py
"""
MT5 Order Executor 単体テスト

対象: src/infrastructure/gateways/brokers/mt5/mt5_order_executor.py
設計: docs/testing/test_design.md (lines 640-681)
"""

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

from src.infrastructure.gateways.brokers.mt5.mt5_order_executor import MT5OrderExecutor


class TestMT5OrderExecutor:
    """MT5OrderExecutor のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モック依存関係
        self.mock_connection = Mock()
        self.mock_validation_service = Mock()
        self.mock_order_repository = Mock()

        # Executorインスタンス
        self.executor = MT5OrderExecutor(
            connection=self.mock_connection,
            validation_service=self.mock_validation_service,
            order_repository=self.mock_order_repository,
            magic_number=12345
        )

        # MT5認証情報
        self.credentials = {
            'mt5_login': 123456,
            'mt5_password': 'test_pass',
            'mt5_server': 'TestServer'
        }

        # 標準MARKET注文ペイロード
        self.market_order = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'tp_price': 151.0,
            'sl_price': 149.0,
            'comment': 'Test Order'
        }

    # ========================================
    # 【正常系】2テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_market_order_success(self, mock_mt5):
        """
        MARKET注文実行成功

        条件: MARKET注文（order_type='MARKET', BUY）
        期待: order_send()成功、DynamoDB保存、result返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,  # is_valid
            Decimal('151.0'),  # checked_tp
            Decimal('149.0')   # checked_sl
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 87654321,
            'price': 150.00,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        # DynamoDB保存成功
        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is True
        assert result is not None
        assert result.order == 87654321

        # MT5関数が呼ばれたことを確認
        mock_mt5.symbol_info_tick.assert_called_once_with('USDJPY')
        mock_mt5.order_send.assert_called_once()

        # DynamoDB保存が呼ばれたことを確認
        self.mock_order_repository.save_mt5_result.assert_called_once()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_ifoco_order_success(self, mock_mt5):
        """
        IFOCO注文実行成功

        条件: IFOCO注文（order_type='IFOCO', entry_price指定）
        期待: LIMIT/STOP判定、order_send()成功、DynamoDB保存
        """
        # Arrange
        ifoco_order = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'IFOCO',
            'lot_size': 0.1,
            'entry_price': 149.50,  # 現在価格より低い → BUY LIMIT
            'tp_price': 151.0,
            'sl_price': 149.0,
            'comment': 'IFOCO Order'
        }

        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_PENDING = 5
        mock_mt5.ORDER_TYPE_BUY_LIMIT = 2
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_PLACED = 10008

        # Tick情報Mock（現在Ask=150.00）
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10008,
            'order': 99999999,
            'price': 149.50,
            'comment': 'Placed'
        })()
        mock_mt5.order_send.return_value = mock_result

        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(ifoco_order, self.credentials)

        # Assert
        assert success is True
        assert result.order == 99999999

        # order_sendの引数を確認
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['action'] == 5  # TRADE_ACTION_PENDING
        assert call_args['type'] == 2  # ORDER_TYPE_BUY_LIMIT（entry_price < current_ask）
        assert call_args['price'] == 149.50

    # ========================================
    # 【バリデーション】2テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_invalid_order_type(self, mock_mt5):
        """
        無効なorder_type

        条件: order_type='INVALID'（MARKET/IFOCO以外）
        期待: execute_order()=False、エラーログ
        """
        # Arrange
        invalid_order = self.market_order.copy()
        invalid_order['order_type'] = 'INVALID'

        self.mock_connection.ensure_connected.return_value = True

        # Act
        success, result = self.executor.execute_order(invalid_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_missing_parameters(self, mock_mt5):
        """
        必須パラメータ欠落

        条件: 必須パラメータ欠落（symbolなど）
        期待: execute_order()=False、エラーログ
        """
        # Arrange
        incomplete_order = {
            # 'symbol': 'USDJPY',  # 欠落
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1
        }

        self.mock_connection.ensure_connected.return_value = True

        # Act
        success, result = self.executor.execute_order(incomplete_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

        # order_sendは呼ばれないことを確認
        mock_mt5.order_send.assert_not_called()

    # ========================================
    # 【エラーハンドリング】2テスト
    # ========================================

    def test_mt5_connection_failure(self):
        """
        MT5未接続

        条件: ensure_connected()=False（MT5未接続）
        期待: execute_order()=False、エラーログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = False

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_order_send_returns_none(self, mock_mt5):
        """
        order_send()がNone返却

        条件: mt5.order_send()がNone返却
        期待: execute_order()=False、エラーログ、last_error()確認
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # order_sendがNoneを返す
        mock_mt5.order_send.return_value = None
        mock_mt5.last_error.return_value = (10006, 'Request rejected')

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None
        mock_mt5.last_error.assert_called_once()

    # ========================================
    # 【追加カバレッジ改善】9テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_market_sell_order_success(self, mock_mt5):
        """
        MARKET SELL注文実行成功

        条件: MARKET注文（order_action='SELL', BID価格使用）
        期待: BID価格で注文実行、DynamoDB保存
        """
        # Arrange
        sell_order = self.market_order.copy()
        sell_order['order_action'] = 'SELL'

        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # Tick情報Mock（BID価格使用）
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('149.0'),  # TP（SELL時は価格下）
            Decimal('151.0')   # SL（SELL時は価格上）
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 11111111,
            'price': 149.99,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(sell_order, self.credentials)

        # Assert
        assert success is True
        assert result.order == 11111111
        assert result.price == 149.99

        # order_sendの引数確認（SELL、BID価格）
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['type'] == 1  # ORDER_TYPE_SELL
        assert call_args['price'] == 149.99

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_ifoco_buy_stop_success(self, mock_mt5):
        """
        IFOCO BUY STOP注文実行成功

        条件: entry_price > current_ask → BUY STOP
        期待: BUY STOP注文発注、DynamoDB保存
        """
        # Arrange
        ifoco_order = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'IFOCO',
            'lot_size': 0.1,
            'entry_price': 150.50,  # 現在Ask(150.00)より高い → BUY STOP
            'tp_price': 151.0,
            'sl_price': 149.0,
            'comment': 'BUY STOP Order'
        }

        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_PENDING = 5
        mock_mt5.ORDER_TYPE_BUY_STOP = 4
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_PLACED = 10008

        # Tick情報Mock（Ask=150.00）
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10008,
            'order': 22222222,
            'price': 150.50,
            'comment': 'Placed'
        })()
        mock_mt5.order_send.return_value = mock_result

        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(ifoco_order, self.credentials)

        # Assert
        assert success is True
        assert result.order == 22222222

        # order_sendの引数確認（BUY STOP）
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['action'] == 5  # TRADE_ACTION_PENDING
        assert call_args['type'] == 4  # ORDER_TYPE_BUY_STOP
        assert call_args['price'] == 150.50

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_ifoco_sell_limit_success(self, mock_mt5):
        """
        IFOCO SELL LIMIT注文実行成功

        条件: SELL、entry_price > current_bid → SELL LIMIT
        期待: SELL LIMIT注文発注
        """
        # Arrange
        ifoco_order = {
            'symbol': 'USDJPY',
            'order_action': 'SELL',
            'order_type': 'IFOCO',
            'lot_size': 0.1,
            'entry_price': 150.50,  # 現在Bid(149.99)より高い → SELL LIMIT
            'tp_price': 149.0,
            'sl_price': 151.0,
            'comment': 'SELL LIMIT Order'
        }

        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_PENDING = 5
        mock_mt5.ORDER_TYPE_SELL_LIMIT = 3
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_PLACED = 10008

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('149.0'),
            Decimal('151.0')
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10008,
            'order': 33333333,
            'price': 150.50,
            'comment': 'Placed'
        })()
        mock_mt5.order_send.return_value = mock_result

        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(ifoco_order, self.credentials)

        # Assert
        assert success is True
        assert result.order == 33333333

        # order_sendの引数確認（SELL LIMIT）
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['type'] == 3  # ORDER_TYPE_SELL_LIMIT
        assert call_args['price'] == 150.50

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_execute_ifoco_sell_stop_success(self, mock_mt5):
        """
        IFOCO SELL STOP注文実行成功

        条件: SELL、entry_price < current_bid → SELL STOP
        期待: SELL STOP注文発注
        """
        # Arrange
        ifoco_order = {
            'symbol': 'USDJPY',
            'order_action': 'SELL',
            'order_type': 'IFOCO',
            'lot_size': 0.1,
            'entry_price': 149.50,  # 現在Bid(149.99)より低い → SELL STOP
            'tp_price': 148.0,
            'sl_price': 151.0,
            'comment': 'SELL STOP Order'
        }

        self.mock_connection.ensure_connected.return_value = True

        # MT5定数Mock
        mock_mt5.TRADE_ACTION_PENDING = 5
        mock_mt5.ORDER_TYPE_SELL_STOP = 5
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_PLACED = 10008

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('148.0'),
            Decimal('151.0')
        )

        # 注文結果Mock
        mock_result = type('OrderResult', (), {
            'retcode': 10008,
            'order': 44444444,
            'price': 149.50,
            'comment': 'Placed'
        })()
        mock_mt5.order_send.return_value = mock_result

        self.mock_order_repository.save_mt5_result.return_value = True

        # Act
        success, result = self.executor.execute_order(ifoco_order, self.credentials)

        # Assert
        assert success is True
        assert result.order == 44444444

        # order_sendの引数確認（SELL STOP）
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['type'] == 5  # ORDER_TYPE_SELL_STOP
        assert call_args['price'] == 149.50

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_tp_sl_validation_failure(self, mock_mt5):
        """
        TP/SL検証失敗

        条件: TP/SL検証がFalse返却
        期待: execute_order()=False
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SL検証失敗
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            False,  # 検証失敗
            None,
            None
        )

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

        # order_sendは呼ばれない
        mock_mt5.order_send.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_tick_info_returns_none(self, mock_mt5):
        """
        tick_info取得失敗

        条件: symbol_info_tick()がNone返却
        期待: execute_order()=False、エラーログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0

        # tick_info取得失敗
        mock_mt5.symbol_info_tick.return_value = None

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

        # order_sendは呼ばれない
        mock_mt5.order_send.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_ask_price_is_zero(self, mock_mt5):
        """
        Ask価格が0

        条件: tick_info.ask == 0（取得失敗）
        期待: execute_order()=False、エラーログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0

        # Ask価格が0
        mock_tick = type('TickInfo', (), {'ask': 0, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

        mock_mt5.order_send.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_order_send_returns_error_retcode(self, mock_mt5):
        """
        order_send()がエラーretcode返却

        条件: result.retcode != DONE/PLACED（拒否）
        期待: execute_order()=False、エラーログ、resultは返却
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.TRADE_RETCODE_PLACED = 10008

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # order_sendがエラーretcode返却
        mock_result = type('OrderResult', (), {
            'retcode': 10013,  # TRADE_RETCODE_INVALID（無効な注文）
            'order': 0,
            'price': 0.0,
            'comment': 'Invalid order'
        })()
        mock_mt5.order_send.return_value = mock_result

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is not None  # resultは返却される
        assert result.retcode == 10013

        # DynamoDB保存は呼ばれない（失敗時）
        self.mock_order_repository.save_mt5_result.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_exception_during_execution(self, mock_mt5):
        """
        注文実行中に例外発生

        条件: order_send()で例外発生
        期待: execute_order()=False、例外ログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # order_sendで例外発生
        mock_mt5.order_send.side_effect = Exception("MT5 internal error")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

    # ========================================
    # 【例外ハンドリング強化】6テスト
    # ========================================

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_dynamodb_save_exception(self, mock_mt5):
        """
        DynamoDB保存時に例外発生

        条件: save_mt5_result()で例外発生
        期待: execute_order()=True（注文は成功）、DynamoDBエラーログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.TRADE_RETCODE_DONE = 10009

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # 注文成功
        mock_result = type('OrderResult', (), {
            'retcode': 10009,
            'order': 99999999,
            'price': 150.00,
            'comment': 'Done'
        })()
        mock_mt5.order_send.return_value = mock_result

        # DynamoDB保存で例外発生
        self.mock_order_repository.save_mt5_result.side_effect = Exception("DynamoDB connection timeout")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        # 注文自体は成功しているため、successはTrue
        assert success is True
        assert result is not None
        assert result.order == 99999999

        # DynamoDB保存は試みられた
        self.mock_order_repository.save_mt5_result.assert_called_once()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_validation_service_exception(self, mock_mt5):
        """
        ValidationServiceで例外発生

        条件: check_tp_sl_validity()で例外発生
        期待: execute_order()=False、例外ログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # ValidationServiceで例外発生
        self.mock_validation_service.check_tp_sl_validity.side_effect = Exception("Invalid TP/SL calculation")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

        # order_sendは呼ばれない
        mock_mt5.order_send.assert_not_called()

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_symbol_info_tick_exception(self, mock_mt5):
        """
        symbol_info_tick()で例外発生

        条件: symbol_info_tick()が例外発生（MT5 API内部エラー）
        期待: execute_order()=False、例外ログ
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0

        # symbol_info_tickで例外発生
        mock_mt5.symbol_info_tick.side_effect = Exception("MT5 symbol not found")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_invalid_credentials_format(self, mock_mt5):
        """
        不正なcredentials形式

        条件: credentialsに必須キーが欠落
        期待: execute_order()=False、KeyError処理
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        # 不正なcredentials（mt5_loginが欠落）
        invalid_credentials = {
            # 'mt5_login': 123456,  # 欠落
            'mt5_password': 'test_pass',
            'mt5_server': 'TestServer'
        }

        # Act
        success, result = self.executor.execute_order(self.market_order, invalid_credentials)

        # Assert
        assert success is False
        assert result is None

    def test_connection_ensure_exception(self):
        """
        ensure_connected()で例外発生

        条件: ensure_connected()が例外発生（ネットワークエラー等）
        期待: execute_order()=False、例外ログ
        """
        # Arrange
        self.mock_connection.ensure_connected.side_effect = Exception("Network timeout")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None

    @patch('src.infrastructure.gateways.brokers.mt5.mt5_order_executor.mt5')
    def test_memory_error_during_execution(self, mock_mt5):
        """
        メモリ不足エラー

        条件: 注文実行中にMemoryError発生
        期待: execute_order()=False、システム例外として処理
        """
        # Arrange
        self.mock_connection.ensure_connected.return_value = True

        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0

        # Tick情報Mock
        mock_tick = type('TickInfo', (), {'ask': 150.00, 'bid': 149.99})()
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # TP/SLバリデーションMock
        self.mock_validation_service.check_tp_sl_validity.return_value = (
            True,
            Decimal('151.0'),
            Decimal('149.0')
        )

        # MemoryError発生
        mock_mt5.order_send.side_effect = MemoryError("Out of memory")

        # Act
        success, result = self.executor.execute_order(self.market_order, self.credentials)

        # Assert
        assert success is False
        assert result is None


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
