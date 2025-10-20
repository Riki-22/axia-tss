# src/domain/entities/position.py

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Dict, Any

@dataclass
class Position:
    """ポジションエンティティ"""
    
    # アイデンティティ
    position_id: str          # アプリケーション生成ID（UUID）
    mt5_ticket: int           # MT5チケット番号（MT5からの一意識別子）
    
    # 基本属性
    symbol: str               # 通貨ペア（例: 'USDJPY'）
    side: str                 # BUY, SELL
    volume: Decimal           # ロットサイズ
    
    # 価格情報
    entry_price: Decimal      # エントリー価格
    current_price: Decimal    # 現在価格（リアルタイム更新）
    stop_loss: Optional[Decimal] = None      # ストップロス（0の場合はNone）
    take_profit: Optional[Decimal] = None    # テイクプロフィット（0の場合はNone）
    
    # 損益情報
    unrealized_pnl: Decimal = Decimal('0')   # 含み損益（通貨単位）
    realized_pnl: Optional[Decimal] = None   # 実現損益（決済時）
    swap: Decimal = Decimal('0')             # スワップ損益
    
    # 状態管理
    status: str = 'OPEN'      # OPEN, CLOSED
    
    # 関連情報
    order_id: Optional[str] = None           # 元のOrder Entity ID
    magic_number: int = 0                    # MT5マジックナンバー
    comment: str = ''                        # コメント
    
    # 時間情報
    opened_at: Optional[datetime] = None     # ポジションオープン時刻
    closed_at: Optional[datetime] = None     # ポジション決済時刻
    created_at: Optional[datetime] = None    # エンティティ作成時刻
    updated_at: Optional[datetime] = None    # 最終更新時刻

    def __post_init__(self):
        """初期化後処理"""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at

    @classmethod
    def from_mt5_position(cls, mt5_position_dict: Dict, position_id: str = None) -> 'Position':
        """
        MT5ポジション辞書からPositionエンティティを生成
        
        Args:
            mt5_position_dict: MT5PositionProviderからの辞書データ
            position_id: アプリケーション生成ID（省略時は自動生成）
            
        Returns:
            Position: Positionエンティティ
        """
        import uuid
        
        if position_id is None:
            position_id = f"POS-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}"
        
        # 価格情報変換（0の場合はNone）
        stop_loss = Decimal(str(mt5_position_dict['sl'])) if mt5_position_dict['sl'] > 0 else None
        take_profit = Decimal(str(mt5_position_dict['tp'])) if mt5_position_dict['tp'] > 0 else None
        
        return cls(
            position_id=position_id,
            mt5_ticket=mt5_position_dict['ticket'],
            symbol=mt5_position_dict['symbol'],
            side=mt5_position_dict['type'],  # 既に'BUY'/'SELL'で変換済み
            volume=Decimal(str(mt5_position_dict['volume'])),
            entry_price=Decimal(str(mt5_position_dict['price_open'])),
            current_price=Decimal(str(mt5_position_dict['price_current'])),
            stop_loss=stop_loss,
            take_profit=take_profit,
            unrealized_pnl=Decimal(str(mt5_position_dict['profit'])),
            swap=Decimal(str(mt5_position_dict['swap'])),
            magic_number=mt5_position_dict['magic'],
            comment=mt5_position_dict['comment'],
            opened_at=mt5_position_dict['time']  # 既にdatetimeオブジェクト
        )
    
    def update_current_price(self, new_price: Decimal, new_pnl: Decimal = None) -> None:
        """
        現在価格と損益を更新
        
        Args:
            new_price: 新しい現在価格
            new_pnl: 新しい含み損益（省略時は自動計算）
        """
        self.current_price = new_price
        
        if new_pnl is not None:
            self.unrealized_pnl = new_pnl
        else:
            # 簡易的な損益計算（実際はpip value考慮が必要）
            price_diff = new_price - self.entry_price
            if self.side == 'SELL':
                price_diff = -price_diff
            # 実際の計算はMT5Providerに委譲
        
        self.updated_at = datetime.now(timezone.utc)
    
    def close(self, close_price: Decimal, close_pnl: Decimal) -> None:
        """
        ポジションを決済状態に変更
        
        Args:
            close_price: 決済価格
            close_pnl: 実現損益
        """
        self.current_price = close_price
        self.realized_pnl = close_pnl
        self.status = 'CLOSED'
        self.closed_at = datetime.now(timezone.utc)
        self.updated_at = self.closed_at
    
    def calculate_pips(self) -> float:
        """
        pips損益を計算
        
        Returns:
            float: pips損益
        """
        # JPYペアの場合は0.01、その他は0.0001がpip値
        pip_value = 0.01 if 'JPY' in self.symbol else 0.0001
        
        price_diff = float(self.current_price - self.entry_price)
        if self.side == 'SELL':
            price_diff = -price_diff
            
        return price_diff / pip_value
    
    def is_profitable(self) -> bool:
        """利益ポジションかどうか判定"""
        return self.unrealized_pnl > 0
    
    def is_open(self) -> bool:
        """オープンポジションかどうか判定"""
        return self.status == 'OPEN'
    
    def to_dict(self) -> Dict[str, Any]:
        """
        PositionエンティティをDynamoDB保存用に辞書変換
        
        Returns:
            Dict: DynamoDB保存用辞書
        """
        return {
            'pk': f'POSITION#{self.mt5_ticket}',  # MT5チケット番号ベース
            'sk': 'METADATA',
            'item_type': 'Position',
            'position_id': self.position_id,
            'mt5_ticket': self.mt5_ticket,
            'symbol': self.symbol,
            'side': self.side,
            'volume': str(self.volume),
            'entry_price': str(self.entry_price),
            'current_price': str(self.current_price),
            'stop_loss': str(self.stop_loss) if self.stop_loss else None,
            'take_profit': str(self.take_profit) if self.take_profit else None,
            'unrealized_pnl': str(self.unrealized_pnl),
            'realized_pnl': str(self.realized_pnl) if self.realized_pnl else None,
            'swap': str(self.swap),
            'status': self.status,
            'order_id': self.order_id,
            'magic_number': self.magic_number,
            'comment': self.comment,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            
            # GSI1用属性（OPENポジションのみ）
            'gs1pk': 'OPEN_POSITIONS' if self.status == 'OPEN' else None,
            'gs1sk': f'SYMBOL#{self.symbol}#{self.opened_at.isoformat()}' if self.status == 'OPEN' and self.opened_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """
        DynamoDBアイテムからPositionエンティティを復元
        
        Args:
            data: DynamoDBアイテム辞書
            
        Returns:
            Position: Positionエンティティ
        """
        return cls(
            position_id=data['position_id'],
            mt5_ticket=data['mt5_ticket'],
            symbol=data['symbol'],
            side=data['side'],
            volume=Decimal(data['volume']),
            entry_price=Decimal(data['entry_price']),
            current_price=Decimal(data['current_price']),
            stop_loss=Decimal(data['stop_loss']) if data.get('stop_loss') else None,
            take_profit=Decimal(data['take_profit']) if data.get('take_profit') else None,
            unrealized_pnl=Decimal(data.get('unrealized_pnl', '0')),
            realized_pnl=Decimal(data['realized_pnl']) if data.get('realized_pnl') else None,
            swap=Decimal(data.get('swap', '0')),
            status=data.get('status', 'OPEN'),
            order_id=data.get('order_id'),
            magic_number=data.get('magic_number', 0),
            comment=data.get('comment', ''),
            opened_at=datetime.fromisoformat(data['opened_at']) if data.get('opened_at') else None,
            closed_at=datetime.fromisoformat(data['closed_at']) if data.get('closed_at') else None,
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )