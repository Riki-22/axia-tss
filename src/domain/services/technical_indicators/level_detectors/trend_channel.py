# src/domain/services/technical_indicators/level_detectors/trend_channel.py

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from scipy import stats


@dataclass
class TrendChannel:
    """トレンドチャネル"""
    upper_line: Dict  # 上部ライン {start_point, end_point, slope, intercept}
    lower_line: Dict  # 下部ライン
    middle_line: Dict  # 中心ライン
    trend_direction: str  # 'bullish', 'bearish', 'neutral'
    channel_width: float  # チャネル幅
    strength: float  # チャネルの強度
    touch_points_upper: List[int]  # 上部ラインのタッチポイント
    touch_points_lower: List[int]  # 下部ラインのタッチポイント
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'upper_line': self.upper_line,
            'lower_line': self.lower_line,
            'middle_line': self.middle_line,
            'trend_direction': self.trend_direction,
            'channel_width': self.channel_width,
            'strength': self.strength,
            'touch_count_upper': len(self.touch_points_upper),
            'touch_count_lower': len(self.touch_points_lower)
        }


class TrendChannelDetector:
    """トレンドチャネル検出器"""
    
    def __init__(self,
                 min_points: int = 3,
                 lookback_period: int = 50,
                 channel_threshold: float = 0.002,
                 min_channel_width: float = 0.001):
        """
        初期化
        
        Args:
            min_points: チャネル形成に必要な最小タッチポイント数
            lookback_period: 分析対象期間
            channel_threshold: チャネルラインへのタッチ判定閾値
            min_channel_width: 最小チャネル幅（価格に対する比率）
        """
        self.min_points = min_points
        self.lookback_period = lookback_period
        self.channel_threshold = channel_threshold
        self.min_channel_width = min_channel_width
    
    def detect(self, df: pd.DataFrame) -> Optional[TrendChannel]:
        """
        トレンドチャネルを検出
        
        Returns:
            検出されたトレンドチャネル（検出されない場合はNone）
        """
        if len(df) < self.lookback_period:
            return None
        
        # 対象期間のデータ
        recent_df = df.tail(self.lookback_period).copy()
        recent_df.reset_index(drop=True, inplace=True)
        
        # 高値と安値の極値を検出
        highs = self._find_swing_points(recent_df['high'], 'high')
        lows = self._find_swing_points(recent_df['low'], 'low')
        
        if len(highs) < self.min_points or len(lows) < self.min_points:
            return None
        
        # 最適なチャネルラインを計算
        upper_line = self._fit_trend_line(highs, recent_df, 'high')
        lower_line = self._fit_trend_line(lows, recent_df, 'low')
        
        if not upper_line or not lower_line:
            return None
        
        # 平行チャネルに調整
        channel = self._create_parallel_channel(upper_line, lower_line, recent_df)
        
        if not channel:
            return None
        
        return channel
    
    def _find_swing_points(self, series: pd.Series, point_type: str) -> List[Dict]:
        """
        スイングポイント（極値）を検出
        """
        points = []
        window = 3 # スイング検出用のウィンドウサイズ
        
        for i in range(window, len(series) - window):
            if point_type == 'high':
                # ローカル高値
                if series.iloc[i] == series.iloc[i-window:i+window+1].max():
                    points.append({'index': i, 'value': series.iloc[i]})
            else:
                # ローカル安値
                if series.iloc[i] == series.iloc[i-window:i+window+1].min():
                    points.append({'index': i, 'value': series.iloc[i]})
        
        return points
    
    def _fit_trend_line(self, points: List[Dict], df: pd.DataFrame, 
                       column: str) -> Optional[Dict]:
        """
        トレンドラインをフィット
        """
        if len(points) < 2:
            return None
        
        x_values = [p['index'] for p in points]
        y_values = [p['value'] for p in points]
        
        # 線形回帰
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_values, y_values)
        
        # R二乗値が低すぎる場合は無効
        if abs(r_value) < 0.1:
            return None
        
        # ラインにタッチするポイントを検出
        touch_points = self._find_line_touches(df[column], slope, intercept)
        
        if len(touch_points) < self.min_points:
            return None
        
        return {
            'slope': slope,
            'intercept': intercept,
            'r_value': r_value,
            'touch_points': touch_points,
            'start_point': {'x': 0, 'y': intercept},
            'end_point': {'x': len(df) - 1, 'y': slope * (len(df) - 1) + intercept}
        }
    
    def _find_line_touches(self, series: pd.Series, slope: float, 
                          intercept: float) -> List[int]:
        """
        ラインにタッチするポイントを検出
        """
        touches = []
        
        for i in range(len(series)):
            line_value = slope * i + intercept
            price_value = series.iloc[i]
            
            # 閾値内にあるかチェック
            if abs(price_value - line_value) / price_value <= self.channel_threshold:
                touches.append(i)
        
        return touches
    
    def _create_parallel_channel(self, upper_line: Dict, lower_line: Dict, 
                                df: pd.DataFrame) -> Optional[TrendChannel]:
        """
        平行チャネルを作成
        """
        # 平均スロープを計算（平行にするため）
        avg_slope = (upper_line['slope'] + lower_line['slope']) / 2
        
        # 上部ラインの切片を再計算
        upper_touches = []
        best_upper_intercept = upper_line['intercept']
        for i in range(len(df)):
            if i in upper_line['touch_points']:
                upper_touches.append(df['high'].iloc[i] - avg_slope * i)
        
        if upper_touches:
            best_upper_intercept = max(upper_touches)  # 最も高い位置
        
        # 下部ラインの切片を再計算
        lower_touches = []
        best_lower_intercept = lower_line['intercept']
        for i in range(len(df)):
            if i in lower_line['touch_points']:
                lower_touches.append(df['low'].iloc[i] - avg_slope * i)
        
        if lower_touches:
            best_lower_intercept = min(lower_touches)  # 最も低い位置
        
        # チャネル幅の計算
        channel_width = abs(best_upper_intercept - best_lower_intercept)
        avg_price = df['close'].mean()
        
        # チャネル幅が狭すぎる場合は無効
        if channel_width / avg_price < self.min_channel_width:
            return None
        
        # 中心ラインの計算
        middle_intercept = (best_upper_intercept + best_lower_intercept) / 2
        
        # トレンド方向の判定
        if avg_slope > 0.0001:
            trend_direction = 'bullish'
        elif avg_slope < -0.0001:
            trend_direction = 'bearish'
        else:
            trend_direction = 'neutral'
        
        # チャネル強度の計算
        total_touches = len(upper_line['touch_points']) + len(lower_line['touch_points'])
        strength = min(total_touches / (self.min_points * 4), 1.0)
        
        return TrendChannel(
            upper_line={
                'slope': avg_slope,
                'intercept': best_upper_intercept,
                'start_point': {'x': 0, 'y': best_upper_intercept},
                'end_point': {'x': len(df) - 1, 'y': avg_slope * (len(df) - 1) + best_upper_intercept}
            },
            lower_line={
                'slope': avg_slope,
                'intercept': best_lower_intercept,
                'start_point': {'x': 0, 'y': best_lower_intercept},
                'end_point': {'x': len(df) - 1, 'y': avg_slope * (len(df) - 1) + best_lower_intercept}
            },
            middle_line={
                'slope': avg_slope,
                'intercept': middle_intercept,
                'start_point': {'x': 0, 'y': middle_intercept},
                'end_point': {'x': len(df) - 1, 'y': avg_slope * (len(df) - 1) + middle_intercept}
            },
            trend_direction=trend_direction,
            channel_width=channel_width,
            strength=strength,
            touch_points_upper=upper_line['touch_points'],
            touch_points_lower=lower_line['touch_points']
        )
    
    def get_channel_position(self, channel: TrendChannel, current_price: float, 
                            current_index: int) -> Dict:
        """
        現在価格のチャネル内での位置を取得
        """
        if not channel:
            return {'position': 'no_channel'}
        
        # 現在位置でのチャネル値
        upper_value = channel.upper_line['slope'] * current_index + channel.upper_line['intercept']
        lower_value = channel.lower_line['slope'] * current_index + channel.lower_line['intercept']
        middle_value = channel.middle_line['slope'] * current_index + channel.middle_line['intercept']
        
        # チャネル内での相対位置（0=下部、1=上部）
        if upper_value != lower_value:
            relative_position = (current_price - lower_value) / (upper_value - lower_value)
        else:
            relative_position = 0.5
        
        # ポジション判定
        if current_price > upper_value:
            position = 'above_channel'
        elif current_price < lower_value:
            position = 'below_channel'
        elif current_price > middle_value:
            position = 'upper_half'
        else:
            position = 'lower_half'
        
        return {
            'position': position,
            'relative_position': relative_position,
            'distance_to_upper': upper_value - current_price,
            'distance_to_lower': current_price - lower_value,
            'distance_to_middle': current_price - middle_value
        }