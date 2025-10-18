# src/presentation/ui/streamlit/components/trading_charts/chart_renderer.py

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChartRenderer:
    """Plotlyチャート描画を担当するクラス"""
    
    def __init__(self):
        """初期化"""
        self.default_colors = {
            'candlestick_up': '#26a69a',
            'candlestick_down': '#ef5350',
            'support': 'green',
            'resistance': 'red',
            'channel': 'rgba(255, 255, 255, 0.5)',
            'channel_fill': 'rgba(100, 100, 100, 0.1)',
            'bullish_marker': 'lime',
            'bearish_marker': 'red',
            'engulfing_bullish': 'green',
            'engulfing_bearish': 'darkred'
        }
    
    def create_chart(self, 
                    df: pd.DataFrame,
                    indicators: Dict[str, Any],
                    symbol: str = "USDJPY",
                    timeframe: str = "H1",
                    data_source: str = "Yahoo Finance") -> go.Figure:
        """
        完全なチャートを作成
        
        Args:
            df: OHLCVデータ
            indicators: インジケーター検出結果
            symbol: 通貨ペア
            timeframe: 時間枠
            data_source: データソース名
        
        Returns:
            go.Figure: Plotlyチャート
        """
        if df.empty:
            return self._create_empty_chart("データが利用できません")
        
        # サブプロット作成
        fig = self._create_subplots(symbol, timeframe)
        
        # メインチャート描画
        self._add_candlestick(fig, df)
        
        # インジケーター描画
        if indicators:
            patterns = indicators.get('patterns', {})
            levels = indicators.get('levels', {})
            channel = indicators.get('channel')
            
            if channel:
                self._add_trend_channel(fig, channel, df)
            
            if levels:
                self._add_support_resistance(fig, levels, df)
            
            if patterns:
                self._add_pattern_markers(fig, patterns, df)
        
        # ボリューム描画
        self._add_volume(fig, df)
        
        # レイアウト設定
        self._configure_layout(fig)
        
        # データソース情報追加
        self._add_data_source_annotation(fig, data_source)
        
        return fig
    
    def _create_subplots(self, symbol: str, timeframe: str) -> go.Figure:
        """サブプロット作成"""
        return make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.8, 0.2],
            subplot_titles=(f'{symbol} - {timeframe}', 'Volume')
        )
    
    def _add_candlestick(self, fig: go.Figure, df: pd.DataFrame):
        """ローソク足を追加"""
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                increasing_line_color=self.default_colors['candlestick_up'],
                decreasing_line_color=self.default_colors['candlestick_down']
            ),
            row=1, col=1
        )
    
    def _add_trend_channel(self, fig: go.Figure, channel: Any, df: pd.DataFrame):
        """トレンドチャネルを描画"""
        if not channel:
            return
        
        x_points = [df.index[0], df.index[-1]]
        
        # 上部ライン
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
                line=dict(color=self.default_colors['channel'], width=1, dash='dash'),
                showlegend=False
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
                line=dict(color=self.default_colors['channel'], width=1, dash='dash'),
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
                name='Trend Channel',
                line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dot'),
                showlegend=True
            ),
            row=1, col=1
        )
        
        # チャネル塗りつぶし
        fig.add_trace(
            go.Scatter(
                x=x_points + x_points[::-1],
                y=y_upper + y_lower[::-1],
                fill='toself',
                fillcolor=self.default_colors['channel_fill'],
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
    
    def _add_support_resistance(self, fig: go.Figure, levels: Dict[str, List], df: pd.DataFrame):
        """サポート/レジスタンスラインを描画"""
        support_levels = levels.get('support', [])
        resistance_levels = levels.get('resistance', [])
        
        # サポートライン
        if support_levels:
            # 最初のラインでレジェンド作成
            first_support = support_levels[0]
            fig.add_trace(
                go.Scatter(
                    x=[df.index[0], df.index[-1]],
                    y=[first_support.level, first_support.level],
                    mode='lines',
                    name='Support',
                    line=dict(color=self.default_colors['support'], width=1, dash='solid'),
                    opacity=0.5,
                    showlegend=True
                ),
                row=1, col=1
            )
            
            # 残りのサポートライン
            for support in support_levels[1:]:
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[0], df.index[-1]],
                        y=[support.level, support.level],
                        mode='lines',
                        line=dict(color=self.default_colors['support'], width=1, dash='solid'),
                        opacity=0.5,
                        showlegend=False,
                        hovertemplate=f'Support: {support.level:.3f}<extra></extra>'
                    ),
                    row=1, col=1
                )
            
            # 価格アノテーション
            for support in support_levels:
                fig.add_annotation(
                    x=df.index[-1],
                    y=support.level,
                    text=f"S: {support.level:.3f}",
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    font=dict(size=10, color=self.default_colors['support']),
                    row=1, col=1
                )
        
        # レジスタンスライン
        if resistance_levels:
            # 最初のラインでレジェンド作成
            first_resistance = resistance_levels[0]
            fig.add_trace(
                go.Scatter(
                    x=[df.index[0], df.index[-1]],
                    y=[first_resistance.level, first_resistance.level],
                    mode='lines',
                    name='Resistance',
                    line=dict(color=self.default_colors['resistance'], width=1, dash='solid'),
                    opacity=0.5,
                    showlegend=True
                ),
                row=1, col=1
            )
            
            # 残りのレジスタンスライン
            for resistance in resistance_levels[1:]:
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[0], df.index[-1]],
                        y=[resistance.level, resistance.level],
                        mode='lines',
                        line=dict(color=self.default_colors['resistance'], width=1, dash='solid'),
                        opacity=0.5,
                        showlegend=False,
                        hovertemplate=f'Resistance: {resistance.level:.3f}<extra></extra>'
                    ),
                    row=1, col=1
                )
            
            # 価格アノテーション
            for resistance in resistance_levels:
                fig.add_annotation(
                    x=df.index[-1],
                    y=resistance.level,
                    text=f"R: {resistance.level:.3f}",
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    font=dict(size=10, color=self.default_colors['resistance']),
                    row=1, col=1
                )
    
    def _add_pattern_markers(self, fig: go.Figure, patterns: Dict[str, List], df: pd.DataFrame):
        """パターンマーカーを描画"""
        
        # Bullish Pin Bar
        bullish_pinbars = patterns.get('bullish_pinbars', [])
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
                        color=self.default_colors['bullish_marker'],
                        line=dict(width=1, color='white')
                    ),
                    text=[f"Bullish Pin Bar<br>Confidence: {p.confidence:.2f}" for p in bullish_pinbars],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Bearish Pin Bar
        bearish_pinbars = patterns.get('bearish_pinbars', [])
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
                        color=self.default_colors['bearish_marker'],
                        line=dict(width=1, color='white')
                    ),
                    text=[f"Bearish Pin Bar<br>Confidence: {p.confidence:.2f}" for p in bearish_pinbars],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Bullish Engulfing
        bullish_engulfings = patterns.get('bullish_engulfings', [])
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
                        color=self.default_colors['engulfing_bullish'],
                        line=dict(width=2, color='white')
                    ),
                    text=[f"Bullish Engulfing<br>Confidence: {e.confidence:.2f}" for e in bullish_engulfings],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Bearish Engulfing
        bearish_engulfings = patterns.get('bearish_engulfings', [])
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
                        color=self.default_colors['engulfing_bearish'],
                        line=dict(width=2, color='white')
                    ),
                    text=[f"Bearish Engulfing<br>Confidence: {e.confidence:.2f}" for e in bearish_engulfings],
                    hovertemplate='%{text}<extra></extra>'
                ),
                row=1, col=1
            )
    
    def _add_volume(self, fig: go.Figure, df: pd.DataFrame):
        """ボリュームバーを追加"""        
        # ボリュームが全て0の場合は価格変動率を表示
        colors = [self.default_colors['candlestick_up'] if row['close'] >= row['open'] 
                 else self.default_colors['candlestick_down']
                 for _, row in df.iterrows()]
        
        if df['volume'].sum() == 0:
            # 価格変動率（ボラティリティ）を代替表示
            price_changes = df['close'].pct_change().abs() * 100
            
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=price_changes,
                    name='Volatility %',
                    marker_color=colors,
                    showlegend=False,
                ),
                row=2, col=1
            )
        else:
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
    
    def _configure_layout(self, fig: go.Figure):
        """
        レイアウト設定
        
        変更点:
        - X軸の範囲選択ボタンを削除（UIで期間選択するため）
        - ズーム・パン機能は維持
        """
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
        
        # X軸設定（範囲選択ボタンなし）
        fig.update_xaxes(
            rangeslider_visible=False,
            type="date",
            row=1, col=1
        )
    
    def _add_data_source_annotation(self, fig: go.Figure, data_source: dict):
        """
        データソース情報をアノテーションとして追加
        
        Args:
            data_source: dict or str
                - dict: {'source': str, 'cache_hit': bool, 'rows': int, 'fresh': bool}
                - str: データソース名
        """
        # data_sourceがdictの場合は整形
        if isinstance(data_source, dict):
            source = data_source.get('source', 'unknown').upper()
            rows = data_source.get('rows', 0)
            cache_hit = data_source.get('cache_hit', False)
            fresh = data_source.get('fresh', False)
            
            # ソース別のアイコン
            emoji_map = {
                'REDIS': '⚡',
                'MT5': '🔌',
                'S3': '📦',
                'YFINANCE': '🌐',
            }
            emoji = emoji_map.get(source, '❓')
            
            # キャッシュ状態
            cache_status = "Cache Hit" if cache_hit else "Fresh Fetch"
            
            # 鮮度
            freshness = "✅ Fresh" if fresh else "ℹ️ Cached"
            
            text = (
                f"{emoji} {source} | "
                f"{rows:,} rows | "
                f"{cache_status} | "
                f"{freshness} | "
                f"Update: {datetime.now().strftime('%H:%M:%S')}"
            )
        else:
            # 文字列の場合はそのまま使用（後方互換性）
            text = f"Data Source: {data_source} | Update: {datetime.now().strftime('%H:%M:%S')}"
        
        fig.add_annotation(
            text=text,
            xref="paper", yref="paper",
            x=1, y=1.02,
            xanchor="right",
            yanchor="bottom",
            showarrow=False,
            font=dict(size=10, color="gray")
        )
    
    def _create_empty_chart(self, message: str) -> go.Figure:
        """空のチャートを作成"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            template='plotly_dark',
            height=700,
            showlegend=False
        )
        return fig