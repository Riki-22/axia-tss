# src/domain/entities/order.py

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Dict, Any

@dataclass
class Order:
    """注文エンティティ"""
    ticket_id: str
    symbol: str
    lot_size: Decimal
    order_type: str  # MARKET, LIMIT, STOP
    action: str  # BUY, SELL
    status: str = 'PENDING'
    mt5_ticket: Optional[int] = None
    entry_price: Optional[Decimal] = None
    tp_price: Optional[Decimal] = None
    sl_price: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc) 

    @classmethod
    def from_sqs_message(cls, payload: Dict[str, Any]) -> 'Order':
        """SQSメッセージから注文エンティティを生成"""
        return cls(
            ticket_id=payload['ticket_id'],
            symbol=payload['symbol'],
            lot_size=Decimal(str(payload['lot_size'])),
            order_type=payload.get('order_type', 'MARKET'),
            action=payload['action'],
            tp_price=Decimal(str(payload['tp_price'])) if payload.get('tp_price') else None,
            sl_price=Decimal(str(payload['sl_price'])) if payload.get('sl_price') else None,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """注文エンティティをDynamoDB保存用に辞書変換"""
        return {
            'pk': f'ORDER#{self.ticket_id}',
            'sk': 'METADATA',
            'ticket_id': self.ticket_id,
            'symbol': self.symbol,
            'lot_size': str(self.lot_size),
            'order_type': self.order_type,
            'action': self.action,
            'status': self.status,
            'mt5_ticket': self.mt5_ticket,
            'entry_price': str(self.entry_price) if self.entry_price else None,
            'tp_price': str(self.tp_price) if self.tp_price else None,
            'sl_price': str(self.sl_price) if self.sl_price else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
        }