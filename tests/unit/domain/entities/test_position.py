# tests/unit/domain/entities/test_position.py
"""Position Entity 単体テスト

対象: src/domain/entities/position.py
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.domain.entities.position import Position


class TestPositionEntity:
    """Position Entity のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        # テスト用Position作成
        self.test_position = Position(
            position_id='POS-TEST-12345678',
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
    # 【正常系】7テスト
    # ========================================

    def test_position_creation_from_mt5(self):
        """MT5データからPositionエンティティ作成

        条件: MT5Position情報の辞書データ
        期待: Positionエンティティ生成、Decimal型変換、タイムスタンプ設定
        """
        # Arrange
        mt5_position_dict = {
            'ticket': 87654321,
            'symbol': 'EURUSD',
            'type': 'SELL',
            'volume': 0.2,
            'price_open': 1.0900,
            'price_current': 1.0850,
            'sl': 1.0950,
            'tp': 1.0800,
            'profit': 10000.0,
            'swap': 50.0,
            'magic': 99999,
            'comment': 'MT5 Test',
            'time': datetime(2025, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
        }

        # Act
        position = Position.from_mt5_position(mt5_position_dict, position_id='POS-TEST-001')

        # Assert
        assert position.position_id == 'POS-TEST-001'
        assert position.mt5_ticket == 87654321
        assert position.symbol == 'EURUSD'
        assert position.side == 'SELL'
        assert position.volume == Decimal('0.2')
        assert position.entry_price == Decimal('1.09')
        assert position.current_price == Decimal('1.085')
        assert position.stop_loss == Decimal('1.095')
        assert position.take_profit == Decimal('1.08')
        assert position.unrealized_pnl == Decimal('10000.0')
        assert position.swap == Decimal('50.0')
        assert position.magic_number == 99999
        assert position.comment == 'MT5 Test'
        assert position.opened_at == datetime(2025, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
        assert position.status == 'OPEN'

    def test_position_creation_with_zero_sl_tp(self):
        """MT5データからPositionエンティティ作成（SL/TP=0）

        条件: SL=0, TP=0（未設定）
        期待: stop_loss=None, take_profit=None
        """
        # Arrange
        mt5_position_dict = {
            'ticket': 11111111,
            'symbol': 'USDJPY',
            'type': 'BUY',
            'volume': 0.1,
            'price_open': 150.00,
            'price_current': 150.50,
            'sl': 0,  # 未設定
            'tp': 0,  # 未設定
            'profit': 5000.0,
            'swap': 0,
            'magic': 0,
            'comment': '',
            'time': datetime(2025, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
        }

        # Act
        position = Position.from_mt5_position(mt5_position_dict)

        # Assert
        assert position.stop_loss is None
        assert position.take_profit is None

    def test_update_current_price(self):
        """現在価格と損益を更新

        条件: 新しい価格とP/Lを指定
        期待: current_price, unrealized_pnl, updated_at更新
        """
        # Arrange
        original_updated_at = self.test_position.updated_at

        # Act
        self.test_position.update_current_price(
            new_price=Decimal('151.00'),
            new_pnl=Decimal('10000.0')
        )

        # Assert
        assert self.test_position.current_price == Decimal('151.00')
        assert self.test_position.unrealized_pnl == Decimal('10000.0')
        assert self.test_position.updated_at > original_updated_at

    def test_close_position(self):
        """ポジションを決済状態に変更

        条件: 決済価格と実現損益を指定
        期待: status='CLOSED', realized_pnl設定, closed_at設定
        """
        # Arrange
        assert self.test_position.status == 'OPEN'
        assert self.test_position.realized_pnl is None
        assert self.test_position.closed_at is None

        # Act
        self.test_position.close(
            close_price=Decimal('151.00'),
            close_pnl=Decimal('10000.0')
        )

        # Assert
        assert self.test_position.status == 'CLOSED'
        assert self.test_position.realized_pnl == Decimal('10000.0')
        assert self.test_position.current_price == Decimal('151.00')
        assert self.test_position.closed_at is not None
        assert self.test_position.updated_at == self.test_position.closed_at

    def test_calculate_pips_jpy_pair(self):
        """pips損益を計算（JPYペア）

        条件: USDJPYペア、BUY、150.00→150.50
        期待: 50 pips利益
        """
        # Act
        pips = self.test_position.calculate_pips()

        # Assert
        # (150.50 - 150.00) / 0.01 = 50 pips
        assert pips == pytest.approx(50.0)

    def test_calculate_pips_non_jpy_pair(self):
        """pips損益を計算（非JPYペア）

        条件: EURUSDペア、SELL、1.0900→1.0850
        期待: 50 pips利益
        """
        # Arrange
        position = Position(
            position_id='POS-TEST-002',
            mt5_ticket=22222222,
            symbol='EURUSD',
            side='SELL',
            volume=Decimal('0.2'),
            entry_price=Decimal('1.0900'),
            current_price=Decimal('1.0850'),
            unrealized_pnl=Decimal('10000.0'),
            swap=Decimal('0')
        )

        # Act
        pips = position.calculate_pips()

        # Assert
        # SELL: (1.0900 - 1.0850) / 0.0001 = 50 pips
        assert pips == pytest.approx(50.0)

    def test_to_dict_conversion(self):
        """Entity → Dict 変換

        条件: 有効なPositionエンティティ
        期待: DynamoDB保存用辞書、Decimal→str、datetime→ISO8601、GSI1属性
        """
        # Act
        result = self.test_position.to_dict()

        # Assert
        assert result['pk'] == 'POSITION#12345678'
        assert result['sk'] == 'METADATA'
        assert result['item_type'] == 'Position'
        assert result['position_id'] == 'POS-TEST-12345678'
        assert result['mt5_ticket'] == 12345678
        assert result['symbol'] == 'USDJPY'
        assert result['side'] == 'BUY'
        assert result['volume'] == '0.1'
        assert result['entry_price'] == '150.00'
        assert result['current_price'] == '150.50'
        assert result['stop_loss'] == '149.00'
        assert result['take_profit'] == '151.00'
        assert result['unrealized_pnl'] == '5000.0'
        assert result['swap'] == '100.0'
        assert result['status'] == 'OPEN'
        assert result['magic_number'] == 12345
        assert result['comment'] == 'Test Position'

        # GSI1属性（OPENの場合）
        assert result['gs1pk'] == 'OPEN_POSITIONS'
        assert result['gs1sk'].startswith('SYMBOL#USDJPY#')

        # datetime → ISO8601
        assert isinstance(result['opened_at'], str)
        assert result['opened_at'] == '2025-11-01T10:00:00+00:00'

    # ========================================
    # 【変換・復元テスト】2テスト
    # ========================================

    def test_from_dict_restoration(self):
        """Dict → Entity 復元

        条件: DynamoDBアイテム辞書
        期待: str→Decimal、str→datetime、データ整合性
        """
        # Arrange
        data = {
            'position_id': 'POS-RESTORE-001',
            'mt5_ticket': 99999999,
            'symbol': 'GBPUSD',
            'side': 'BUY',
            'volume': '0.5',
            'entry_price': '1.2500',
            'current_price': '1.2550',
            'stop_loss': '1.2450',
            'take_profit': '1.2600',
            'unrealized_pnl': '25000.0',
            'realized_pnl': None,
            'swap': '150.0',
            'status': 'OPEN',
            'order_id': 'ORDER-123',
            'magic_number': 55555,
            'comment': 'Restored Position',
            'opened_at': '2025-11-05T10:00:00+00:00',
            'closed_at': None,
            'created_at': '2025-11-05T09:00:00+00:00',
            'updated_at': '2025-11-05T10:00:00+00:00'
        }

        # Act
        position = Position.from_dict(data)

        # Assert
        assert position.position_id == 'POS-RESTORE-001'
        assert position.mt5_ticket == 99999999
        assert position.symbol == 'GBPUSD'
        assert position.side == 'BUY'
        assert position.volume == Decimal('0.5')
        assert position.entry_price == Decimal('1.2500')
        assert position.current_price == Decimal('1.2550')
        assert position.stop_loss == Decimal('1.2450')
        assert position.take_profit == Decimal('1.2600')
        assert position.unrealized_pnl == Decimal('25000.0')
        assert position.realized_pnl is None
        assert position.swap == Decimal('150.0')
        assert position.status == 'OPEN'
        assert position.order_id == 'ORDER-123'
        assert position.magic_number == 55555
        assert position.comment == 'Restored Position'
        assert position.opened_at == datetime(2025, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
        assert position.closed_at is None
        assert position.created_at == datetime(2025, 11, 5, 9, 0, 0, tzinfo=timezone.utc)
        assert position.updated_at == datetime(2025, 11, 5, 10, 0, 0, tzinfo=timezone.utc)

    def test_to_dict_from_dict_roundtrip(self):
        """to_dict → from_dict 往復変換

        条件: Positionエンティティ
        期待: 往復変換後もデータ整合性維持
        """
        # Act
        dict_data = self.test_position.to_dict()
        restored_position = Position.from_dict(dict_data)

        # Assert
        assert restored_position.position_id == self.test_position.position_id
        assert restored_position.mt5_ticket == self.test_position.mt5_ticket
        assert restored_position.symbol == self.test_position.symbol
        assert restored_position.side == self.test_position.side
        assert restored_position.volume == self.test_position.volume
        assert restored_position.entry_price == self.test_position.entry_price
        assert restored_position.current_price == self.test_position.current_price
        assert restored_position.stop_loss == self.test_position.stop_loss
        assert restored_position.take_profit == self.test_position.take_profit
        assert restored_position.unrealized_pnl == self.test_position.unrealized_pnl
        assert restored_position.swap == self.test_position.swap
        assert restored_position.status == self.test_position.status

    # ========================================
    # 【状態判定テスト】1テスト
    # ========================================

    def test_is_profitable_and_is_open(self):
        """is_profitable() と is_open() の判定

        条件: 利益ポジション、OPENステータス
        期待: is_profitable()=True, is_open()=True
        """
        # Act & Assert - 利益ポジション
        assert self.test_position.is_profitable() is True
        assert self.test_position.is_open() is True

        # 損失ポジションに変更
        self.test_position.unrealized_pnl = Decimal('-5000.0')
        assert self.test_position.is_profitable() is False
        assert self.test_position.is_open() is True

        # 決済
        self.test_position.status = 'CLOSED'
        assert self.test_position.is_open() is False


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
