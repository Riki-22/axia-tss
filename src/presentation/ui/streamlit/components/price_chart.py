# src/presentation/ui/streamlit/components/price_chart.py

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Market Dataクライアントのインポート
try:
    from src.infrastructure.market_data.yfinance_client import YFinanceClient
    YFINANCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"YFinance client not available: {e}")
    YFINANCE_AVAILABLE = False

# ドメイン層のインポート
try:
    from src.domain.technical_indicators.pattern_detectors.pinbar_detector import PinBarDetector
    from src.domain.technical_indicators.pattern_detectors.engulfing_detector import EngulfingDetector
    from src.domain.technical_indicators.level_detectors.support_resistance import SupportResistanceDetector
    from src.domain.technical_indicators.level_detectors.trend_channel import TrendChannelDetector
    INDICATORS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Technical indicators not available: {e}")
    INDICATORS_AVAILABLE = False


class PriceChartComponent:
    """価格チャート表示コンポーネント"""
    
    def __init__(self, use_real_data: bool = True):
        """
        Args:
            use_real_data: 実データを使用するかどうか
        """
        self.use_real_data = use_real_data and YFINANCE_AVAILABLE
        
        # データクライアント初期化
        if self.use_real_data:
            self.data_client = YFinanceClient(cache_duration=300)  # 5分キャッシュ
        else:
            self.data_client = None
            
        # 検出器の初期化
        if INDICATORS_AVAILABLE:
            self.pinbar_detector = PinBarDetector(min_confidence=0.6)
            self.engulfing_detector = EngulfingDetector(min_confidence=0.6)
            self.sr_detector = SupportResistanceDetector(window=20, min_touches=2)
            self.channel_detector = TrendChannelDetector(min_points=2, lookback_period=30)
    
    @staticmethod
    @st.cache_data(ttl=300)  # 5分キャッシュ
    def fetch_market_data(symbol: str, timeframe: str, period: str = '1mo', use_real: bool = True) -> pd.DataFrame:
        """
        市場データ取得（キャッシュ付き）
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            period: 取得期間
            use_real: 実データ使用フラグ
        """
        if use_real and YFINANCE_AVAILABLE:
            try:
                client = YFinanceClient(cache_duration=300)
                df = client.fetch_ohlcv(symbol, timeframe, period=period)
                
                if not df.empty:
                    logger.info(f"実データ取得成功: {symbol} {timeframe} - {len(df)}件")
                    return df
                else:
                    logger.warning(f"データ取得失敗、ダミーデータを使用: {symbol}")
                    return PriceChartComponent._generate_dummy_data(30)
                    
            except Exception as e:
                logger.error(f"データ取得エラー: {e}")
                return PriceChartComponent._generate_dummy_data(30)
        else:
            return PriceChartComponent._generate_dummy_data(30)
    
    @staticmethod
    def render_chart(symbol: str = "USDJPY", 
                    timeframe: str = "H1", 
                    days: int = 30,
                    use_real_data: bool = True,
                    show_indicators: bool = True) -> go.Figure:
        """
        インタラクティブな価格チャートを描画
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            days: 表示日数
            use_real_data: 実データ使用フラグ
            show_indicators: インジケーター表示フラグ
        """
        
        # データ取得期間の設定
        period_map = {
            7: '7d',
            14: '2wk',
            30: '1mo',
            60: '3mo',
            180: '6mo',
            365: '1y'
        }
        period = period_map.get(days, '1mo')
        
        # データ取得
        df = PriceChartComponent.fetch_market_data(symbol, timeframe, period, use_real_data)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="データが利用できません",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig
        
        # チャート作成
        chart = PriceChartComponent(use_real_data=use_real_data)
        
        # テクニカル指標の検出
        patterns = {}
        levels = {}
        channel = None
        
        if show_indicators and INDICATORS_AVAILABLE:
            patterns = chart._detect_patterns(df)
            levels = chart._detect_levels(df)
            channel = chart._detect_channel(df)
            
            # 検出結果の表示
            with st.expander("🎯 検出結果", expanded=False):
                st.write(f"Pin Bars: {len(patterns.get('pinbars', []))}")
                st.write(f"Engulfings: {len(patterns.get('engulfings', []))}")
                st.write(f"Support Levels: {len(levels.get('support', []))}")
                st.write(f"Resistance Levels: {len(levels.get('resistance', []))}")
                st.write(f"Channel Detected: {channel is not None}")
                if channel:
                    st.write(f"Channel Direction: {channel.trend_direction}")
                    st.write(f"Channel Width: {channel.channel_width:.3f}")
        
        # Plotlyチャート作成
        fig = chart._create_plotly_chart(df, patterns, levels, channel, symbol, timeframe, chart)
        
        # データソース情報を追加
        data_source = "Yahoo Finance" if use_real_data and YFINANCE_AVAILABLE else "Dummy Data"
        fig.add_annotation(
            text=f"Data Source: {data_source} | Update: {datetime.now().strftime('%H:%M:%S')}",
            xref="paper", yref="paper",
            x=1, y=1.02,
            xanchor="right",
            yanchor="bottom",
            showarrow=False,
            font=dict(size=10, color="gray")
        )
        
        return fig
    
    def _create_plotly_chart(self, df: pd.DataFrame, 
                           patterns: dict, 
                           levels: dict,
                           channel: dict,
                           symbol: str,
                           timeframe: str,
                           chart: 'PriceChartComponent') -> go.Figure:
        """Plotlyチャートを作成"""
        
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
        if levels:
            chart._add_support_resistance(fig, levels, df)
        
        # パターンマーカー描画
        if patterns:
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
            rangeslider_visible=False,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(step="all", label="ALL")
                ])
            ),
            type="date",
            row=1, col=1
        )
        
        return fig
    
    def _detect_patterns(self, df: pd.DataFrame) -> dict:
        """パターン検出を実行"""
        try:
            pinbars = self.pinbar_detector.detect(df)
            engulfings = self.engulfing_detector.detect(df)
            
            logger.info(f"Detected {len(pinbars)} pin bars, {len(engulfings)} engulfings")
            
            return {
                'pinbars': pinbars,
                'engulfings': engulfings
            }
        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            st.warning(f"パターン検出エラー: {e}")
            return {'pinbars': [], 'engulfings': []}
    
    def _detect_levels(self, df: pd.DataFrame) -> dict:
        """サポート/レジスタンス検出を実行"""
        try:
            support_levels, resistance_levels = self.sr_detector.detect(df)
            
            logger.info(f"Detected {len(support_levels)} support, {len(resistance_levels)} resistance")
            
            return {
                'support': support_levels,
                'resistance': resistance_levels
            }
        except Exception as e:
            logger.error(f"Level detection error: {e}")
            st.warning(f"レベル検出エラー: {e}")
            return {'support': [], 'resistance': []}
    
    def _detect_channel(self, df: pd.DataFrame):
        """トレンドチャネル検出を実行"""
        try:
            return self.channel_detector.detect(df)
        except Exception as e:
            logger.error(f"❌ Channel detection error: {e}")
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
                fillcolor='rgba(100, 100, 100, 0.1)',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
    
    def _add_support_resistance(self, fig, levels, df):
        """サポート/レジスタンスラインを描画"""
        
        # レジェンド用のダミートレースを追加（1回だけ）
        support_levels = levels.get('support', [])
        resistance_levels = levels.get('resistance', [])
        
        # サポートレジェンド（データがある場合のみ）
        if support_levels:
            # 最初のサポートラインでレジェンドを作成
            first_support = support_levels[0]
            fig.add_trace(
                go.Scatter(
                    x=[df.index[0], df.index[-1]],
                    y=[first_support.level, first_support.level],
                    mode='lines',
                    name='Support',
                    line=dict(color='green', width=1, dash='solid'),
                    opacity=0.5,
                    showlegend=True
                ),
                row=1, col=1
            )
            
            # 残りのサポートライン（レジェンドなし）
            for support in support_levels[1:]:
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[0], df.index[-1]],
                        y=[support.level, support.level],
                        mode='lines',
                        line=dict(color='green', width=1, dash='solid'),
                        opacity=0.5,
                        showlegend=False,
                        hovertemplate=f'Support: {support.level:.3f}<extra></extra>'
                    ),
                    row=1, col=1
                )
        
        # レジスタンスレジェンド（データがある場合のみ）
        if resistance_levels:
            # 最初のレジスタンスラインでレジェンドを作成
            first_resistance = resistance_levels[0]
            fig.add_trace(
                go.Scatter(
                    x=[df.index[0], df.index[-1]],
                    y=[first_resistance.level, first_resistance.level],
                    mode='lines',
                    name='Resistance',
                    line=dict(color='red', width=1, dash='solid'),
                    opacity=0.5,
                    showlegend=True
                ),
                row=1, col=1
            )
            
            # 残りのレジスタンスライン（レジェンドなし）
            for resistance in resistance_levels[1:]:
                fig.add_trace(
                    go.Scatter(
                        x=[df.index[0], df.index[-1]],
                        y=[resistance.level, resistance.level],
                        mode='lines',
                        line=dict(color='red', width=1, dash='solid'),
                        opacity=0.5,
                        showlegend=False,
                        hovertemplate=f'Resistance: {resistance.level:.3f}<extra></extra>'
                    ),
                    row=1, col=1
                )
        
        # アノテーション追加（価格表示）
        for support in support_levels:
            fig.add_annotation(
                x=df.index[-1],
                y=support.level,
                text=f"S: {support.level:.3f}",
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                font=dict(size=10, color='green'),
                row=1, col=1
            )
        
        for resistance in resistance_levels:
            fig.add_annotation(
                x=df.index[-1],
                y=resistance.level,
                text=f"R: {resistance.level:.3f}",
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                font=dict(size=10, color='red'),
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
    def _generate_dummy_data(days: int) -> pd.DataFrame:
        """ダミーデータ生成（フォールバック用）"""
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='h')
        
        # ランダムウォーク価格生成
        np.random.seed(42)
        price = 150.0
        prices = []
        
        for _ in range(len(dates)):
            change = np.random.randn() * 0.5
            price += change
            prices.append(price)
        
        # OHLCデータ生成
        df = pd.DataFrame({
            'open': prices + np.random.randn(len(dates)) * 0.1,
            'high': prices + np.abs(np.random.randn(len(dates)) * 0.3),
            'low': prices - np.abs(np.random.randn(len(dates)) * 0.3),
            'close': prices,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates)
        
        # 論理的整合性の確保
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
        
        return df