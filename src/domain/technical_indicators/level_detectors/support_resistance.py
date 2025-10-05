# src/domain/technical_indicators/level_detectors/support_resistance.py

from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceLevel:
    """価格レベル（サポート/レジスタンス）"""
    level: float  # 価格レベル
    level_type: str  # 'support' or 'resistance'
    strength: float  # 強度（タッチ回数ベース）
    touch_points: List[int]  # タッチしたインデックス
    first_touch: datetime  # 最初のタッチ時刻
    last_touch: datetime  # 最後のタッチ時刻
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'level': self.level,
            'level_type': self.level_type,
            'strength': self.strength,
            'touch_count': len(self.touch_points),
            'first_touch': self.first_touch.isoformat() if isinstance(self.first_touch, datetime) else str(self.first_touch),
            'last_touch': self.last_touch.isoformat() if isinstance(self.last_touch, datetime) else str(self.last_touch)
        }


class SupportResistanceDetector:
    """サポート/レジスタンスレベル検出器"""
    
    def __init__(self,
                 window: int = 20,
                 min_touches: int = 2,
                 price_threshold: float = 0.001,
                 max_levels: int = 3):
        """
        初期化
        
        Args:
            window: ローカル高値/安値を検出するウィンドウサイズ
            min_touches: 有効なレベルと判定する最小タッチ回数
            price_threshold: 同一レベルと判定する価格の許容誤差（比率）
            max_levels: 各タイプの最大レベル数
        """
        self.window = window
        self.min_touches = min_touches
        self.price_threshold = price_threshold
        self.max_levels = max_levels
    
    def detect(self, df: pd.DataFrame) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """
        サポート/レジスタンスレベルを検出
        
        Returns:
            (サポートレベルのリスト, レジスタンスレベルのリスト)
        """
        if len(df) < self.window * 2:
            return [], []
        
        # ローカル高値/安値を検出
        local_highs = self._find_local_extrema(df, 'high', 'max')
        local_lows = self._find_local_extrema(df, 'low', 'min')
        
        # レジスタンスレベルを特定
        resistance_levels = self._identify_levels(df, local_highs, 'resistance', 'high')
        
        # サポートレベルを特定
        support_levels = self._identify_levels(df, local_lows, 'support', 'low')
        
        # 強度でソートして上位を選択
        resistance_levels = sorted(resistance_levels, key=lambda x: x.strength, reverse=True)[:self.max_levels]
        support_levels = sorted(support_levels, key=lambda x: x.strength, reverse=True)[:self.max_levels]
        
        return support_levels, resistance_levels
    
    def _find_local_extrema(self, df: pd.DataFrame, column: str, method: str) -> List[Dict]:
        """
        ローカルな高値または安値を検出
        
        Args:
            column: 'high' or 'low'
            method: 'max' or 'min'
        """
        extrema = []
        half_window = self.window // 2
        
        for i in range(half_window, len(df) - half_window):
            window_start = max(0, i - half_window)
            window_end = min(len(df), i + half_window + 1)
            window_data = df[column].iloc[window_start:window_end]
            
            if method == 'max':
                if df[column].iloc[i] == window_data.max():
                    extrema.append({
                        'index': i,
                        'price': df[column].iloc[i],
                        'timestamp': df.index[i]
                    })
            else:  # min
                if df[column].iloc[i] == window_data.min():
                    extrema.append({
                        'index': i,
                        'price': df[column].iloc[i],
                        'timestamp': df.index[i]
                    })
        
        return extrema
    
    def _identify_levels(self, df: pd.DataFrame, extrema: List[Dict], 
                        level_type: str, price_column: str) -> List[PriceLevel]:
        """
        極値からサポート/レジスタンスレベルを特定
        """
        if not extrema:
            return []
        
        # 価格でクラスタリング
        levels = []
        used_extrema = set()
        
        for i, ext in enumerate(extrema):
            if i in used_extrema:
                continue
            
            level_price = ext['price']
            cluster = [ext]
            used_extrema.add(i)
            
            # 近い価格の極値をクラスタリング
            for j, other_ext in enumerate(extrema[i+1:], i+1):
                if j in used_extrema:
                    continue
                    
                price_diff = abs(other_ext['price'] - level_price) / level_price
                if price_diff <= self.price_threshold:
                    cluster.append(other_ext)
                    used_extrema.add(j)
            
            # タッチ回数が条件を満たす場合のみレベルとして採用
            if len(cluster) >= self.min_touches:
                # 追加のタッチポイントを検出
                all_touches = self._find_all_touches(df, level_price, price_column)
                
                if len(all_touches) >= self.min_touches:
                    levels.append(PriceLevel(
                        level=level_price,
                        level_type=level_type,
                        strength=len(all_touches) / len(df),  # 正規化された強度
                        touch_points=all_touches,
                        first_touch=df.index[all_touches[0]],
                        last_touch=df.index[all_touches[-1]]
                    ))
        
        return levels
    
    def _find_all_touches(self, df: pd.DataFrame, level_price: float, 
                         price_column: str) -> List[int]:
        """
        指定された価格レベルにタッチした全てのポイントを検出
        """
        touches = []
        threshold = level_price * self.price_threshold
        
        for i in range(len(df)):
            price = df[price_column].iloc[i]
            if abs(price - level_price) <= threshold:
                touches.append(i)
        
        return touches
    
    def get_nearest_levels(self, df: pd.DataFrame, current_price: float) -> Dict:
        """
        現在価格に最も近いサポート/レジスタンスを取得
        """
        support_levels, resistance_levels = self.detect(df)
        
        nearest_support = None
        nearest_resistance = None
        
        # 最も近いサポート（現在価格より下）
        for support in support_levels:
            if support.level < current_price:
                if nearest_support is None or support.level > nearest_support.level:
                    nearest_support = support
        
        # 最も近いレジスタンス（現在価格より上）
        for resistance in resistance_levels:
            if resistance.level > current_price:
                if nearest_resistance is None or resistance.level < nearest_resistance.level:
                    nearest_resistance = resistance
        
        return {
            'nearest_support': nearest_support.to_dict() if nearest_support else None,
            'nearest_resistance': nearest_resistance.to_dict() if nearest_resistance else None,
            'all_support': [s.to_dict() for s in support_levels],
            'all_resistance': [r.to_dict() for r in resistance_levels]
        }