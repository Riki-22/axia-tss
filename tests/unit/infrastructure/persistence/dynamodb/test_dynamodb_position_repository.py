# tests/unit/infrastructure/persistence/dynamodb/test_dynamodb_position_repository.py
"""
DynamoDB Position Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_position_repository.py
フォーカス: 例外ハンドリングテスト
"""

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from src.infrastructure.persistence.dynamodb.dynamodb_position_repository import DynamoDBPositionRepository
from src.domain.entities.position import Position


class TestDynamoDBPositionRepository:
    """DynamoDBPositionRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # Mock DynamoDB resource and table
        self.mock_dynamodb = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb.Table.return_value = self.mock_table

        self.table_name = "test-positions-table"
        self.repository = DynamoDBPositionRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb
        )

        # Sample position entity
        self.sample_position = Position(
            position_id="pos_12345",
            mt5_ticket=99999,
            symbol="USDJPY",
            side="BUY",
            volume=Decimal("1.0"),
            entry_price=Decimal("150.50"),
            current_price=Decimal("150.75"),
            unrealized_pnl=Decimal("25.00"),
            status="OPEN"
        )

    # ========================================
    # 【正常系】4テスト
    # ========================================

    def test_save_success(self):
        """
        ポジション保存成功

        条件: 有効なPositionエンティティ
        期待: save()=True、DynamoDB put_item呼び出し
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save(self.sample_position)

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

    def test_find_by_mt5_ticket_success(self):
        """
        MT5チケットでポジション検索成功

        条件: DynamoDBに該当ポジションが存在
        期待: find_by_mt5_ticket()がPositionを返す
        """
        # Arrange
        mock_item = {
            'pk': 'POSITION#99999',
            'sk': 'METADATA',
            'position_id': 'pos_12345',
            'mt5_ticket': 99999,
            'symbol': 'USDJPY',
            'side': 'BUY',
            'volume': Decimal('1.0'),
            'entry_price': Decimal('150.50'),
            'current_price': Decimal('150.75'),
            'unrealized_pnl': Decimal('25.00'),
            'status': 'OPEN'
        }
        self.mock_table.get_item.return_value = {'Item': mock_item}

        # Act
        result = self.repository.find_by_mt5_ticket(99999)

        # Assert
        assert result is not None
        assert result.mt5_ticket == 99999
        assert result.symbol == 'USDJPY'

    def test_find_open_positions_success(self):
        """
        オープンポジション検索成功

        条件: GSI1に複数のOPENポジションが存在
        期待: find_open_positions()がPositionリストを返す
        """
        # Arrange
        mock_items = [
            {
                'position_id': 'pos_1',
                'mt5_ticket': 11111,
                'symbol': 'USDJPY',
                'side': 'BUY',
                'volume': Decimal('1.0'),
                'entry_price': Decimal('150.50'),
                'current_price': Decimal('150.75'),
                'unrealized_pnl': Decimal('25.00'),
                'status': 'OPEN'
            },
            {
                'position_id': 'pos_2',
                'mt5_ticket': 22222,
                'symbol': 'EURUSD',
                'side': 'SELL',
                'volume': Decimal('0.5'),
                'entry_price': Decimal('1.0850'),
                'current_price': Decimal('1.0845'),
                'unrealized_pnl': Decimal('2.50'),
                'status': 'OPEN'
            }
        ]
        self.mock_table.query.return_value = {'Items': mock_items}

        # Act
        result = self.repository.find_open_positions()

        # Assert
        assert len(result) == 2
        assert all(isinstance(pos, Position) for pos in result)

    def test_update_status_success(self):
        """
        ポジションステータス更新成功

        条件: 有効なmt5_ticketとstatus
        期待: update_status()=True、楽観的ロック使用
        """
        # Arrange
        current_item = {
            'pk': 'POSITION#99999',
            'sk': 'METADATA',
            'version': 1,
            'status': 'OPEN'
        }
        self.mock_table.get_item.return_value = {'Item': current_item}
        self.mock_table.update_item.return_value = {}

        # Act
        result = self.repository.update_status(99999, 'CLOSED')

        # Assert
        assert result is True
        self.mock_table.update_item.assert_called_once()

    # ========================================
    # 【例外ハンドリング】12テスト
    # ========================================

    def test_save_table_not_initialized(self):
        """
        save()でテーブル未初期化

        条件: table=None
        期待: save()=False、エラーログ
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.save(self.sample_position)

        # Assert
        assert result is False

    def test_save_dynamodb_exception(self):
        """
        save()でDynamoDB例外発生

        条件: table.put_item()でException発生
        期待: save()=False、エラーログ
        """
        # Arrange
        self.mock_table.put_item.side_effect = Exception("DynamoDB connection timeout")

        # Act
        result = self.repository.save(self.sample_position)

        # Assert
        assert result is False

    def test_find_by_mt5_ticket_table_not_initialized(self):
        """
        find_by_mt5_ticket()でテーブル未初期化

        条件: table=None
        期待: find_by_mt5_ticket()=None、エラーログ
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.find_by_mt5_ticket(99999)

        # Assert
        assert result is None

    def test_find_by_mt5_ticket_dynamodb_exception(self):
        """
        find_by_mt5_ticket()でDynamoDB例外発生

        条件: table.get_item()でException発生
        期待: find_by_mt5_ticket()=None、エラーログ
        """
        # Arrange
        self.mock_table.get_item.side_effect = Exception("DynamoDB read error")

        # Act
        result = self.repository.find_by_mt5_ticket(99999)

        # Assert
        assert result is None

    def test_find_by_position_id_table_not_initialized(self):
        """
        find_by_position_id()でテーブル未初期化

        条件: table=None
        期待: find_by_position_id()=None、エラーログ
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.find_by_position_id("pos_12345")

        # Assert
        assert result is None

    def test_find_by_position_id_scan_exception(self):
        """
        find_by_position_id()でスキャン例外発生

        条件: table.scan()でException発生
        期待: find_by_position_id()=None、エラーログ
        """
        # Arrange
        self.mock_table.scan.side_effect = Exception("DynamoDB scan error")

        # Act
        result = self.repository.find_by_position_id("pos_12345")

        # Assert
        assert result is None

    def test_find_open_positions_table_not_initialized(self):
        """
        find_open_positions()でテーブル未初期化

        条件: table=None
        期待: find_open_positions()=[]、エラーログ
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.find_open_positions()

        # Assert
        assert result == []

    def test_find_open_positions_query_exception(self):
        """
        find_open_positions()でクエリ例外発生

        条件: table.query()でException発生
        期待: find_open_positions()=[]、エラーログ
        """
        # Arrange
        self.mock_table.query.side_effect = Exception("DynamoDB query error")

        # Act
        result = self.repository.find_open_positions()

        # Assert
        assert result == []

    def test_find_closed_positions_scan_exception(self):
        """
        find_closed_positions()でスキャン例外発生

        条件: table.scan()でException発生
        期待: find_closed_positions()=[]、エラーログ
        """
        # Arrange
        self.mock_table.scan.side_effect = Exception("DynamoDB scan error")

        # Act
        result = self.repository.find_closed_positions()

        # Assert
        assert result == []

    def test_update_status_optimistic_lock_conflict(self):
        """
        update_status()で楽観的ロック競合

        条件: update_item()でConditionalCheckFailedException発生
        期待: update_status()=False、競合ログ
        """
        # Arrange
        current_item = {
            'pk': 'POSITION#99999',
            'sk': 'METADATA',
            'version': 1,
            'status': 'OPEN'
        }
        self.mock_table.get_item.return_value = {'Item': current_item}

        # ClientError for optimistic lock conflict
        error_response = {
            'Error': {
                'Code': 'ConditionalCheckFailedException',
                'Message': 'The conditional request failed'
            }
        }
        self.mock_table.update_item.side_effect = ClientError(error_response, 'UpdateItem')

        # Act
        result = self.repository.update_status(99999, 'CLOSED')

        # Assert
        assert result is False

    def test_update_status_position_not_found(self):
        """
        update_status()でポジション未発見

        条件: get_item()で該当アイテムなし
        期待: update_status()=False、警告ログ
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # 'Item'キーなし

        # Act
        result = self.repository.update_status(99999, 'CLOSED')

        # Assert
        assert result is False

    def test_delete_by_mt5_ticket_dynamodb_exception(self):
        """
        delete_by_mt5_ticket()でDynamoDB例外発生

        条件: table.delete_item()でException発生
        期待: delete_by_mt5_ticket()=False、エラーログ
        """
        # Arrange
        self.mock_table.delete_item.side_effect = Exception("DynamoDB delete error")

        # Act
        result = self.repository.delete_by_mt5_ticket(99999)

        # Assert
        assert result is False

    # ========================================
    # 【複雑なシナリオ】3テスト
    # ========================================

    def test_find_open_positions_with_symbol_filter(self):
        """
        シンボル指定でオープンポジション検索

        条件: symbol='USDJPY'を指定
        期待: 該当シンボルのポジションのみ返す
        """
        # Arrange
        mock_items = [
            {
                'position_id': 'pos_1',
                'mt5_ticket': 11111,
                'symbol': 'USDJPY',
                'side': 'BUY',
                'volume': Decimal('1.0'),
                'entry_price': Decimal('150.50'),
                'current_price': Decimal('150.75'),
                'unrealized_pnl': Decimal('25.00'),
                'status': 'OPEN'
            }
        ]
        self.mock_table.query.return_value = {'Items': mock_items}

        # Act
        result = self.repository.find_open_positions(symbol='USDJPY')

        # Assert
        assert len(result) == 1
        assert result[0].symbol == 'USDJPY'

    def test_get_position_statistics_table_not_initialized(self):
        """
        get_position_statistics()でテーブル未初期化

        条件: table=None
        期待: デフォルト統計値を返す
        """
        # Arrange
        self.repository.table = None

        # Act
        result = self.repository.get_position_statistics()

        # Assert
        assert result['total_positions'] == 0
        assert result['open_positions'] == 0
        assert result['closed_positions'] == 0
        assert result['total_unrealized_pnl'] == 0
        assert result['total_realized_pnl'] == 0

    def test_get_position_statistics_exception(self):
        """
        get_position_statistics()で例外発生

        条件: find_open_positions()内でException発生
        期待: デフォルト統計値を返す、エラーログ
        """
        # Arrange
        self.mock_table.query.side_effect = Exception("Statistics calculation error")

        # Act
        result = self.repository.get_position_statistics()

        # Assert
        assert result['total_positions'] == 0
        assert result['open_positions'] == 0


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
