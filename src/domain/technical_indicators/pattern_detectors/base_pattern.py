# src/domain/technical_indicators/pattern_detectors/base_pattern.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import pandas as pd
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PatternSignal:
    """検出されたパターンシグナル"""
    index: int  # データフレーム内のインデックス
    timestamp: datetime  # 時刻
    pattern_type: str  # パターンタイプ（例: 'bullish_pinbar', 'bearish_engulfing'）
    confidence: float  # 信頼度 (0.0 - 1.0)
    price_level: float  # 価格レベル（マーカー表示位置）
    metadata: Dict  # 追加情報（ヒゲの長さ、実体の大きさなど）
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'index': self.index,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'pattern_type': self.pattern_type,
            'confidence': self.confidence,
            'price_level': self.price_level,
            'metadata': self.metadata
        }


class BasePatternDetector(ABC):
    """パターン検出器の基底クラス"""
    
    def __init__(self, min_confidence: float = 0.7):
        """
        Args:
            min_confidence: 最小信頼度閾値
        """
        self.min_confidence = min_confidence
        
    @abstractmethod
    def detect(self, df: pd.DataFrame) -> List[PatternSignal]:
        """
        パターンを検出する
        
        Args:
            df: OHLCVデータフレーム
                必須カラム: open, high, low, close, volume
                
        Returns:
            検出されたパターンシグナルのリスト
        """
        pass
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """
        データフレームの妥当性を検証
        
        Args:
            df: 検証するデータフレーム
            
        Returns:
            bool: 妥当な場合True
            
        Raises:
            ValueError: 必須カラムが存在しない場合
        """
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"必須カラムが不足しています: {missing_columns}")
        
        if len(df) < 2:
            raise ValueError("データが不足しています（最低2本のローソク足が必要）")
            
        return True
    
    def calculate_body_size(self, open_price: float, close_price: float) -> float:
        """ローソク足の実体サイズを計算"""
        return abs(close_price - open_price)
    
    def calculate_upper_wick(self, high: float, open_price: float, close_price: float) -> float:
        """上ヒゲの長さを計算"""
        return high - max(open_price, close_price)
    
    def calculate_lower_wick(self, low: float, open_price: float, close_price: float) -> float:
        """下ヒゲの長さを計算"""
        return min(open_price, close_price) - low
    
    def is_bullish_candle(self, open_price: float, close_price: float) -> bool:
        """陽線かどうかを判定"""
        return close_price > open_price
    
    def is_bearish_candle(self, open_price: float, close_price: float) -> bool:
        """陰線かどうかを判定"""
        return close_price < open_price
    
    def filter_by_confidence(self, signals: List[PatternSignal]) -> List[PatternSignal]:
        """信頼度でフィルタリング"""
        return [s for s in signals if s.confidence >= self.min_confidence]