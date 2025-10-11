# src/domain/repositories/kill_switch_repository.py
from abc import ABC, abstractmethod

class IKillSwitchRepository(ABC):
    """Kill Switch確認のリポジトリインターフェース"""
    
    @abstractmethod
    def is_active(self) -> bool:
        """Kill Switchがアクティブかどうかを確認
        
        Returns:
            bool: True = 取引停止, False = 取引可能
        """
        pass
    
    @abstractmethod
    def activate(self) -> bool:
        """Kill Switchを有効化"""
        pass
    
    @abstractmethod
    def deactivate(self) -> bool:
        """Kill Switchを無効化"""
        pass