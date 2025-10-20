# src/presentation/ui/streamlit/pages/signal_page.py

import streamlit as st
import logging
import warnings
from components.trading_charts.price_chart import PriceChartComponent
from components.trading_charts.chart_data_source import get_chart_data_source

# Plotly警告を抑制
warnings.filterwarnings('ignore', message='.*keyword arguments have been deprecated.*')

logger = logging.getLogger(__name__)


def render_signal_page():
    """シグナル分析ページのレンダリング（チャート+シグナル統合）"""
    # チャート設定エリア
    _render_chart_controls()
    
    st.divider()
    
    # チャート表示（シグナル表示ON）
    _render_signal_chart()
    
    st.divider()
    
    # シグナル詳細分析
    _render_signal_analysis()


def _render_chart_controls():
    """チャート設定コントロール"""
    # データソース取得
    data_source = get_chart_data_source()
    
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        symbol = st.selectbox(
            "通貨ペア",
            ["USDJPY", "EURUSD", "GBPJPY", "AUDUSD", "EURJPY"],
            index=0,
            key="signal_symbol"
        )
    
    with col2:
        timeframe = st.selectbox(
            "時間足",
            ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            index=4,  # H1をデフォルト
            key="signal_timeframe"
        )
    
    with col3:
        period_days = st.selectbox(
            "期間",
            [1, 7, 30, 90],
            index=2,  # 30日をデフォルト
            key="signal_period"
        )
    
    with col4:
        # 強制更新ボタン
        if st.button("🔄 最新", key="signal_refresh"):
            st.cache_data.clear()
            st.rerun()
    
    # セッション状態に保存
    st.session_state.signal_chart_symbol = symbol
    st.session_state.signal_chart_timeframe = timeframe
    st.session_state.signal_chart_period = period_days


def _render_signal_chart():
    """シグナル表示付きチャート"""
    
    # セッション状態から設定取得
    symbol = st.session_state.get('signal_chart_symbol', 'USDJPY')
    timeframe = st.session_state.get('signal_chart_timeframe', 'H1')
    period_days = st.session_state.get('signal_chart_period', 30)
    
    try:
        # データソース取得
        data_source = get_chart_data_source()
        
        # チャートデータ取得
        df, metadata = data_source.get_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            period_days=period_days
        )
        
        if df is not None and not df.empty:
            # PriceChartComponent でシグナル表示ON
            chart = PriceChartComponent.render_chart(
                symbol=symbol,
                timeframe=timeframe,
                days=period_days,
                use_real_data=True,
                show_indicators=True  # シグナル表示ON
            )
            
            # チャート表示
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.warning("チャートの生成に失敗しました")
            
            # データソース情報表示
            _render_data_source_info(metadata, symbol, timeframe)
            
        else:
            st.error(f"⚠️ {symbol} {timeframe} のデータを取得できませんでした")
            logger.warning(f"No data available for signal chart: {symbol} {timeframe}")
            
    except Exception as e:
        st.error(f"⚠️ チャート表示エラー: {str(e)}")
        logger.error(f"Signal chart error: {e}", exc_info=True)


def _render_data_source_info(metadata: dict, symbol: str, timeframe: str):
    """データソース情報表示"""
    
    info_cols = st.columns(4)
    
    with info_cols[0]:
        source = metadata.get('source', 'Unknown')
        source_icons = {
            'redis': '⚡ Redis',
            'mt5': '🏦 MT5', 
            's3': '📦 S3',
            'yfinance': '🌐 yfinance'
        }
        st.caption(f"データソース: {source_icons.get(source, source)}")
    
    with info_cols[1]:
        response_time = metadata.get('response_time', 0)
        st.caption(f"取得時間: {response_time:.3f}秒")
    
    with info_cols[2]:
        row_count = metadata.get('row_count', 0)
        st.caption(f"データ数: {row_count:,}行")
    
    with info_cols[3]:
        cache_hit = metadata.get('cache_hit', False)
        cache_status = "ヒット" if cache_hit else "ミス"
        st.caption(f"キャッシュ: {cache_status}")


def _render_signal_analysis():
    """シグナル詳細分析表示"""
    
    # 現在選択されている通貨ペアを取得
    symbol = st.session_state.get('signal_chart_symbol', 'USDJPY')
    timeframe = st.session_state.get('signal_chart_timeframe', 'H1')
    
    st.markdown(f"####  {symbol} {timeframe} シグナル分析")
    
    # シグナル設定（1列レイアウト）
    st.markdown("#####  シグナル設定")
    
    # シグナル表示オプション（横並び）
    signal_option_cols = st.columns(4)
    with signal_option_cols[0]:
        show_trend = st.checkbox("トレンド", value=True, key="show_trend_signals")
    with signal_option_cols[1]:
        show_oscillator = st.checkbox("オシレーター", value=True, key="show_oscillator_signals")
    with signal_option_cols[2]:
        show_volatility = st.checkbox("ボラティリティ", value=True, key="show_volatility_signals")
    with signal_option_cols[3]:
        show_patterns = st.checkbox("パターン", value=True, key="show_pattern_signals")
    
    # シグナル感度
    sensitivity = st.slider("シグナル感度", 1, 10, 5, key="signal_sensitivity")
    
    # シグナル詳細表示
    st.markdown("##### 検出シグナル")
    _render_signal_list(symbol, timeframe, {
        'trend': show_trend,
        'oscillator': show_oscillator,
        'volatility': show_volatility,
        'patterns': show_patterns,
        'sensitivity': sensitivity
    })


def _render_signal_list(symbol: str, timeframe: str, signal_config: dict):
    """検出シグナル一覧表示"""
    
    # Phase 3実装予定: 実際のテクニカル指標から取得
    # 現在はダミーデータ
    
    # シグナル表示エリア
    signal_display_cols = st.columns(2)
    
    with signal_display_cols[0]:
        if signal_config['trend']:
            st.markdown("**トレンド系シグナル**")
            st.success("MACD: BUYシグナル")
            st.info("移動平均: 上昇トレンド")
            st.warning("⚠️ ブレイクアウト: 監視中") 
            st.success("✅ トレンド強度: 強")
            st.markdown("---")
        
        if signal_config['volatility']:
            st.markdown("**ボラティリティ系シグナル**")
            st.success("✅ ボリンジャー: 下部反発")
            st.info("ATR: 0.0045 (標準)")
            st.success("✅ ボラティリティ: 拡大中")
            st.warning("⚠️ スクイーズ: 解除")
    
    with signal_display_cols[1]:
        if signal_config['oscillator']:
            st.markdown("**オシレーター系シグナル**")
            st.warning("⚠️ RSI: 中立圏 (55)")
            st.success("✅ Stochastic: BUYゾーン")
            st.error("❌ RCI: SELLシグナル")
            st.info("モメンタム: 弱気")
            st.markdown("---")
        
        if signal_config['patterns']:
            st.markdown("**チャートパターン**")
            st.success("✅ ピンバー: 反転シグナル")
            st.info("エンガルフィング: 未検出")
            st.success("✅ サポート/レジスタンス: 150.65")
            st.info("フィボナッチ: 61.8%水準")
    
    # 統合シグナル
    st.markdown("---")
    st.markdown("**⚡ 統合判定:**")
    
    # シンプルな統合ロジック（Phase 3で高度化）
    trend_score = 3 if signal_config['trend'] else 0
    osc_score = 1 if signal_config['oscillator'] else 0  # RCI SELLでマイナス
    vol_score = 2 if signal_config['volatility'] else 0
    pattern_score = 2 if signal_config['patterns'] else 0
    
    total_score = trend_score + osc_score + vol_score + pattern_score
    max_score = 8
    
    signal_strength = (total_score / max_score) * 100
    
    if signal_strength > 70:
        st.success(f"🚀 **強いBUYシグナル** ({signal_strength:.0f}%)")
    elif signal_strength > 40:
        st.warning(f"⚡ **弱いシグナル** ({signal_strength:.0f}%)")
    else:
        st.info(f"😐 **中立** ({signal_strength:.0f}%)")
    
    # シグナル強度プログレスバー
    st.progress(int(signal_strength), f"シグナル強度: {signal_strength:.0f}%")


# セッション状態初期化
def initialize_signal_page_state():
    """シグナルページ用セッション状態初期化"""
    if 'signal_chart_symbol' not in st.session_state:
        st.session_state.signal_chart_symbol = 'USDJPY'
    if 'signal_chart_timeframe' not in st.session_state:
        st.session_state.signal_chart_timeframe = 'H1'  
    if 'signal_chart_period' not in st.session_state:
        st.session_state.signal_chart_period = 30