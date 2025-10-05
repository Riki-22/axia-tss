# src/presentation/ui/streamlit/components/price_chart.py

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ドメイン層のインポート
from src.domain.technical_indicators.pattern_detectors.pinbar_detector import PinBarDetector
from src.domain.technical_indicators.pattern_detectors.engulfing_detector import EngulfingDetector
from src.domain.technical_indicators.level_detectors.support_resistance import SupportResistanceDetector
from src.domain.technical_indicators.level_detectors.trend_channel import TrendChannelDetector


class PriceChartComponent:
    """価格チャート表示コンポーネント"""
    
    def __init__(self):
        """検出器の初期化"""
        self.pinbar_detector = PinBarDetector(min_confidence=0.6)
        self.engulfing_detector = EngulfingDetector(min_confidence=0.6)
        self.sr_detector = SupportResistanceDetector(window=20, min_touches=2)
        self.channel_detector = TrendChannelDetector(min_points=3, lookback_period=50)
    
    @staticmethod
    def render_chart(symbol="USDJPY", timeframe="H4", days=30):
        """インタラクティブな価格チャートを描画"""
        
        # インスタンス作成
        chart = PriceChartComponent()
        
        # データ生成
        df = chart._generate_dummy_data(days)
        
        # テクニカル指標の検出
        patterns = chart._detect_patterns(df)
        levels = chart._detect_levels(df)
        channel = chart._detect_channel(df)
        
        # Plotlyチャート作成
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.8, 0.2],
            subplot_titles=(f'{symbol} - {timeframe}', 'Volume')
        )
        
        # ============= メインチャート =============
        
        # ローソク足
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ),
            row=1, col=1
        )
        
        # トレンドチャネル描画
        if channel:
            chart._add_trend_channel(fig, channel, df)
        
        # サポート/レジスタンス描画
        chart._add_support_resistance(fig, levels, df)
        
        # パターンマーカー描画
        chart._add_pattern_markers(fig, patterns, df)
        
        # 移動平均線（オプション）
        # for ma_period, color in [(20, 'yellow'), (50, 'orange'), (200, 'purple')]:
        #     ma_col = f'MA{ma_period}'
        #     if len(df) >= ma_period:
        #         df[ma_col] = df['close'].rolling(window=ma_period).mean()
                
        #         fig.add_trace(
        #             go.Scatter(
        #                 x=df.index,
        #                 y=df[ma_col],
        #                 name=ma_col,
        #                 line=dict(color=color, width=1),
        #                 opacity=0.5
        #             ),
        #             row=1, col=1
        #         )
        
        # ============= ボリューム =============
        colors = ['#26a69a' if row['close'] >= row['open'] else '#ef5350' 
                  for _, row in df.iterrows()]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False
            ),
            row=2, col=1
        )
        
        # ============= レイアウト設定 =============
        fig.update_layout(
            template='plotly_dark',
            height=700,
            showlegend=True,
            legend=dict(
                orientation="h",
                xanchor="right",
                x=1
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            hovermode='x unified',
            xaxis_rangeslider_visible=False
        )
        
        # X軸の範囲選択ボタン
        fig.update_xaxes(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(step="all", label="ALL")
                ])
            ),
            row=2, col=1
        )
        
        return fig
    
    def _detect_patterns(self, df: pd.DataFrame) -> dict:
        """パターン検出を実行"""
        try:
            pinbars = self.pinbar_detector.detect(df)
            engulfings = self.engulfing_detector.detect(df)
            
            return {
                'pinbars': pinbars,
                'engulfings': engulfings
            }
        except Exception as e:
            st.warning(f"パターン検出エラー: {e}")
            return {'pinbars': [], 'engulfings': []}
    
    def _detect_levels(self, df: pd.DataFrame) -> dict:
        """サポート/レジスタンス検出を実行"""
        try:
            support_levels, resistance_levels = self.sr_detector.detect(df)
            return {
                'support': support_levels,
                'resistance': resistance_levels
            }
        except Exception as e:
            st.warning(f"レベル検出エラー: {e}")
            return {'support': [], 'resistance': []}
    
    def _detect_channel(self, df: pd.DataFrame):
        """トレンドチャネル検出を実行"""
        try:
            return self.channel_detector.detect(df)
        except Exception as e:
            st.warning(f"チャネル検出エラー: {e}")
            return None
    
    def _add_trend_channel(self, fig, channel, df):
        """トレンドチャネルを描画"""
        if not channel:
            return
        
        # 上部ライン
        x_points = [df.index[0], df.index[-1]]
        y_upper = [
            channel.upper_line['start_point']['y'],
            channel.upper_line['end_point']['y']
        ]
        
        fig.add_trace(
            go.Scatter(
                x=x_points,
                y=y_upper,
                mode='lines',
                name='Channel Upper',
                line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dash'),
                showlegend=True
            ),
            row=1, col=1
        )
        
        # 下部ライン
        y_lower = [
            channel.lower_line['start_point']['y'],
            channel.lower_line['end_point']['y']
        ]
        
        fig.add_trace(
            go.Scatter(
                x=x_points,
                y=y_lower,
                mode='lines',
                name='Channel Lower',
                line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dash'),
                showlegend=False
            ),
            row=1, col=1
        )
        
        # 中心ライン
        y_middle = [
            channel.middle_line['start_point']['y'],
            channel.middle_line['end_point']['y']
        ]
        
        fig.add_trace(
            go.Scatter(
                x=x_points,
                y=y_middle,
                mode='lines',
                name='Channel Middle',
                line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dot'),
                showlegend=False
            ),
            row=1, col=1
        )
        
        # チャネル塗りつぶし
        fig.add_trace(
            go.Scatter(
                x=x_points + x_points[::-1],
                y=y_upper + y_lower[::-1],
                fill='toself',
                fillcolor='rgba(100, 100, 100, 0.1)',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
    
    def _add_support_resistance(self, fig, levels, df):
        """サポート/レジスタンスラインを描画"""
        
        # サポートライン
        for support in levels.get('support', []):
            fig.add_hline(
                y=support.level,
                line_color="green",
                line_width=1,
                line_dash="solid",
                opacity=0.5,
                annotation_text=f"S: {support.level:.3f}",
                annotation_position="right",
                row=1, col=1
            )
        
        # レジスタンスライン
        for resistance in levels.get('resistance', []):
            fig.add_hline(
                y=resistance.level,
                line_color="red",
                line_width=1,
                line_dash="solid",
                opacity=0.5,
                annotation_text=f"R: {resistance.level:.3f}",
                annotation_position="right",
                row=1, col=1
            )
    
    def _add_pattern_markers(self, fig, patterns, df):
        """パターンマーカーを描画"""
        
        # Pin Barマーカー
        bullish_pinbars = []
        bearish_pinbars = []
        
        for pinbar in patterns.get('pinbars', []):
            if pinbar.pattern_type == 'bullish_pinbar':
                bullish_pinbars.append(pinbar)
            else:
                bearish_pinbars.append(pinbar)
        
        # Bullish Pin Bar (▲)
        if bullish_pinbars:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[p.index] for p in bullish_pinbars],
                    y=[p.price_level for p in bullish_pinbars],
                    mode='markers',
                    name='Bullish Pin Bar',
                    marker=dict(
                        symbol='triangle-up',
                        size=12,
                        color='lime',
                        line=dict(width=1, color='white')
                    ),
                    text=[f"Bullish Pin Bar<br>Confidence: {p.confidence:.2f}" for p in bullish_pinbars],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Bearish Pin Bar (▼)
        if bearish_pinbars:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[p.index] for p in bearish_pinbars],
                    y=[p.price_level for p in bearish_pinbars],
                    mode='markers',
                    name='Bearish Pin Bar',
                    marker=dict(
                        symbol='triangle-down',
                        size=12,
                        color='red',
                        line=dict(width=1, color='white')
                    ),
                    text=[f"Bearish Pin Bar<br>Confidence: {p.confidence:.2f}" for p in bearish_pinbars],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Engulfingマーカー
        bullish_engulfings = []
        bearish_engulfings = []
        
        for engulfing in patterns.get('engulfings', []):
            if engulfing.pattern_type == 'bullish_engulfing':
                bullish_engulfings.append(engulfing)
            else:
                bearish_engulfings.append(engulfing)
        
        # Bullish Engulfing (🟢)
        if bullish_engulfings:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[e.index] for e in bullish_engulfings],
                    y=[e.price_level for e in bullish_engulfings],
                    mode='markers',
                    name='Bullish Engulfing',
                    marker=dict(
                        symbol='circle',
                        size=15,
                        color='green',
                        line=dict(width=2, color='white')
                    ),
                    text=[f"Bullish Engulfing<br>Confidence: {e.confidence:.2f}" for e in bullish_engulfings],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Bearish Engulfing (🔴)
        if bearish_engulfings:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[e.index] for e in bearish_engulfings],
                    y=[e.price_level for e in bearish_engulfings],
                    mode='markers',
                    name='Bearish Engulfing',
                    marker=dict(
                        symbol='circle',
                        size=15,
                        color='darkred',
                        line=dict(width=2, color='white')
                    ),
                    text=[f"Bearish Engulfing<br>Confidence: {e.confidence:.2f}" for e in bearish_engulfings],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
    
    @staticmethod
    def _generate_dummy_data(days=30):
        """ダミーの価格データを生成（パターンを意図的に含む）"""
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
        
        # トレンドのあるデータを生成
        np.random.seed(42)
        trend = np.linspace(150, 155, len(dates))
        noise = np.cumsum(np.random.randn(len(dates)) * 0.1)
        close_prices = trend + noise
        
        data = []
        for i, date in enumerate(dates):
            close = close_prices[i]
            
            # 意図的にパターンを作成（10%の確率）
            if np.random.random() < 0.1:
                # Pin Barパターンを作成
                if np.random.random() < 0.5:
                    # Bullish Pin Bar
                    open_price = close + np.random.uniform(0.05, 0.1)
                    high = max(open_price, close) + np.random.uniform(0, 0.05)
                    low = min(open_price, close) - np.random.uniform(0.2, 0.3)
                else:
                    # Bearish Pin Bar
                    open_price = close - np.random.uniform(0.05, 0.1)
                    high = max(open_price, close) + np.random.uniform(0.2, 0.3)
                    low = min(open_price, close) - np.random.uniform(0, 0.05)
            else:
                # 通常のローソク足
                open_price = close + np.random.uniform(-0.1, 0.1)
                high = max(open_price, close) + abs(np.random.uniform(0, 0.2))
                low = min(open_price, close) - abs(np.random.uniform(0, 0.2))
            
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'datetime': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        return df