# src/domain/technical_indicators/pattern_detectors/pinbar_detector.py

from typing import List, Dict
import pandas as pd
from .base_pattern import BasePatternDetector, PatternSignal


class PinBarDetector(BasePatternDetector):
    """Pin Barパターン検出器"""
    
    def __init__(self, 
                 body_to_wick_ratio: float = 2.0,
                 min_wick_ratio: float = 0.66,
                 opposite_wick_ratio: float = 0.1,
                 min_confidence: float = 0.7):
        """
        Pin Bar検出器の初期化
        
        Args:
            body_to_wick_ratio: ヒゲが実体の何倍以上必要か
            min_wick_ratio: 全体の値幅に対する最小ヒゲ比率
            opposite_wick_ratio: 反対側のヒゲの最大許容比率
            min_confidence: 最小信頼度閾値
        """
        super().__init__(min_confidence)
        self.body_to_wick_ratio = body_to_wick_ratio
        self.min_wick_ratio = min_wick_ratio
        self.opposite_wick_ratio = opposite_wick_ratio
    
    def detect(self, df: pd.DataFrame) -> List[PatternSignal]:
        """
        Pin Barパターンを検出
        
        Pin Barの条件:
        - Bullish Pin Bar: 長い下ヒゲ、小さい実体、短い上ヒゲ
        - Bearish Pin Bar: 長い上ヒゲ、小さい実体、短い下ヒゲ
        """
        self.validate_dataframe(df)
        signals = []
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            
            # 基本値の取得
            open_price = row['open']
            high = row['high']
            low = row['low']
            close = row['close']
            
            # 各部分のサイズ計算
            body_size = self.calculate_body_size(open_price, close)
            upper_wick = self.calculate_upper_wick(high, open_price, close)
            lower_wick = self.calculate_lower_wick(low, open_price, close)
            total_range = high - low
            
            # ゼロ除算回避
            if total_range == 0 or body_size == 0:
                continue
            
            # Bullish Pin Bar検出（ハンマー型）
            if lower_wick > body_size * self.body_to_wick_ratio:
                if lower_wick / total_range >= self.min_wick_ratio:
                    if upper_wick / total_range <= self.opposite_wick_ratio:
                        # 信頼度計算
                        confidence = self._calculate_confidence(
                            lower_wick, body_size, upper_wick, total_range, 'bullish'
                        )
                        
                        signals.append(PatternSignal(
                            index=i,
                            timestamp=df.index[i],
                            pattern_type='bullish_pinbar',
                            confidence=confidence,
                            price_level=low * 0.995,  # マーカー表示位置（少し下）
                            metadata={
                                'body_size': body_size,
                                'lower_wick': lower_wick,
                                'upper_wick': upper_wick,
                                'total_range': total_range,
                                'body_position': 'top' if close > open_price else 'bottom'
                            }
                        ))
            
            # Bearish Pin Bar検出（流れ星型）
            elif upper_wick > body_size * self.body_to_wick_ratio:
                if upper_wick / total_range >= self.min_wick_ratio:
                    if lower_wick / total_range <= self.opposite_wick_ratio:
                        # 信頼度計算
                        confidence = self._calculate_confidence(
                            upper_wick, body_size, lower_wick, total_range, 'bearish'
                        )
                        
                        signals.append(PatternSignal(
                            index=i,
                            timestamp=df.index[i],
                            pattern_type='bearish_pinbar',
                            confidence=confidence,
                            price_level=high * 1.005,  # マーカー表示位置（少し上）
                            metadata={
                                'body_size': body_size,
                                'upper_wick': upper_wick,
                                'lower_wick': lower_wick,
                                'total_range': total_range,
                                'body_position': 'bottom' if close > open_price else 'top'
                            }
                        ))
        
        return self.filter_by_confidence(signals)
    
    def _calculate_confidence(self, main_wick: float, body_size: float, 
                            opposite_wick: float, total_range: float, 
                            pattern_type: str) -> float:
        """
        Pin Barの信頼度を計算
        
        信頼度の要素:
        1. メインのヒゲと実体の比率が大きいほど高信頼度
        2. 反対側のヒゲが小さいほど高信頼度
        3. 全体に対するヒゲの比率が大きいほど高信頼度
        """
        # ヒゲと実体の比率スコア（2倍で0.5、4倍で0.8）
        wick_body_score = min(main_wick / (body_size + 0.001) / 5, 1.0)
        
        # 反対側のヒゲの小ささスコア
        opposite_score = 1.0 - (opposite_wick / total_range)
        
        # メインヒゲの全体に対する比率スコア
        main_wick_score = main_wick / total_range
        
        # 重み付け平均
        confidence = (
            wick_body_score * 0.4 +
            opposite_score * 0.3 +
            main_wick_score * 0.3
        )
        
        return min(max(confidence, 0.0), 1.0)