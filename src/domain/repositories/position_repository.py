# src/domain/repositories/position_repository.py

from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.entities.position import Position

class IPositionRepository(ABC):
    """ポジション管理のリポジトリインターフェース"""
    
    @abstractmethod
    def save(self, position: Position) -> bool:
        """
        ポジションを保存
        
        Args:
            position: Positionエンティティ
            
        Returns:
            bool: 保存成功時True
        """
        pass
    
    @abstractmethod
    def find_by_mt5_ticket(self, mt5_ticket: int) -> Optional[Position]:
        """
        MT5チケット番号でポジションを検索
        
        Args:
            mt5_ticket: MT5チケット番号
            
        Returns:
            Position: 見つかったPositionエンティティ、None if not found
        """
        pass
    
    @abstractmethod
    def find_by_position_id(self, position_id: str) -> Optional[Position]:
        """
        ポジションIDでポジションを検索
        
        Args:
            position_id: アプリケーション生成ポジションID
            
        Returns:
            Position: 見つかったPositionエンティティ、None if not found
        """
        pass
    
    @abstractmethod
    def find_open_positions(self, symbol: str = None) -> List[Position]:
        """
        オープンポジションを検索（GSI1活用）
        
        Args:
            symbol: 通貨ペア（省略時は全通貨ペア）
            
        Returns:
            List[Position]: オープンポジション一覧
        """
        pass
    
    @abstractmethod
    def find_closed_positions(
        self, 
        symbol: str = None, 
        limit: int = 100
    ) -> List[Position]:
        """
        決済済みポジションを検索
        
        Args:
            symbol: 通貨ペア（省略時は全通貨ペア）
            limit: 取得件数上限
            
        Returns:
            List[Position]: 決済済みポジション一覧
        """
        pass
    
    @abstractmethod
    def update_status(
        self, 
        mt5_ticket: int, 
        status: str, 
        close_data: Optional[dict] = None
    ) -> bool:
        """
        ポジションステータスを更新
        
        Args:
            mt5_ticket: MT5チケット番号
            status: 新しいステータス（OPEN, CLOSED）
            close_data: 決済データ（決済時のみ）
            
        Returns:
            bool: 更新成功時True
        """
        pass
    
    @abstractmethod
    def delete_by_mt5_ticket(self, mt5_ticket: int) -> bool:
        """
        MT5チケット番号でポジションを削除
        
        Args:
            mt5_ticket: MT5チケット番号
            
        Returns:
            bool: 削除成功時True
        """
        pass
    
    @abstractmethod
    def get_position_statistics(self, symbol: str = None) -> dict:
        """
        ポジション統計情報を取得
        
        Args:
            symbol: 通貨ペア（省略時は全通貨ペア）
            
        Returns:
            dict: 統計情報
                {
                    'total_positions': int,
                    'open_positions': int,
                    'closed_positions': int,
                    'total_unrealized_pnl': Decimal,
                    'total_realized_pnl': Decimal
                }
        """
        pass