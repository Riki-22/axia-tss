# tests/unit/infrastructure/persistence/dynamodb/test_dynamodb_order_repository.py
"""
DynamoDB Order Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_order_repository.py
フォーカス: 例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

from src.infrastructure.persistence.dynamodb.dynamodb_order_repository import DynamoDBOrderRepository
from src.domain.entities.order import Order


class TestDynamoDBOrderRepository:
    """DynamoDBOrderRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # Mock DynamoDB resource and table
        self.mock_dynamodb = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb.Table.return_value = self.mock_table

        self.table_name = "test-orders-table"
        self.repository = DynamoDBOrderRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Sample order entity
        self.sample_order = Order(
            ticket_id="12345",
            symbol="USDJPY",
            lot_size=Decimal("1.0"),
            order_type="MARKET_BUY",
            action="BUY",
            status="OPEN"
        )

        # Sample MT5 result mock
        self.sample_mt5_result = self._create_mt5_result_mock()

        # Sample payload
        self.sample_payload = {
            'strategy_id': 'strategy_001',
            'symbol': 'USDJPY',
            'order_action': 'BUY',
            'order_type': 'MARKET',
            'lot_size': 1.0,
            'entry_price': 150.50,
            'tp_price': 151.00,
            'sl_price': 150.00,
            'comment': 'Test order',
            'is_scenario_order': False
        }

    def _create_mt5_result_mock(self):
        """MT5注文結果のモックを作成"""
        result = Mock()
        result.order = 99999999
        result.retcode = 10009  # TRADE_RETCODE_DONE
        result.price = 150.50
        result.volume = 1.0
        result.comment = "Order placed"

        # request属性
        result.request = Mock()
        result.request.type = 0  # ORDER_TYPE_BUY
        result.request.tp = 151.00
        result.request.sl = 150.00

        return result

    # ========================================
    # 【正常系】2テスト
    # ========================================

    def test_save_success(self):
        """
        注文保存成功

        条件: 有効なOrderエンティティ
        期待: save()=True、DynamoDB put_item呼び出し
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save(self.sample_order)

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_success(self, mock_mt5):
        """
        MT5注文結果保存成功

        条件: 有効なMT5結果とpayload
        期待: save_mt5_result()=True、DynamoDB put_item呼び出し
        """
        # Arrange
        mock_mt5.ORDER_TYPE_BUY = 0
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save_mt5_result(
            self.sample_mt5_result,
            self.sample_payload,
            "123456"
        )

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

    # ========================================
    # 【例外ハンドリング】8テスト
    # ========================================

    def test_save_dynamodb_exception(self):
        """
        save()でDynamoDB例外発生

        条件: table.put_item()でException発生
        期待: save()=False、エラーログ
        """
        # Arrange
        self.mock_table.put_item.side_effect = Exception("DynamoDB connection timeout")

        # Act
        result = self.repository.save(self.sample_order)

        # Assert
        assert result is False

    def test_save_order_to_dict_exception(self):
        """
        save()でOrder.to_dict()例外発生

        条件: Order.to_dict()でException発生
        期待: save()=False、エラーログ
        """
        # Arrange
        invalid_order = Mock(spec=Order)
        invalid_order.to_dict.side_effect = Exception("Serialization error")

        # Act
        result = self.repository.save(invalid_order)

        # Assert
        assert result is False

    def test_save_mt5_result_missing_table_name(self):
        """
        save_mt5_result()でtable_name欠落

        条件: table_name=None
        期待: save_mt5_result()=False、エラーログ
        """
        # Arrange
        self.repository.table_name = None

        # Act
        result = self.repository.save_mt5_result(
            self.sample_mt5_result,
            self.sample_payload,
            "123456"
        )

        # Assert
        assert result is False

    def test_save_mt5_result_invalid_order_result(self):
        """
        save_mt5_result()で無効な注文結果

        条件: order_result.order属性がNone
        期待: save_mt5_result()=False、エラーログ
        """
        # Arrange
        invalid_result = Mock()
        invalid_result.order = None

        # Act
        result = self.repository.save_mt5_result(
            invalid_result,
            self.sample_payload,
            "123456"
        )

        # Assert
        assert result is False

    def test_save_mt5_result_table_not_initialized(self):
        """
        save_mt5_result()でテーブル未初期化

        条件: self.table=None
        期待: save_mt5_result()=False、エラーログ
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.save_mt5_result(
            self.sample_mt5_result,
            self.sample_payload,
            "123456"
        )

        # Assert
        assert result is False

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_dynamodb_exception(self, mock_mt5):
        """
        save_mt5_result()でDynamoDB例外発生

        条件: table.put_item()でException発生
        期待: save_mt5_result()=False、エラーログ
        """
        # Arrange
        mock_mt5.ORDER_TYPE_BUY = 0
        self.mock_table.put_item.side_effect = Exception("DynamoDB throttling error")

        # Act
        result = self.repository.save_mt5_result(
            self.sample_mt5_result,
            self.sample_payload,
            "123456"
        )

        # Assert
        assert result is False

    def test_find_by_ticket_id_dynamodb_exception(self):
        """
        find_by_ticket_id()でDynamoDB例外発生

        条件: table.get_item()でException発生
        期待: find_by_ticket_id()=None、エラーログ
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB read error")

        # Act
        result = self.repository.find_by_ticket_id("12345")

        # Assert
        assert result is None

    def test_update_status_dynamodb_exception(self):
        """
        update_status()でDynamoDB例外発生

        条件: table.update_item()でException発生
        期待: update_status()=False、エラーログ
        """
        # Arrange
        self.mock_table.update_item.side_effect = Exception("DynamoDB update error")

        # Act
        result = self.repository.update_status("12345", "CLOSED", mt5_ticket=99999)

        # Assert
        assert result is False

    # ========================================
    # 【エッジケース】2テスト
    # ========================================

    def test_find_by_ticket_id_not_found(self):
        """
        find_by_ticket_id()で該当なし

        条件: DynamoDBにアイテムが存在しない
        期待: find_by_ticket_id()=None
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # 'Item'キーなし

        # Act
        result = self.repository.find_by_ticket_id("99999")

        # Assert
        assert result is None

    @patch('src.infrastructure.persistence.dynamodb.dynamodb_order_repository.mt5')
    def test_save_mt5_result_with_scenario_order(self, mock_mt5):
        """
        save_mt5_result()でシナリオ注文の保存

        条件: is_scenario_order=True のpayload
        期待: save_mt5_result()=True、scenario属性が正しく保存される
        """
        # Arrange
        mock_mt5.ORDER_TYPE_BUY = 0
        self.mock_table.put_item.return_value = {}

        scenario_payload = self.sample_payload.copy()
        scenario_payload.update({
            'is_scenario_order': True,
            'scenario_id_ref': 'scenario_001',
            'scenario_activate_price_target': 150.30,
            'scenario_entry_price_target': 150.50,
            'scenario_cancel_price_target': 150.70
        })

        # Act
        result = self.repository.save_mt5_result(
            self.sample_mt5_result,
            scenario_payload,
            "123456"
        )

        # Assert
        assert result is True

        # put_itemが呼ばれた引数を検証
        call_args = self.mock_table.put_item.call_args
        saved_item = call_args.kwargs['Item']

        assert saved_item['is_scenario_order'] is True
        assert saved_item['scenario_id_ref'] == 'scenario_001'
        assert saved_item['scenario_status'] == 'ACTIVE'


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
