# src/domain/technical_indicators/pattern_detectors/engulfing_detector.py

from typing import List
import pandas as pd
from .base_pattern import BasePatternDetector, PatternSignal


class EngulfingDetector(BasePatternDetector):
    """Engulfingパターン検出器"""
    
    def __init__(self, 
                 min_body_ratio: float = 1.5,
                 trend_period: int = 5,
                 min_confidence: float = 0.7):
        """
        Engulfingパターン検出器の初期化
        
        Args:
            min_body_ratio: 包み込む側の実体が包み込まれる側の何倍以上必要か
            trend_period: トレンド判定に使用する期間
            min_confidence: 最小信頼度閾値
        """
        super().__init__(min_confidence)
        self.min_body_ratio = min_body_ratio
        self.trend_period = trend_period
    
    def detect(self, df: pd.DataFrame) -> List[PatternSignal]:
        """
        Engulfingパターンを検出
        
        Engulfingパターンの条件:
        - Bullish Engulfing: 下降トレンドの後、陰線を陽線が完全に包み込む
        - Bearish Engulfing: 上昇トレンドの後、陽線を陰線が完全に包み込む
        """
        self.validate_dataframe(df)
        signals = []
        
        # トレンド計算用のSMA
        if len(df) > self.trend_period:
            df['sma'] = df['close'].rolling(window=self.trend_period).mean()
        
        for i in range(2, len(df)):  # 最低2本のローソク足が必要
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            # 現在と前のローソク足の値
            curr_open = curr['open']
            curr_close = curr['close']
            curr_high = curr['high']
            curr_low = curr['low']
            
            prev_open = prev['open']
            prev_close = prev['close']
            prev_high = prev['high']
            prev_low = prev['low']
            
            # 実体サイズ
            curr_body = self.calculate_body_size(curr_open, curr_close)
            prev_body = self.calculate_body_size(prev_open, prev_close)
            
            # Bullish Engulfing検出
            if (self.is_bearish_candle(prev_open, prev_close) and  # 前日が陰線
                self.is_bullish_candle(curr_open, curr_close) and  # 当日が陽線
                curr_open <= prev_close and  # 当日始値が前日終値以下
                curr_close >= prev_open and   # 当日終値が前日始値以上
                curr_body >= prev_body * self.min_body_ratio):  # 実体サイズ条件
                
                # トレンド確認（下降トレンドが望ましい）
                trend_score = self._calculate_trend_score(df, i, 'bullish')
                
                # 信頼度計算
                confidence = self._calculate_confidence(
                    curr_body, prev_body, curr_high, curr_low, 
                    prev_high, prev_low, trend_score, 'bullish'
                )
                
                signals.append(PatternSignal(
                    index=i,
                    timestamp=df.index[i],
                    pattern_type='bullish_engulfing',
                    confidence=confidence,
                    price_level=curr_low * 0.995,
                    metadata={
                        'current_body': curr_body,
                        'previous_body': prev_body,
                        'body_ratio': curr_body / (prev_body + 0.001),
                        'trend_score': trend_score,
                        'engulfing_type': 'full' if curr_low < prev_low and curr_high > prev_high else 'body_only'
                    }
                ))
            
            # Bearish Engulfing検出
            elif (self.is_bullish_candle(prev_open, prev_close) and  # 前日が陽線
                  self.is_bearish_candle(curr_open, curr_close) and  # 当日が陰線
                  curr_open >= prev_close and  # 当日始値が前日終値以上
                  curr_close <= prev_open and   # 当日終値が前日始値以下
                  curr_body >= prev_body * self.min_body_ratio):  # 実体サイズ条件
                
                # トレンド確認（上昇トレンドが望ましい）
                trend_score = self._calculate_trend_score(df, i, 'bearish')
                
                # 信頼度計算
                confidence = self._calculate_confidence(
                    curr_body, prev_body, curr_high, curr_low, 
                    prev_high, prev_low, trend_score, 'bearish'
                )
                
                signals.append(PatternSignal(
                    index=i,
                    timestamp=df.index[i],
                    pattern_type='bearish_engulfing',
                    confidence=confidence,
                    price_level=curr_high * 1.005,
                    metadata={
                        'current_body': curr_body,
                        'previous_body': prev_body,
                        'body_ratio': curr_body / (prev_body + 0.001),
                        'trend_score': trend_score,
                        'engulfing_type': 'full' if curr_low < prev_low and curr_high > prev_high else 'body_only'
                    }
                ))
        
        return self.filter_by_confidence(signals)
    
    def _calculate_trend_score(self, df: pd.DataFrame, index: int, pattern_type: str) -> float:
        """
        トレンドスコアを計算
        Bullish Engulfingの場合は下降トレンドが高スコア
        Bearish Engulfingの場合は上昇トレンドが高スコア
        """
        if index < self.trend_period:
            return 0.5  # データ不足の場合は中立
        
        # 直近のトレンドを評価
        recent_prices = df['close'].iloc[index-self.trend_period:index]
        price_change = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]
        
        if pattern_type == 'bullish':
            # 下降トレンドほど高スコア
            return max(0, min(1, -price_change * 10 + 0.5))
        else:
            # 上昇トレンドほど高スコア
            return max(0, min(1, price_change * 10 + 0.5))
    
    def _calculate_confidence(self, curr_body: float, prev_body: float,
                            curr_high: float, curr_low: float,
                            prev_high: float, prev_low: float,
                            trend_score: float, pattern_type: str) -> float:
        """
        Engulfingパターンの信頼度を計算
        
        信頼度の要素:
        1. 実体の比率が大きいほど高信頼度
        2. 完全な包み込み（高値安値も含む）の場合はさらに高信頼度
        3. 適切なトレンドの後に出現した場合は高信頼度
        """
        # 実体比率スコア
        body_ratio = curr_body / (prev_body + 0.001)
        body_score = min(body_ratio / 3, 1.0)  # 3倍で満点
        
        # 完全包み込みスコア
        full_engulfing = (curr_high >= prev_high and curr_low <= prev_low)
        engulfing_score = 1.0 if full_engulfing else 0.7
        
        # 重み付け平均
        confidence = (
            body_score * 0.3 +
            engulfing_score * 0.3 +
            trend_score * 0.4
        )
        
        return min(max(confidence, 0.0), 1.0)