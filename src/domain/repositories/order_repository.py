# src/domain/repositories/order_repository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.entities.order import Order

class IOrderRepository(ABC):
    """注文管理のリポジトリインターフェース"""
    
    @abstractmethod
    def save(self, order: Order) -> bool:
        """注文を保存"""
        pass
    
    @abstractmethod
    def find_by_ticket_id(self, ticket_id: str) -> Optional[Order]:
        """チケットIDで注文を検索"""
        pass
    
    @abstractmethod
    def find_by_status(self, status: str) -> List[Order]:
        """ステータスで注文を検索"""
        pass
    
    @abstractmethod
    def update_status(self, ticket_id: str, status: str, mt5_ticket: Optional[int] = None) -> bool:
        """注文ステータスを更新"""
        pass