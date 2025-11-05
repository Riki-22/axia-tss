# tests/unit/infrastructure/persistence/dynamodb/test_order_repository.py
"""
DynamoDB Order Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_order_repository.py
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from src.infrastructure.persistence.dynamodb.dynamodb_order_repository import DynamoDBOrderRepository
from src.domain.entities.order import Order


class TestDynamoDBOrderRepository:
    """DynamoDBOrderRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックDynamoDBリソース
        self.mock_dynamodb_resource = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb_resource.Table.return_value = self.mock_table

        # リポジトリインスタンス
        self.table_name = "TSS_Positions"
        self.repository = DynamoDBOrderRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb_resource
        )

        # テスト用Orderエンティティ
        self.test_order = Order(
            ticket_id=12345678,
            symbol='USDJPY',
            lot_size=Decimal('0.1'),
            order_type='MARKET_BUY',
            action='BUY',
            status='OPEN',
            entry_price=Decimal('150.00'),
            tp_price=Decimal('151.00'),
            sl_price=Decimal('149.00')
        )

    # ========================================
    # 【正常系】5テスト
    # ========================================

    def test_save_order_success(self):
        """
        Order保存成功

        条件: 有効なOrderエンティティ
        期待: DynamoDB put_item成功、True返却
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save(self.test_order)

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_success_normal_order(self, mock_mt5):
        """
        MT5注文結果保存成功（通常注文）

        条件: 有効なorder_result、通常注文ペイロード
        期待: DynamoDB put_item成功、True返却
        """
        # Arrange
        # MT5定数Mock
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.ORDER_TYPE_BUY_LIMIT = 2
        mock_mt5.ORDER_TYPE_SELL_LIMIT = 3
        mock_mt5.ORDER_TYPE_BUY_STOP = 4
        mock_mt5.ORDER_TYPE_SELL_STOP = 5
        mock_mt5.ORDER_TYPE_BUY_STOP_LIMIT = 6
        mock_mt5.ORDER_TYPE_SELL_STOP_LIMIT = 7

        # MT5注文結果Mock
        mock_order_result = type('OrderResult', (), {
            'order': 87654321,
            'retcode': 10009,
            'comment': 'Request completed',
            'volume': 0.1,
            'price': 150.00,
            'request': type('Request', (), {
                'type': 0,  # ORDER_TYPE_BUY
                'tp': 151.00,
                'sl': 149.00
            })()
        })()

        # 通常注文ペイロード
        payload = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'entry_price': 150.00,
            'tp_price': 151.00,
            'sl_price': 149.00,
            'comment': 'Test Order'
        }

        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save_mt5_result(
            order_result=mock_order_result,
            payload=payload,
            mt5_login_id='123456'
        )

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数を確認
        call_args = self.mock_table.put_item.call_args[1]
        item = call_args['Item']

        assert item['ticket_id'] == 87654321
        assert item['symbol'] == 'USDJPY'
        assert item['order_action'] == 'BUY'
        assert item['order_type_executed'] == 'MARKET_BUY'
        assert item['is_scenario_order'] is False

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_success_scenario_order(self, mock_mt5):
        """
        MT5注文結果保存成功（シナリオ注文）

        条件: is_scenario_order=True
        期待: scenario関連フィールド保存
        """
        # Arrange
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.ORDER_TYPE_BUY_LIMIT = 2
        mock_mt5.ORDER_TYPE_SELL_LIMIT = 3
        mock_mt5.ORDER_TYPE_BUY_STOP = 4
        mock_mt5.ORDER_TYPE_SELL_STOP = 5
        mock_mt5.ORDER_TYPE_BUY_STOP_LIMIT = 6
        mock_mt5.ORDER_TYPE_SELL_STOP_LIMIT = 7

        mock_order_result = type('OrderResult', (), {
            'order': 99999999,
            'retcode': 10009,
            'comment': 'Request completed',
            'volume': 0.1,
            'price': 150.00,
            'request': type('Request', (), {
                'type': 0,
                'tp': 151.00,
                'sl': 149.00
            })()
        })()

        # シナリオ注文ペイロード
        payload = {
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 0.1,
            'tp_price': 151.00,
            'sl_price': 149.00,
            'is_scenario_order': True,
            'scenario_id_ref': 'SCENARIO-12345',
            'scenario_activate_price_target': 150.10,
            'scenario_entry_price_target': 150.00,
            'scenario_cancel_price_target': 149.90
        }

        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save_mt5_result(
            order_result=mock_order_result,
            payload=payload,
            mt5_login_id='123456'
        )

        # Assert
        assert result is True

        call_args = self.mock_table.put_item.call_args[1]
        item = call_args['Item']

        assert item['is_scenario_order'] is True
        assert item['scenario_id_ref'] == 'SCENARIO-12345'
        assert item['scenario_status'] == 'ACTIVE'

    def test_find_by_ticket_id_success(self):
        """
        チケットIDで検索成功

        条件: 存在するチケットID
        期待: Orderエンティティ返却
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'ORDER#12345678',
                'sk': 'METADATA',
                'ticket_id': 12345678,
                'symbol': 'USDJPY',
                'order_action': 'BUY',
                'order_status': 'OPEN',
                'order_type_executed': 'MARKET_BUY',
                'executed_lot_size': '0.1',
                'executed_entry_price': '150.00',
                'executed_tp_price': '151.00',
                'executed_sl_price': '149.00'
            }
        }

        # Act
        order = self.repository.find_by_ticket_id('12345678')

        # Assert
        assert order is not None
        assert order.ticket_id == 12345678
        assert order.symbol == 'USDJPY'
        assert order.action == 'BUY'

        self.mock_table.get_item.assert_called_once_with(
            Key={'pk': 'ORDER#12345678', 'sk': 'METADATA'}
        )

    def test_update_status_success(self):
        """
        ステータス更新成功

        条件: 有効なチケットID、新しいステータス
        期待: DynamoDB update_item成功、True返却
        """
        # Arrange
        self.mock_table.update_item.return_value = {}

        # Act
        result = self.repository.update_status(
            ticket_id='12345678',
            status='CLOSED',
            mt5_ticket=12345678
        )

        # Assert
        assert result is True
        self.mock_table.update_item.assert_called_once()

        # update_itemの引数を確認
        call_args = self.mock_table.update_item.call_args[1]
        assert call_args['ExpressionAttributeValues'][':status'] == 'CLOSED'
        assert call_args['ExpressionAttributeValues'][':mt5_ticket'] == 12345678

    # ========================================
    # 【エラーハンドリング】3テスト
    # ========================================

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_invalid_order_result(self, mock_mt5):
        """
        無効なorder_result

        条件: order_result=None または order属性なし
        期待: False返却、エラーログ
        """
        # Test Case 1: None
        result = self.repository.save_mt5_result(
            order_result=None,
            payload={},
            mt5_login_id='123456'
        )
        assert result is False

        # Test Case 2: order属性なし
        invalid_result = type('InvalidResult', (), {})()
        result = self.repository.save_mt5_result(
            order_result=invalid_result,
            payload={},
            mt5_login_id='123456'
        )
        assert result is False

    def test_find_by_ticket_id_not_found(self):
        """
        チケットIDで検索（見つからない）

        条件: 存在しないチケットID
        期待: None返却
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # Itemなし

        # Act
        order = self.repository.find_by_ticket_id('99999999')

        # Assert
        assert order is None

    def test_save_order_table_not_initialized(self):
        """
        Order保存（テーブル未初期化）

        条件: DynamoDBテーブル=None
        期待: False返却、エラーログ
        """
        # Arrange
        repo_no_table = DynamoDBOrderRepository(
            table_name="",
            dynamodb_resource=None
        )
        repo_no_table.table = None

        # Act
        result = repo_no_table.save(self.test_order)

        # Assert
        # saveメソッドはtableがNoneでもput_itemを呼ぼうとしてエラーになる
        # 実装ではtry-exceptでFalse返却
        assert result is False
