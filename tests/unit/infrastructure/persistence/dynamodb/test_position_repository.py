# tests/unit/infrastructure/persistence/dynamodb/test_position_repository.py
"""
DynamoDB Position Repository 単体テスト

対象: src/infrastructure/persistence/dynamodb/dynamodb_position_repository.py
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError

from src.infrastructure.persistence.dynamodb.dynamodb_position_repository import DynamoDBPositionRepository
from src.domain.entities.position import Position


class TestDynamoDBPositionRepository:
    """DynamoDBPositionRepository のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックDynamoDBリソース
        self.mock_dynamodb_resource = Mock()
        self.mock_table = Mock()
        self.mock_dynamodb_resource.Table.return_value = self.mock_table

        # リポジトリインスタンス
        self.table_name = "TSS_Positions"
        self.repository = DynamoDBPositionRepository(
            table_name=self.table_name,
            dynamodb_resource=self.mock_dynamodb_resource
        )

        # テスト用Positionエンティティ
        self.test_position = Position(
            position_id='POS-12345678-abcd1234',
            mt5_ticket=12345678,
            symbol='USDJPY',
            side='BUY',
            volume=Decimal('0.1'),
            entry_price=Decimal('150.00'),
            current_price=Decimal('150.50'),
            stop_loss=Decimal('149.00'),
            take_profit=Decimal('151.00'),
            unrealized_pnl=Decimal('5000.0'),
            swap=Decimal('100.0'),
            status='OPEN',
            magic_number=12345,
            comment='Test Position',
            opened_at=datetime(2025, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
        )

    # ========================================
    # 【正常系】6テスト
    # ========================================

    def test_save_position_success(self):
        """
        ポジション保存成功

        条件: 有効なPositionエンティティ
        期待: DynamoDB put_item成功、True返却
        """
        # Arrange
        self.mock_table.put_item.return_value = {}

        # Act
        result = self.repository.save(self.test_position)

        # Assert
        assert result is True
        self.mock_table.put_item.assert_called_once()

        # put_itemの引数を確認
        call_args = self.mock_table.put_item.call_args[1]
        item = call_args['Item']

        assert item['position_id'] == 'POS-12345678-abcd1234'
        assert item['version'] == 1
        assert 'last_updated_utc' in item

    def test_find_by_mt5_ticket_success(self):
        """
        MT5チケット番号で検索成功

        条件: 存在するMT5チケット番号
        期待: Positionエンティティ返却
        """
        # Arrange
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'POSITION#12345678',
                'sk': 'METADATA',
                'position_id': 'POS-12345678-abcd1234',
                'mt5_ticket': 12345678,
                'symbol': 'USDJPY',
                'side': 'BUY',
                'volume': '0.1',
                'entry_price': '150.00',
                'current_price': '150.50',
                'stop_loss': '149.00',
                'take_profit': '151.00',
                'unrealized_pnl': '5000.0',
                'swap': '100.0',
                'status': 'OPEN',
                'magic_number': 12345,
                'comment': 'Test Position'
            }
        }

        # Act
        position = self.repository.find_by_mt5_ticket(12345678)

        # Assert
        assert position is not None
        assert position.mt5_ticket == 12345678
        assert position.symbol == 'USDJPY'
        assert position.side == 'BUY'

        self.mock_table.get_item.assert_called_once_with(
            Key={
                'pk': 'POSITION#12345678',
                'sk': 'METADATA'
            }
        )

    def test_find_open_positions_all(self):
        """
        オープンポジション検索（全件）

        条件: GSI1にOPEN_POSITIONSが複数存在
        期待: 全OPENポジションリスト返却
        """
        # Arrange
        self.mock_table.query.return_value = {
            'Items': [
                {
                    'position_id': 'POS-1',
                    'mt5_ticket': 11111111,
                    'symbol': 'USDJPY',
                    'side': 'BUY',
                    'volume': '0.1',
                    'entry_price': '150.00',
                    'current_price': '150.50',
                    'unrealized_pnl': '5000.0',
                    'swap': '0',
                    'status': 'OPEN'
                },
                {
                    'position_id': 'POS-2',
                    'mt5_ticket': 22222222,
                    'symbol': 'EURUSD',
                    'side': 'SELL',
                    'volume': '0.2',
                    'entry_price': '1.0900',
                    'current_price': '1.0850',
                    'unrealized_pnl': '10000.0',
                    'swap': '0',
                    'status': 'OPEN'
                }
            ]
        }

        # Act
        positions = self.repository.find_open_positions()

        # Assert
        assert len(positions) == 2
        assert positions[0].mt5_ticket == 11111111
        assert positions[1].mt5_ticket == 22222222

        # GSI1クエリが呼ばれたことを確認
        self.mock_table.query.assert_called_once()
        call_args = self.mock_table.query.call_args[1]
        assert call_args['IndexName'] == 'GSI1'

    def test_find_open_positions_by_symbol(self):
        """
        オープンポジション検索（シンボル指定）

        条件: 特定シンボルのOPENポジション検索
        期待: 指定シンボルのポジションのみ返却
        """
        # Arrange
        self.mock_table.query.return_value = {
            'Items': [
                {
                    'position_id': 'POS-1',
                    'mt5_ticket': 11111111,
                    'symbol': 'USDJPY',
                    'side': 'BUY',
                    'volume': '0.1',
                    'entry_price': '150.00',
                    'current_price': '150.50',
                    'unrealized_pnl': '5000.0',
                    'swap': '0',
                    'status': 'OPEN'
                }
            ]
        }

        # Act
        positions = self.repository.find_open_positions(symbol='USDJPY')

        # Assert
        assert len(positions) == 1
        assert positions[0].symbol == 'USDJPY'

        # GSI1クエリがシンボル付きで呼ばれたことを確認
        self.mock_table.query.assert_called_once()

    def test_find_closed_positions_success(self):
        """
        決済済みポジション検索

        条件: CLOSEDポジションが複数存在
        期待: 決済済みポジションリスト返却（決済日時降順）
        """
        # Arrange
        self.mock_table.scan.return_value = {
            'Items': [
                {
                    'position_id': 'POS-1',
                    'mt5_ticket': 11111111,
                    'symbol': 'USDJPY',
                    'side': 'BUY',
                    'volume': '0.1',
                    'entry_price': '150.00',
                    'current_price': '150.50',
                    'unrealized_pnl': '0',
                    'realized_pnl': '5000.0',
                    'swap': '0',
                    'status': 'CLOSED',
                    'closed_at': '2025-11-01T10:00:00+00:00'
                },
                {
                    'position_id': 'POS-2',
                    'mt5_ticket': 22222222,
                    'symbol': 'EURUSD',
                    'side': 'SELL',
                    'volume': '0.2',
                    'entry_price': '1.0900',
                    'current_price': '1.0850',
                    'unrealized_pnl': '0',
                    'realized_pnl': '10000.0',
                    'swap': '0',
                    'status': 'CLOSED',
                    'closed_at': '2025-11-02T12:00:00+00:00'
                }
            ]
        }

        # Act
        positions = self.repository.find_closed_positions()

        # Assert
        assert len(positions) == 2
        # 決済日時順（新しい順）でソートされているか確認
        assert positions[0].mt5_ticket == 22222222  # より新しい

        self.mock_table.scan.assert_called_once()

    def test_update_status_success(self):
        """
        ステータス更新成功

        条件: 有効なMT5チケット、楽観的ロック成功
        期待: DynamoDB update_item成功、True返却
        """
        # Arrange
        # 現在のアイテム取得
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'POSITION#12345678',
                'sk': 'METADATA',
                'status': 'OPEN',
                'version': 1
            }
        }

        # 更新成功
        self.mock_table.update_item.return_value = {}

        # Act
        close_data = {
            'closed_at': '2025-11-05T10:00:00+00:00',
            'realized_pnl': '5000.0'
        }
        result = self.repository.update_status(12345678, 'CLOSED', close_data)

        # Assert
        assert result is True

        self.mock_table.get_item.assert_called_once()
        self.mock_table.update_item.assert_called_once()

        # update_itemの引数を確認
        call_args = self.mock_table.update_item.call_args[1]
        assert ':status' in call_args['ExpressionAttributeValues']
        assert call_args['ExpressionAttributeValues'][':status'] == 'CLOSED'
        assert ':new_version' in call_args['ExpressionAttributeValues']
        assert call_args['ExpressionAttributeValues'][':new_version'] == 2  # version incremented

    # ========================================
    # 【エラーハンドリング】4テスト
    # ========================================

    def test_find_by_mt5_ticket_not_found(self):
        """
        MT5チケット番号で検索（見つからない）

        条件: 存在しないMT5チケット番号
        期待: None返却
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # Itemなし

        # Act
        position = self.repository.find_by_mt5_ticket(99999999)

        # Assert
        assert position is None

    def test_update_status_optimistic_lock_conflict(self):
        """
        ステータス更新（楽観的ロック競合）

        条件: 別のプロセスがバージョンを更新済み
        期待: ConditionalCheckFailed、False返却
        """
        # Arrange
        # 現在のアイテム取得
        self.mock_table.get_item.return_value = {
            'Item': {
                'pk': 'POSITION#12345678',
                'sk': 'METADATA',
                'status': 'OPEN',
                'version': 1
            }
        }

        # 楽観的ロック競合エラー
        error_response = {
            'Error': {
                'Code': 'ConditionalCheckFailedException',
                'Message': 'The conditional request failed'
            }
        }
        self.mock_table.update_item.side_effect = ClientError(error_response, 'UpdateItem')

        # Act
        result = self.repository.update_status(12345678, 'CLOSED')

        # Assert
        assert result is False

    def test_save_position_table_not_initialized(self):
        """
        ポジション保存（テーブル未初期化）

        条件: DynamoDBテーブル=None
        期待: False返却、エラーログ
        """
        # Arrange
        repo_no_table = DynamoDBPositionRepository(
            table_name="",
            dynamodb_resource=None
        )

        # Act
        result = repo_no_table.save(self.test_position)

        # Assert
        assert result is False

    def test_get_position_statistics_success(self):
        """
        統計情報取得

        条件: OPENポジション2件、CLOSEDポジション1件
        期待: 正確な統計情報返却
        """
        # Arrange
        # find_open_positionsのモック
        open_pos1 = Position(
            position_id='POS-1',
            mt5_ticket=11111111,
            symbol='USDJPY',
            side='BUY',
            volume=Decimal('0.1'),
            entry_price=Decimal('150.00'),
            current_price=Decimal('150.50'),
            unrealized_pnl=Decimal('5000.0'),
            swap=Decimal('0'),
            status='OPEN'
        )
        open_pos2 = Position(
            position_id='POS-2',
            mt5_ticket=22222222,
            symbol='EURUSD',
            side='SELL',
            volume=Decimal('0.2'),
            entry_price=Decimal('1.0900'),
            current_price=Decimal('1.0850'),
            unrealized_pnl=Decimal('10000.0'),
            swap=Decimal('0'),
            status='OPEN'
        )

        # find_closed_positionsのモック
        closed_pos = Position(
            position_id='POS-3',
            mt5_ticket=33333333,
            symbol='USDJPY',
            side='BUY',
            volume=Decimal('0.1'),
            entry_price=Decimal('150.00'),
            current_price=Decimal('150.50'),
            unrealized_pnl=Decimal('0'),
            realized_pnl=Decimal('3000.0'),
            swap=Decimal('0'),
            status='CLOSED'
        )

        self.repository.find_open_positions = Mock(return_value=[open_pos1, open_pos2])
        self.repository.find_closed_positions = Mock(return_value=[closed_pos])

        # Act
        stats = self.repository.get_position_statistics()

        # Assert
        assert stats['total_positions'] == 3
        assert stats['open_positions'] == 2
        assert stats['closed_positions'] == 1
        assert stats['total_unrealized_pnl'] == 15000.0  # 5000 + 10000
        assert stats['total_realized_pnl'] == 3000.0

    # ========================================
    # 【追加カバレッジ改善】10テスト
    # ========================================

    def test_save_position_exception_handling(self):
        """
        ポジション保存 - 例外ハンドリング

        条件: put_item()で例外発生
        期待: False返却、エラーログ
        """
        # Arrange
        self.mock_table.put_item.side_effect = Exception("DynamoDB error")

        # Act
        result = self.repository.save(self.test_position)

        # Assert
        assert result is False

    def test_find_by_position_id_success(self):
        """
        ポジションID検索 - 成功

        条件: 有効なposition_id
        期待: Positionエンティティ返却
        """
        # Arrange
        self.mock_table.scan.return_value = {
            'Items': [{
                'position_id': 'POS-12345678-abcd1234',
                'mt5_ticket': 12345678,
                'symbol': 'USDJPY',
                'side': 'BUY',
                'volume': '0.1',
                'entry_price': '150.00',
                'current_price': '150.50',
                'unrealized_pnl': '5000.0',
                'swap': '0',
                'status': 'OPEN'
            }]
        }

        # Act
        position = self.repository.find_by_position_id('POS-12345678-abcd1234')

        # Assert
        assert position is not None
        assert position.position_id == 'POS-12345678-abcd1234'
        assert position.mt5_ticket == 12345678

        # scanが呼ばれたことを確認
        self.mock_table.scan.assert_called_once()

    def test_find_by_position_id_not_found(self):
        """
        ポジションID検索 - 見つからない

        条件: 存在しないposition_id
        期待: None返却
        """
        # Arrange
        self.mock_table.scan.return_value = {'Items': []}

        # Act
        position = self.repository.find_by_position_id('POS-NONEXISTENT')

        # Assert
        assert position is None

    def test_find_open_positions_table_not_initialized(self):
        """
        オープンポジション検索 - テーブル未初期化

        条件: DynamoDBテーブル=None
        期待: 空リスト返却
        """
        # Arrange
        repo_no_table = DynamoDBPositionRepository(
            table_name="",
            dynamodb_resource=None
        )

        # Act
        positions = repo_no_table.find_open_positions()

        # Assert
        assert positions == []

    def test_find_closed_positions_with_symbol(self):
        """
        決済済みポジション検索 - symbol指定

        条件: 特定シンボルの決済済みポジション
        期待: 指定シンボルのみ返却
        """
        # Arrange
        self.mock_table.scan.return_value = {
            'Items': [{
                'position_id': 'POS-1',
                'mt5_ticket': 11111111,
                'symbol': 'USDJPY',
                'side': 'BUY',
                'volume': '0.1',
                'entry_price': '150.00',
                'current_price': '150.50',
                'unrealized_pnl': '0',
                'realized_pnl': '5000.0',
                'swap': '0',
                'status': 'CLOSED',
                'closed_at': '2025-11-01T10:00:00+00:00'
            }]
        }

        # Act
        positions = self.repository.find_closed_positions(symbol='USDJPY')

        # Assert
        assert len(positions) == 1
        assert positions[0].symbol == 'USDJPY'

        # scanがsymbol付きで呼ばれたことを確認
        self.mock_table.scan.assert_called_once()
        call_args = self.mock_table.scan.call_args[1]
        assert 'FilterExpression' in call_args

    def test_update_status_position_not_found(self):
        """
        ステータス更新 - ポジション見つからない

        条件: 存在しないMT5チケット
        期待: False返却、警告ログ
        """
        # Arrange
        self.mock_table.get_item.return_value = {}  # Itemなし

        # Act
        result = self.repository.update_status(99999999, 'CLOSED')

        # Assert
        assert result is False

    def test_delete_by_mt5_ticket_success(self):
        """
        ポジション削除 - 成功

        条件: 有効なMT5チケット
        期待: delete_item成功、True返却
        """
        # Arrange
        self.mock_table.delete_item.return_value = {}

        # Act
        result = self.repository.delete_by_mt5_ticket(12345678)

        # Assert
        assert result is True

        self.mock_table.delete_item.assert_called_once_with(
            Key={
                'pk': 'POSITION#12345678',
                'sk': 'METADATA'
            }
        )

    def test_delete_by_mt5_ticket_table_not_initialized(self):
        """
        ポジション削除 - テーブル未初期化

        条件: DynamoDBテーブル=None
        期待: False返却
        """
        # Arrange
        repo_no_table = DynamoDBPositionRepository(
            table_name="",
            dynamodb_resource=None
        )

        # Act
        result = repo_no_table.delete_by_mt5_ticket(12345678)

        # Assert
        assert result is False

    def test_get_position_statistics_table_not_initialized(self):
        """
        統計情報取得 - テーブル未初期化

        条件: DynamoDBテーブル=None
        期待: ゼロ統計返却
        """
        # Arrange
        repo_no_table = DynamoDBPositionRepository(
            table_name="",
            dynamodb_resource=None
        )

        # Act
        stats = repo_no_table.get_position_statistics()

        # Assert
        assert stats['total_positions'] == 0
        assert stats['open_positions'] == 0
        assert stats['closed_positions'] == 0
        assert stats['total_unrealized_pnl'] == 0
        assert stats['total_realized_pnl'] == 0

    def test_get_position_statistics_with_symbol(self):
        """
        統計情報取得 - symbol指定

        条件: 特定シンボルの統計情報
        期待: 指定シンボルのみの統計返却
        """
        # Arrange
        # find_open_positionsのモック（symbol指定）
        open_pos = Position(
            position_id='POS-1',
            mt5_ticket=11111111,
            symbol='USDJPY',
            side='BUY',
            volume=Decimal('0.1'),
            entry_price=Decimal('150.00'),
            current_price=Decimal('150.50'),
            unrealized_pnl=Decimal('5000.0'),
            swap=Decimal('0'),
            status='OPEN'
        )

        # find_closed_positionsのモック（symbol指定）
        closed_pos = Position(
            position_id='POS-2',
            mt5_ticket=22222222,
            symbol='USDJPY',
            side='BUY',
            volume=Decimal('0.1'),
            entry_price=Decimal('150.00'),
            current_price=Decimal('150.50'),
            unrealized_pnl=Decimal('0'),
            realized_pnl=Decimal('3000.0'),
            swap=Decimal('0'),
            status='CLOSED'
        )

        self.repository.find_open_positions = Mock(return_value=[open_pos])
        self.repository.find_closed_positions = Mock(return_value=[closed_pos])

        # Act
        stats = self.repository.get_position_statistics(symbol='USDJPY')

        # Assert
        assert stats['total_positions'] == 2
        assert stats['open_positions'] == 1
        assert stats['closed_positions'] == 1
        assert stats['total_unrealized_pnl'] == 5000.0
        assert stats['total_realized_pnl'] == 3000.0

        # find_open_positions/find_closed_positionsがsymbol付きで呼ばれたことを確認
        self.repository.find_open_positions.assert_called_once_with('USDJPY')
        self.repository.find_closed_positions.assert_called_once_with('USDJPY', limit=100)
