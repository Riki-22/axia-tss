# src/presentation/ui/streamlit/components/trading_charts/price_chart.py

import streamlit as st
import plotly.graph_objects as go
import logging
from typing import Optional

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# コンポーネントモジュールのインポート
from .chart_data_source import get_chart_data_source
from .chart_indicators import ChartIndicators
from .chart_renderer import ChartRenderer


class PriceChartComponent:
    """
    価格チャート表示コンポーネント（統合レイヤー）
    
    Day 2対応:
    - ChartDataSource直接生成 → get_chart_data_source()経由
    - OhlcvDataProvider統合対応
    - メタデータ対応
    """
    
    def __init__(self, use_real_data: bool = True):
        """
        Args:
            use_real_data: 実データを使用するかどうか（後方互換性）
        """
        self.use_real_data = use_real_data
        
        # 各コンポーネントの初期化
        self.data_source = get_chart_data_source()
        self.indicators = ChartIndicators(min_confidence=0.6)
        self.renderer = ChartRenderer()
        
        logger.info(f"PriceChartComponent initialized (real_data: {use_real_data})")
    
    @staticmethod
    def render_chart(
        symbol: str = "USDJPY", 
        timeframe: str = "H1", 
        days: int = 30,
        use_real_data: bool = True,
        show_indicators: bool = False  # デフォルトFalse（パフォーマンス優先）
    ) -> go.Figure:
        """
        インタラクティブな価格チャートを描画（静的メソッド）
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            days: 表示日数
            use_real_data: 実データ使用フラグ（後方互換性）
            show_indicators: インジケーター表示フラグ
        
        Returns:
            go.Figure: Plotlyチャート
        """
        try:
            # コンポーネントインスタンス作成
            chart = PriceChartComponent(use_real_data=use_real_data)
            
            # データ取得（OhlcvDataProvider経由）
            df, metadata = chart.data_source.get_ohlcv_data(
                symbol=symbol,
                timeframe=timeframe,
                period_days=days
            )
            
            if df is None or df.empty:
                error_msg = metadata.get('error', 'データが利用できません')
                logger.warning(f"No data available: {symbol} {timeframe} - {error_msg}")
                return chart.renderer._create_empty_chart(error_msg)
            
            # インジケーター検出
            indicator_results = {}
            if show_indicators:
                try:
                    indicator_results = chart.indicators.detect_all(df)
                    # 検出結果のサマリー表示
                    chart._display_detection_summary(indicator_results)
                except Exception as e:
                    logger.warning(f"Indicator detection failed: {e}")
                    # インジケーター失敗はチャート表示を止めない
            
            # データソース情報の準備
            data_source_info = {
                'source': metadata.get('source', 'unknown'),
                'cache_hit': metadata.get('cache_hit', False),
                'rows': len(df),
                'fresh': metadata.get('fresh', False)
            }
            
            # チャート作成
            fig = chart.renderer.create_chart(
                df=df,
                indicators=indicator_results,
                symbol=symbol,
                timeframe=timeframe,
                data_source=data_source_info
            )
            
            logger.info(
                f"Chart rendered: {symbol} {timeframe}, "
                f"{len(df)} rows, source={data_source_info['source']}"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Chart render error: {e}", exc_info=True)
            # エラー時は空のチャートを返す
            renderer = ChartRenderer()
            return renderer._create_empty_chart(f"エラー: {str(e)}")
    
    def render(
        self,
        symbol: str = "USDJPY",
        timeframe: str = "H1",
        days: int = 30,
        show_indicators: bool = False
    ) -> go.Figure:
        """
        インスタンスメソッドとしてのチャート描画
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            days: 表示日数
            show_indicators: インジケーター表示フラグ
        
        Returns:
            go.Figure: Plotlyチャート
        """
        try:
            # データ取得
            df, metadata = self.data_source.get_ohlcv_data(
                symbol=symbol,
                timeframe=timeframe,
                period_days=days
            )
            
            if df is None or df.empty:
                error_msg = metadata.get('error', 'データが利用できません')
                return self.renderer._create_empty_chart(error_msg)
            
            # インジケーター検出
            indicator_results = {}
            if show_indicators:
                try:
                    indicator_results = self.indicators.detect_all(df)
                    self._display_detection_summary(indicator_results)
                except Exception as e:
                    logger.warning(f"Indicator detection failed: {e}")
            
            # データソース情報
            data_source_info = {
                'source': metadata.get('source', 'unknown'),
                'cache_hit': metadata.get('cache_hit', False),
                'rows': len(df),
                'fresh': metadata.get('fresh', False)
            }
            
            # チャート作成
            fig = self.renderer.create_chart(
                df=df,
                indicators=indicator_results,
                symbol=symbol,
                timeframe=timeframe,
                data_source=data_source_info
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Chart render error: {e}", exc_info=True)
            return self.renderer._create_empty_chart(f"エラー: {str(e)}")
    
    def _display_detection_summary(self, results: dict):
        """
        検出結果のサマリーをStreamlitで表示
        
        Args:
            results: インジケーター検出結果
        """
        summary = results.get('summary', {})
        
        if not summary:
            return
        
        with st.expander("🎯 検出結果", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("合計パターン", summary.get('total_patterns', 0))
                st.metric("Bullishシグナル", summary.get('bullish_signals', 0))
                st.metric("Bearishシグナル", summary.get('bearish_signals', 0))
            
            with col2:
                st.metric("サポートレベル", summary.get('support_levels', 0))
                st.metric("レジスタンスレベル", summary.get('resistance_levels', 0))
            
            with col3:
                if summary.get('channel_detected'):
                    st.metric("チャネル", "検出済み")
                    st.write(f"方向: {summary.get('channel_direction', 'N/A')}")
                    st.write(f"幅: {summary.get('channel_width', 0):.3f}")
                else:
                    st.metric("チャネル", "未検出")
            
            # 検出器ステータス表示
            status = self.indicators.get_detection_status()
            st.write("---")
            st.write("**検出器ステータス:**")
            status_cols = st.columns(4)
            
            status_icons = {
                True: "✅",
                False: "❌"
            }
            
            with status_cols[0]:
                st.write(f"{status_icons[status.get('pinbar', False)]} Pin Bar")
            with status_cols[1]:
                st.write(f"{status_icons[status.get('engulfing', False)]} Engulfing")
            with status_cols[2]:
                st.write(f"{status_icons[status.get('support_resistance', False)]} S/R")
            with status_cols[3]:
                st.write(f"{status_icons[status.get('trend_channel', False)]} Channel")
    
    def get_component_status(self) -> dict:
        """
        コンポーネントの状態を取得
        
        Returns:
            dict: コンポーネントのステータス情報
        """
        return {
            'data_source': {
                'available': self.data_source is not None,
                'provider_available': self.data_source.data_provider is not None
            },
            'indicators': {
                'available': self.indicators.indicators_available,
                'detectors': self.indicators.get_detection_status()
            },
            'renderer': {
                'available': True
            }
        }