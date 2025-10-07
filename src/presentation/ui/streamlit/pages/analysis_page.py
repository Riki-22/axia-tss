# src/presentation/ui/streamlit/pages/analysis_page.py

import streamlit as st


def render_analysis_page():
    """分析ページのレンダリング"""
    _render_bayesian_analysis()
    st.markdown("---")
    _render_market_regime()
    st.markdown("---")
    _render_performance_metrics()


def _render_bayesian_analysis():
    """ベイジアン分析の表示"""
    st.markdown("#### 🧠 ベイジアン確率分析")
    b1, b2, b3, b4 = st.columns(4)
    
    with b1:
        st.metric("成功確率", "72.3%", "+17.3%")
    with b2:
        st.metric("事前確率", "55.0%", None)
    with b3:
        st.metric("尤度", "0.85", None)
    with b4:
        st.metric("推奨ロット", "0.73", None)


def _render_market_regime():
    """市場レジーム分析の表示"""
    st.markdown("#### 🗂️ 市場レジーム分析")
    r1, r2, r3 = st.columns(3)
    
    with r1:
        st.info("**レジーム**: 上昇トレンド")
        st.progress(78, "信頼度: 78%")
    with r2:
        st.metric("トレンド強度", "強", "↑")
    with r3:
        st.metric("ボラティリティ", "中", "→")


def _render_performance_metrics():
    """パフォーマンス指標の表示"""
    st.markdown("#### 🎯 パフォーマンス指標")
    p1, p2, p3, p4 = st.columns(4)
    
    with p1:
        st.metric("Sharpe Ratio", "1.85", "+0.12")
    with p2:
        st.metric("勝率", "68.5%", "→")
    with p3:
        st.metric("PF", "2.1", "+0.15")
    with p4:
        st.metric("最大DD", "-8.2%", "-1.2%")