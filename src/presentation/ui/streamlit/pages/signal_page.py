# src/presentation/ui/streamlit/pages/signal_page.py

import streamlit as st


def render_signal_page():
    """シグナルページのレンダリング"""
    _render_signal_overview()
    st.markdown("---")
    _render_integrated_analysis()


def _render_signal_overview():
    """シグナル概要の表示"""
    st.markdown("#### シグナル統合")
    sig1, sig2, sig3 = st.columns(3)
    
    with sig1:
        st.markdown("**📈 トレンド系**")
        st.success("MACD: BUY")
        st.success("MA Cross: BUY")
        st.info("Breakout: 監視中")
    
    with sig2:
        st.markdown("**📊 オシレーター**")
        st.warning("RSI: 中立(45)")
        st.success("Stochastic: BUY")
        st.error("RCI: SELL")
    
    with sig3:
        st.markdown("**💨 ボラティリティ**")
        st.success("BB: 下部タッチ")
        st.info("ATR: 0.0045")
        st.success("Squeeze: 拡大")


def _render_integrated_analysis():
    """統合分析の表示"""
    st.markdown("#### ⚡ 統合シグナル分析")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**推奨アクション**")
        st.success("### BUY")
        st.progress(75, "シグナル強度: 75%")
    
    with col2:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("トレンド", "+3/3", "✓")
        with c2:
            st.metric("オシレーター", "+2/3", "✓")
        with c3:
            st.metric("ボラティリティ", "+2/3", "✓")