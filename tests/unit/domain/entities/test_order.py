# tests/unit/domain/entities/test_order.py
"""Order Entity 単体テスト

対象: src/domain/entities/order.py
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.domain.entities.order import Order


class TestOrderEntity:
    """Order Entity のテストクラス"""

    # ========================================
    # 【正常系】6テスト
    # ========================================

    def test_order_creation_basic(self):
        """基本的な注文エンティティ作成

        条件: 必須パラメータのみ指定
        期待: Orderエンティティ生成、デフォルト値設定、created_at自動設定
        """
        # Act
        order = Order(
            ticket_id='ORDER-123456',
            symbol='USDJPY',
            lot_size=Decimal('0.1'),
            order_type='MARKET',
            action='BUY'
        )

        # Assert
        assert order.ticket_id == 'ORDER-123456'
        assert order.symbol == 'USDJPY'
        assert order.lot_size == Decimal('0.1')
        assert order.order_type == 'MARKET'
        assert order.action == 'BUY'
        assert order.status == 'PENDING'  # デフォルト
        assert order.mt5_ticket is None
        assert order.entry_price is None
        assert order.tp_price is None
        assert order.sl_price is None
        assert order.created_at is not None  # 自動設定
        assert order.executed_at is None

    def test_order_creation_from_sqs_message(self):
        """SQSメッセージから注文エンティティ生成

        条件: SQSペイロード
        期待: Orderエンティティ生成、Decimal変換、TP/SL設定
        """
        # Arrange
        sqs_payload = {
            'ticket_id': 'ORDER-SQS-001',
            'symbol': 'EURUSD',
            'lot_size': 0.2,
            'order_type': 'LIMIT',
            'action': 'SELL',
            'tp_price': 1.0800,
            'sl_price': 1.0950
        }

        # Act
        order = Order.from_sqs_message(sqs_payload)

        # Assert
        assert order.ticket_id == 'ORDER-SQS-001'
        assert order.symbol == 'EURUSD'
        assert order.lot_size == Decimal('0.2')
        assert order.order_type == 'LIMIT'
        assert order.action == 'SELL'
        assert order.tp_price == Decimal('1.08')
        assert order.sl_price == Decimal('1.095')
        assert order.status == 'PENDING'

    def test_order_creation_from_sqs_without_tp_sl(self):
        """SQSメッセージから注文エンティティ生成（TP/SLなし）

        条件: TP/SL未指定のSQSペイロード
        期待: tp_price=None, sl_price=None
        """
        # Arrange
        sqs_payload = {
            'ticket_id': 'ORDER-SQS-002',
            'symbol': 'USDJPY',
            'lot_size': 0.1,
            'order_type': 'MARKET',
            'action': 'BUY'
        }

        # Act
        order = Order.from_sqs_message(sqs_payload)

        # Assert
        assert order.tp_price is None
        assert order.sl_price is None

    def test_order_to_dict_conversion(self):
        """注文エンティティをDynamoDB保存用に辞書変換

        条件: 完全なOrderエンティティ
        期待: DynamoDB保存形式、Decimal→str、datetime→ISO8601
        """
        # Arrange
        created_time = datetime(2025, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
        executed_time = datetime(2025, 11, 5, 10, 1, 0, tzinfo=timezone.utc)

        order = Order(
            ticket_id='ORDER-DICT-001',
            symbol='GBPUSD',
            lot_size=Decimal('0.5'),
            order_type='MARKET',
            action='BUY',
            status='EXECUTED',
            mt5_ticket=87654321,
            entry_price=Decimal('1.2500'),
            tp_price=Decimal('1.2600'),
            sl_price=Decimal('1.2400'),
            created_at=created_time,
            executed_at=executed_time
        )

        # Act
        result = order.to_dict()

        # Assert
        assert result['pk'] == 'ORDER#ORDER-DICT-001'
        assert result['sk'] == 'METADATA'
        assert result['ticket_id'] == 'ORDER-DICT-001'
        assert result['symbol'] == 'GBPUSD'
        assert result['lot_size'] == '0.5'
        assert result['order_type'] == 'MARKET'
        assert result['action'] == 'BUY'
        assert result['status'] == 'EXECUTED'
        assert result['mt5_ticket'] == 87654321
        assert result['entry_price'] == '1.2500'
        assert result['tp_price'] == '1.2600'
        assert result['sl_price'] == '1.2400'
        assert result['created_at'] == '2025-11-05T10:00:00+00:00'
        assert result['executed_at'] == '2025-11-05T10:01:00+00:00'

    def test_order_lifecycle_pending_to_executed(self):
        """注文ライフサイクル: PENDING → EXECUTED

        条件: 初期状態PENDING、MT5実行後EXECUTED
        期待: ステータス遷移、MT5チケット設定、executed_at設定
        """
        # Arrange - PENDING状態
        order = Order(
            ticket_id='ORDER-LIFECYCLE-001',
            symbol='USDJPY',
            lot_size=Decimal('0.1'),
            order_type='MARKET',
            action='BUY'
        )
        assert order.status == 'PENDING'
        assert order.mt5_ticket is None
        assert order.executed_at is None

        # Act - MT5実行後
        order.status = 'EXECUTED'
        order.mt5_ticket = 12345678
        order.executed_at = datetime.now(timezone.utc)

        # Assert
        assert order.status == 'EXECUTED'
        assert order.mt5_ticket == 12345678
        assert order.executed_at is not None

    def test_order_decimal_precision(self):
        """Decimal型の精度維持

        条件: 浮動小数点数をDecimalに変換
        期待: 精度が正確に維持される
        """
        # Arrange & Act
        order = Order.from_sqs_message({
            'ticket_id': 'ORDER-DECIMAL-001',
            'symbol': 'EURUSD',
            'lot_size': 0.123,  # float
            'action': 'BUY',
            'tp_price': 1.09876,  # float
            'sl_price': 1.08765   # float
        })

        # Assert
        assert order.lot_size == Decimal('0.123')
        assert order.tp_price == Decimal('1.09876')
        assert order.sl_price == Decimal('1.08765')

        # to_dict後も精度維持
        dict_data = order.to_dict()
        assert dict_data['lot_size'] == '0.123'
        assert dict_data['tp_price'] == '1.09876'
        assert dict_data['sl_price'] == '1.08765'

    # ========================================
    # 【エッジケース】2テスト
    # ========================================

    def test_order_with_zero_lot_size(self):
        """ロットサイズが0の注文

        条件: lot_size=0
        期待: エンティティ生成可能（バリデーションは別レイヤー）
        """
        # Act
        order = Order(
            ticket_id='ORDER-ZERO-LOT',
            symbol='USDJPY',
            lot_size=Decimal('0'),
            order_type='MARKET',
            action='BUY'
        )

        # Assert
        assert order.lot_size == Decimal('0')
        # 注意: ビジネスルールのバリデーションはOrderValidationServiceで行う

    def test_order_timestamp_auto_generation(self):
        """タイムスタンプ自動生成

        条件: created_at未指定
        期待: __post_init__でUTC現在時刻が自動設定
        """
        # Arrange
        before = datetime.now(timezone.utc)

        # Act
        order = Order(
            ticket_id='ORDER-TIMESTAMP-001',
            symbol='USDJPY',
            lot_size=Decimal('0.1'),
            order_type='MARKET',
            action='BUY'
        )

        # Assert
        after = datetime.now(timezone.utc)
        assert order.created_at is not None
        assert before <= order.created_at <= after


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
